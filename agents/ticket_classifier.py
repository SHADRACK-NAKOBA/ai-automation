"""
agents/ticket_classifier.py
============================
Agent #1: AI-Powered Ticket Auto-Classifier

WHAT IT DOES:
  Reads unclassified ServiceNow tickets, uses Claude to determine:
  - Category (Database, Network, Application, etc.)
  - Priority (P1, P2, P3, P4)
  - Suggested assignment team
  - Confidence score (0.0 to 1.0)

  If confidence >= threshold (default 0.75): auto-applies classification
  If confidence < threshold: adds AI suggestion comment for human review
  P1 is NEVER auto-applied — always requires human confirmation.

WHY THIS AGENT FIRST:
  It's the highest-frequency automation target.
  Every single ticket needs classification. This is manual work
  that happens 100+ times per day. High volume = high ROI.
  It's also the safest first automation — wrong classification
  is annoying but not dangerous.

DESIGN DECISIONS:
  - Structured JSON output: We ask Claude for JSON, not prose.
    Prose is hard to parse reliably. JSON is deterministic.
  - Confidence threshold: We don't trust AI blindly.
    Below 0.75 = flag, not apply.
  - P1 guardrail: Hard-coded. Never auto-apply P1. Period.
  - Audit trail: Every classification gets logged to metrics DB.
  - Dry run mode: ALWAYS test with dry_run=True first.

MINUTES SAVED PER RUN: ~4 minutes per ticket
ESTIMATED WEEKLY VOLUME: 100-500 tickets depending on team size
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional
import anthropic

from shared.config import get_config
from shared.snow_client import ServiceNowClient
from shared.data_sanitizer import sanitize_ticket
from shared.metrics_db import MetricsDB
from shared.logger import get_logger

logger = get_logger("ticket_classifier")

CATEGORIES = [
    "Database", "Network", "Application", "Authentication",
    "Performance", "Data_Quality", "Integration", "Security", "Other"
]

PRIORITIES = ["P1", "P2", "P3", "P4"]

PRIORITY_MAP = {"P1": "1", "P2": "2", "P3": "3", "P4": "4"}

MINUTES_SAVED_PER_TICKET = 4.0


@dataclass
class ClassificationResult:
    category: str
    priority: str
    suggested_team: str
    confidence: float
    reason: str
    tags: list = field(default_factory=list)


def build_classification_prompt(ticket: dict) -> str:
    """
    Build the Claude prompt for classifying a ticket.

    WHY DETAILED PRIORITY GUIDE:
      'P1' means different things to different teams.
      By defining exactly what P1 means here, we get consistent results.
      This prompt is the place to tune when accuracy is off.
    """
    return f"""You are a senior IT application support analyst with 10+ years of experience.
Your job is to classify this support ticket accurately.

AVAILABLE CATEGORIES:
{', '.join(CATEGORIES)}

CATEGORY DEFINITIONS:
- Application: service crashes, OOM errors, restarts, wrong business logic, incorrect calculations, disk full on app servers
- Performance: slowness, high latency, timeouts, queries taking longer than expected — service is still UP but slow
- Data_Quality: bad data in records, import failures, validation errors on DATA — not on the application itself
- Database: DB connectivity, listener down, connection pool, query failures at DB level
- Integration: missing feeds, SFTP failures, API-to-API connection issues

PRIORITY DEFINITIONS:
- P1: Complete outage, revenue impact, >100 users cannot work, data loss risk
- P2: Major function broken, significant user impact (10-100 users), workaround unavailable
- P3: Partial degradation, workaround exists, moderate impact (<10 users affected)
- P4: Minor issue, cosmetic bug, single user, enhancement request, hardware upgrade

TICKET TO CLASSIFY:
Title: {ticket.get('short_description', 'No title')}
Description: {ticket.get('description', 'No description')[:1500]}
Submitted by: {ticket.get('caller_id', {}).get('display_value', 'Unknown')}
Affected system: {ticket.get('cmdb_ci', {}).get('display_value', 'Unknown') if isinstance(ticket.get('cmdb_ci'), dict) else ticket.get('cmdb_ci', 'Unknown')}

INSTRUCTIONS:
1. Analyze the ticket carefully
2. Choose the single best category from the list above
3. Assign a priority based ONLY on the definitions above
4. Suggest an assignment team (be specific: "Database Team", "Network Ops", "App Support L2")
5. Give a confidence score (0.0 to 1.0) — be honest if the ticket is ambiguous
6. Provide one clear sentence explaining your classification

Respond with ONLY a valid JSON object, no markdown, no explanation outside the JSON:
{{
  "category": "<category>",
  "priority": "<P1|P2|P3|P4>",
  "suggested_team": "<team name>",
  "confidence": <float>,
  "reason": "<one sentence>",
  "tags": ["<tag1>", "<tag2>"]
}}"""


def parse_claude_response(raw: str) -> Optional[ClassificationResult]:
    """
    Parse Claude's JSON response into a ClassificationResult.
    Handles common issues like markdown code fences.
    """
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    try:
        data = json.loads(cleaned)

        # Validate required fields
        required = ["category", "priority", "suggested_team", "confidence", "reason"]
        for field_name in required:
            if field_name not in data:
                raise ValueError(f"Missing field: {field_name}")

        # Validate values are in allowed sets
        if data["category"] not in CATEGORIES:
            data["category"] = "Other"
        if data["priority"] not in PRIORITIES:
            data["priority"] = "P3"
        data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))

        return ClassificationResult(
            category=data["category"],
            priority=data["priority"],
            suggested_team=data["suggested_team"],
            confidence=data["confidence"],
            reason=data["reason"],
            tags=data.get("tags", []),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Claude response: {e}\nRaw: {raw[:200]}")
        return None


class TicketClassifier:
    """
    Main agent class.

    USAGE:
      config = get_config()
      agent = TicketClassifier(config)
      agent.run()                    # Process all unclassified tickets
      agent.run_single("INC001")     # Process one specific ticket
    """

    def __init__(self, config: dict):
        self.config = config
        self.snow = ServiceNowClient(config)
        self.ai = anthropic.Anthropic(api_key=config["anthropic_key"])
        self.db = MetricsDB(config.get("db_path", "data/metrics.db"))
        self.threshold = config.get("confidence_threshold", 0.75)
        self.dry_run = config.get("dry_run", True)
        self.model = config.get("ai_model", "claude-sonnet-4-6")
        self.max_tokens = config.get("ai_max_tokens", 1000)

        logger.info(
            f"TicketClassifier ready | threshold={self.threshold} | "
            f"dry_run={self.dry_run} | model={self.model}"
        )

    def classify(self, ticket: dict) -> Optional[ClassificationResult]:
        """
        Send one ticket to Claude for classification.
        Returns None if classification fails.
        """
        # Sanitize BEFORE sending to external API
        safe_ticket = sanitize_ticket(ticket)
        prompt = build_classification_prompt(safe_ticket)

        try:
            message = self.ai.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            return parse_claude_response(raw)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def apply_classification(
        self, ticket: dict, result: ClassificationResult
    ) -> bool:
        """
        Apply the classification back to ServiceNow.
        Decision logic:
          - confidence >= threshold AND not P1 → auto-apply
          - confidence < threshold OR P1 → add suggestion comment only
        """
        number = ticket.get("number", "UNKNOWN")
        sys_id = ticket.get("sys_id", "")
        is_p1 = result.priority == "P1"
        above_threshold = result.confidence >= self.threshold
        auto_apply = above_threshold and not is_p1

        # Build the comment that always gets added
        action_label = "AUTO-APPLIED ✅" if auto_apply else "SUGGESTION ONLY 💡"
        if is_p1:
            action_label = "P1 — HUMAN REVIEW REQUIRED ⚠️"

        comment = (
            f"[AI Ticket Classifier — {action_label}]\n"
            f"Category: {result.category}\n"
            f"Priority: {result.priority}\n"
            f"Suggested Team: {result.suggested_team}\n"
            f"Confidence: {result.confidence:.0%}\n"
            f"Reason: {result.reason}\n"
            f"Tags: {', '.join(result.tags) if result.tags else 'none'}\n"
            f"---\n"
            f"This classification was generated by AI. "
            f"{'Applied automatically (confidence ≥ {:.0%}).'.format(self.threshold) if auto_apply else 'Please review and apply manually.'}"
        )

        payload = {"work_notes": comment}

        if auto_apply:
            payload.update({
                "category": result.category.lower(),
                "priority": PRIORITY_MAP.get(result.priority, "3"),
                "assignment_group": result.suggested_team,
            })

        success = self.snow.update_incident(sys_id, payload)

        # Log to metrics DB
        self.db.log_run(
            agent_name="TicketClassifier",
            ticket_number=number,
            trigger_type="scheduled",
            input_summary=ticket.get("short_description", "")[:200],
            output_summary=f"{result.category}/{result.priority} ({result.confidence:.0%})",
            classification={
                "category": result.category,
                "priority": result.priority,
                "team": result.suggested_team,
            },
            confidence=result.confidence,
            auto_applied=auto_apply,
            success=success,
            minutes_saved=MINUTES_SAVED_PER_TICKET if success else 0,
        )

        status = "AUTO-APPLIED" if auto_apply else "SUGGESTED"
        logger.info(
            f"  {number}: [{result.category}/{result.priority}] "
            f"confidence={result.confidence:.0%} → {status}"
        )
        return success

    def run(self, limit: int = 50) -> dict:
        """
        Main entry point. Fetches and classifies all unclassified tickets.
        Returns a summary dict.
        """
        start = time.time()
        logger.info("=" * 60)
        logger.info("TICKET CLASSIFIER — Starting run")
        logger.info(f"  DRY RUN: {self.dry_run}")
        logger.info(f"  Confidence threshold: {self.threshold:.0%}")
        logger.info("=" * 60)

        tickets = self.snow.get_unclassified_tickets(limit=limit)
        if not tickets:
            logger.info("No unclassified tickets found.")
            return {"processed": 0, "auto_applied": 0, "suggested": 0, "failed": 0}

        stats = {"processed": 0, "auto_applied": 0, "suggested": 0, "failed": 0}

        for ticket in tickets:
            number = ticket.get("number", "UNKNOWN")
            logger.info(f"Processing {number}: {ticket.get('short_description', '')[:60]}...")

            result = self.classify(ticket)
            if result is None:
                stats["failed"] += 1
                continue

            success = self.apply_classification(ticket, result)
            stats["processed"] += 1
            if success:
                is_p1 = result.priority == "P1"
                if result.confidence >= self.threshold and not is_p1:
                    stats["auto_applied"] += 1
                else:
                    stats["suggested"] += 1
            else:
                stats["failed"] += 1

        elapsed = round((time.time() - start) * 1000)
        hours_saved = (stats["processed"] * MINUTES_SAVED_PER_TICKET) / 60

        logger.info("=" * 60)
        logger.info("TICKET CLASSIFIER — Run complete")
        logger.info(f"  Processed:    {stats['processed']}")
        logger.info(f"  Auto-applied: {stats['auto_applied']}")
        logger.info(f"  Suggested:    {stats['suggested']}")
        logger.info(f"  Failed:       {stats['failed']}")
        logger.info(f"  Hours saved:  {hours_saved:.2f}h")
        logger.info(f"  Duration:     {elapsed}ms")
        logger.info("=" * 60)

        return stats

    def run_single(self, ticket_number_or_sys_id: str) -> Optional[ClassificationResult]:
        """Process a single ticket by number or sys_id. Useful for testing."""
        tickets = self.snow.get_unclassified_tickets(limit=200)
        ticket = next(
            (t for t in tickets if
             t.get("number") == ticket_number_or_sys_id or
             t.get("sys_id") == ticket_number_or_sys_id),
            None
        )
        if not ticket:
            logger.error(f"Ticket not found: {ticket_number_or_sys_id}")
            return None
        result = self.classify(ticket)
        if result:
            self.apply_classification(ticket, result)
        return result


def run_accuracy_test(agent: TicketClassifier) -> dict:
    """
    Compare AI classifications against expected values in synthetic data.
    Run this before going live to validate accuracy.

    Target: >80% category accuracy, >85% priority accuracy
    """
    import json
    from pathlib import Path

    path = Path("data/synthetic/tickets.json")
    if not path.exists():
        logger.error("No synthetic data found. Run: python tools/seed_data.py")
        return {}

    with open(path) as f:
        tickets = json.load(f)

    # Only test tickets that have expected values
    test_tickets = [t for t in tickets if t.get("expected_category")]
    results = []

    logger.info(f"\nRunning accuracy test on {len(test_tickets)} tickets...")
    logger.info("-" * 70)

    for ticket in test_tickets:
        result = agent.classify(ticket)
        if not result:
            continue

        cat_match = result.category == ticket["expected_category"]
        pri_match = result.priority == ticket["expected_priority"]
        results.append({
            "number": ticket["number"],
            "expected_cat": ticket["expected_category"],
            "got_cat": result.category,
            "cat_correct": cat_match,
            "expected_pri": ticket["expected_priority"],
            "got_pri": result.priority,
            "pri_correct": pri_match,
            "confidence": result.confidence,
        })

        status = "✅" if (cat_match and pri_match) else "❌"
        logger.info(
            f"{status} {ticket['number']} | "
            f"Cat: {ticket['expected_category']} → {result.category} {'✓' if cat_match else '✗'} | "
            f"Pri: {ticket['expected_priority']} → {result.priority} {'✓' if pri_match else '✗'} | "
            f"Conf: {result.confidence:.0%}"
        )

    total = len(results)
    if total == 0:
        return {}

    cat_accuracy = sum(1 for r in results if r["cat_correct"]) / total
    pri_accuracy = sum(1 for r in results if r["pri_correct"]) / total

    logger.info("-" * 70)
    logger.info(f"Category accuracy: {cat_accuracy:.0%} (target: >80%)")
    logger.info(f"Priority accuracy: {pri_accuracy:.0%} (target: >85%)")

    if cat_accuracy >= 0.80 and pri_accuracy >= 0.85:
        logger.info("✅ ACCURACY TARGETS MET — Safe to go live")
    else:
        logger.info("❌ ACCURACY BELOW TARGET — Tune the prompt before going live")

    return {
        "total": total,
        "category_accuracy": cat_accuracy,
        "priority_accuracy": pri_accuracy,
        "targets_met": cat_accuracy >= 0.80 and pri_accuracy >= 0.85,
    }


# ------------------------------------------------------------------ #
# Direct execution
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import sys
    config = get_config()
    agent = TicketClassifier(config)

    if len(sys.argv) > 1 and sys.argv[1] == "--accuracy-test":
        run_accuracy_test(agent)
    elif len(sys.argv) > 1 and sys.argv[1] == "--ticket":
        ticket_id = sys.argv[2] if len(sys.argv) > 2 else None
        if ticket_id:
            result = agent.run_single(ticket_id)
            if result:
                print(f"\nResult: {result}")
    else:
        agent.run()
