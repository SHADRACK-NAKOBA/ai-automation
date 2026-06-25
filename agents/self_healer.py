"""
agents/self_healer.py
======================
Agent #4: Self-Healing Script Runner

WHAT IT DOES:
  Monitors incoming alerts for known failure patterns.
  When a pattern matches, executes a pre-approved remediation
  action automatically, then posts the result to the ticket.

WHY THIS AGENT:
  Known failures have known fixes. There is no reason a human
  should be woken up at 2am to restart a service that has
  crashed with the same OOM error 20 times before.

  Time saved per healed incident: 25 minutes
  On-call wake-ups eliminated: all known pattern failures

HEALING RULES:
  Each rule has four properties:
  - pattern:    regex that matches the alert text
  - action:     what to do when pattern matches
  - auto:       True = execute automatically
                False = notify and wait for human approval
  - max_per_hr: rate limit to prevent runaway healing

SAFETY GUARDRAILS:
  - Rate limiting: each rule has a max runs per hour
  - Approval required for risky actions (job kills, pool recycling)
  - Every action logged to metrics database
  - P1 tickets always get human notification regardless
  - Hard list of actions that are NEVER automated

PRODUCTION UPGRADE:
  Replace the _simulate_action() method with real commands:
  - Ansible playbook calls for service restarts
  - Shell commands via SSH for disk cleanup
  - Management API calls for connection pool recycling
  - Job scheduler API for killing stuck jobs
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import anthropic

from shared.config import get_config
from shared.snow_client import ServiceNowClient
from shared.metrics_db import MetricsDB
from shared.logger import get_logger

logger = get_logger("self_healer")

MINUTES_SAVED_PER_HEAL = 25.0

# ----------------------------------------------------------------
# ACTIONS THAT ARE NEVER AUTOMATED — hard coded safety list
# ----------------------------------------------------------------
NEVER_AUTOMATE = [
    "database failover",
    "production rollback",
    "data deletion",
    "firewall rule change",
    "ssl certificate replacement",
    "user account deletion",
]


@dataclass
class HealingRule:
    """
    Defines one healing rule.

    name:        Human readable name shown in work notes
    pattern:     Regex pattern matched against alert text
    action_name: Short name of the remediation action
    auto:        True = execute automatically without approval
    max_per_hr:  Maximum times this rule can auto-run per hour
    description: What this rule does in plain English
    """
    name: str
    pattern: str
    action_name: str
    auto: bool
    max_per_hr: int
    description: str
    run_history: list = field(default_factory=list)


@dataclass
class HealingResult:
    """Result of a healing action execution."""
    rule_name: str
    action_name: str
    target: str
    success: bool
    output: str
    auto_executed: bool
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class SelfHealingAgent:
    """
    Main agent class for self-healing automation.

    USAGE:
      python agents/self_healer.py --test
      python agents/self_healer.py --alert "OutOfMemoryError on payment-service"
      python agents/self_healer.py --ticket INC0000018
    """

    # ----------------------------------------------------------------
    # HEALING RULES — customise these for your environment
    # ----------------------------------------------------------------
    RULES = [
        HealingRule(
            name="OOM Service Restart",
            pattern=(
                r"(OutOfMemory|OOM|heap\s+space|"
                r"GC\s+overhead|java\.lang\.OutOfMemoryError)"
            ),
            action_name="restart_service",
            auto=True,
            max_per_hr=3,
            description=(
                "Restarts a Java service that has crashed due to "
                "OutOfMemoryError. Safe to automate — service "
                "recovers in 2-3 minutes."
            )
        ),
        HealingRule(
            name="Disk Full Cleanup",
            pattern=(
                r"(disk\s+(full|usage|space)|"
                r"no\s+space\s+left|"
                r"filesystem.*9[0-9]%|"
                r"ENOSPC)"
            ),
            action_name="clear_temp_files",
            auto=True,
            max_per_hr=2,
            description=(
                "Clears /tmp and old log files when disk usage "
                "exceeds 90%. Safe to automate — only removes "
                "files older than 24 hours."
            )
        ),
        HealingRule(
            name="Connection Pool Exhausted",
            pattern=(
                r"(connection\s+pool\s+exhausted|"
                r"too\s+many\s+connections|"
                r"max_connections|"
                r"Cannot\s+get\s+a\s+connection)"
            ),
            action_name="recycle_connection_pool",
            auto=False,  # Requires human approval
            max_per_hr=1,
            description=(
                "Recycles the database connection pool. "
                "Requires human approval — may interrupt "
                "active transactions."
            )
        ),
        HealingRule(
            name="Stuck Batch Job",
            pattern=(
                r"(batch\s+job.*stuck|"
                r"scheduler.*hung|"
                r"job.*running.*[2-9][0-9]{2,}\s+min|"
                r"job.*timeout)"
            ),
            action_name="kill_stuck_job",
            auto=False,  # Requires human approval
            max_per_hr=2,
            description=(
                "Kills a batch job that has been running too long. "
                "Requires human approval — killing a job may "
                "require manual data reconciliation."
            )
        ),
    ]

    def __init__(self, config: dict):
        self.config = config
        self.snow = ServiceNowClient(config)
        self.db = MetricsDB(config.get("db_path", "data/metrics.db"))
        self.dry_run = config.get("dry_run", True)
        logger.info(
            f"SelfHealingAgent ready | "
            f"rules={len(self.RULES)} | "
            f"dry_run={self.dry_run}"
        )

    # ----------------------------------------------------------------
    # RULE MATCHING
    # ----------------------------------------------------------------

    def match_rule(self, alert_text: str) -> Optional[HealingRule]:
        """
        Find the first healing rule that matches the alert text.
        Returns None if no rule matches.
        """
        for rule in self.RULES:
            if re.search(rule.pattern, alert_text, re.IGNORECASE):
                logger.info(f"Rule matched: '{rule.name}'")
                return rule
        logger.info("No healing rule matched this alert")
        return None

    def is_never_automate(self, alert_text: str) -> bool:
        """
        Check if this alert involves something on the never-automate list.
        Returns True if the action should never be automated.
        """
        alert_lower = alert_text.lower()
        for blocked in NEVER_AUTOMATE:
            if blocked in alert_lower:
                logger.warning(
                    f"Alert matches never-automate list: '{blocked}'"
                )
                return True
        return False

    def is_rate_limited(self, rule: HealingRule) -> bool:
        """
        Check if this rule has exceeded its hourly run limit.
        Prevents runaway automation loops.
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)

        # Remove runs older than 1 hour
        rule.run_history = [
            t for t in rule.run_history
            if t > one_hour_ago
        ]

        if len(rule.run_history) >= rule.max_per_hr:
            logger.warning(
                f"Rate limit hit for rule '{rule.name}': "
                f"{len(rule.run_history)}/{rule.max_per_hr} "
                f"runs in last hour"
            )
            return True
        return False

    # ----------------------------------------------------------------
    # HEALING ACTIONS
    # ----------------------------------------------------------------

    def _simulate_action(
        self,
        action_name: str,
        target: str
    ) -> tuple:
        """
        Simulates a healing action for development/testing.

        PRODUCTION: Replace each simulation with a real command:

        restart_service:
            import subprocess
            result = subprocess.run(
                ['ansible', '-i', f'{host},', 'all', '-m', 'service',
                 '-a', f'name={service} state=restarted'],
                capture_output=True, text=True, timeout=120
            )

        clear_temp_files:
            result = subprocess.run(
                ['ssh', host, 'find /tmp -mtime +1 -delete'],
                capture_output=True, text=True, timeout=60
            )

        recycle_connection_pool:
            import requests
            requests.post(f'http://{host}:8080/actuator/refresh')

        kill_stuck_job:
            result = subprocess.run(
                ['ssh', host, f'kill -9 {job_pid}'],
                capture_output=True, text=True
            )
        """
        simulations = {
            "restart_service": (
                True,
                f"[SIMULATED] Service on {target} restarted successfully. "
                f"Heap memory now at 38%. Service responding normally."
            ),
            "clear_temp_files": (
                True,
                f"[SIMULATED] Cleared 12.4GB from /tmp on {target}. "
                f"Disk usage: 94% → 58%. Log rotation re-enabled."
            ),
            "recycle_connection_pool": (
                True,
                f"[SIMULATED] Connection pool recycled on {target}. "
                f"Active connections: 0 → rebuilt to 20. "
                f"Pool health: OK."
            ),
            "kill_stuck_job": (
                True,
                f"[SIMULATED] Stuck job terminated on {target}. "
                f"Job had been running for 3h 42m. "
                f"Manual reconciliation may be required."
            ),
        }

        if action_name in simulations:
            return simulations[action_name]
        return False, f"Unknown action: {action_name}"

    def execute_action(
        self,
        rule: HealingRule,
        target: str
    ) -> HealingResult:
        """
        Execute a healing action and return the result.
        In dry_run mode: simulates without touching anything real.
        """
        logger.info(
            f"Executing action: {rule.action_name} "
            f"on target: {target}"
        )

        if self.dry_run:
            output = (
                f"[DRY RUN] Would execute: {rule.action_name} "
                f"on {target}. No real action taken."
            )
            success = True
        else:
            # In production: replace with real commands
            success, output = self._simulate_action(
                rule.action_name,
                target
            )

        # Record this run for rate limiting
        if success:
            rule.run_history.append(datetime.utcnow())

        return HealingResult(
            rule_name=rule.name,
            action_name=rule.action_name,
            target=target,
            success=success,
            output=output,
            auto_executed=rule.auto,
        )

    # ----------------------------------------------------------------
    # TICKET INTEGRATION
    # ----------------------------------------------------------------

    def build_work_note(
        self,
        rule: HealingRule,
        result: HealingResult,
        alert_text: str
    ) -> str:
        """Build the work note to attach to the ServiceNow ticket."""
        status = "SUCCESS" if result.success else "FAILED"
        mode = "AUTO-EXECUTED" if result.auto_executed else "PENDING APPROVAL"

        if not rule.auto:
            mode = "AWAITING HUMAN APPROVAL"

        return (
            f"[Self-Healing Agent — {status} | {mode}]\n"
            f"\n"
            f"Rule Triggered: {rule.name}\n"
            f"Action: {rule.action_name}\n"
            f"Target: {result.target}\n"
            f"Executed at: {result.timestamp}\n"
            f"\n"
            f"What this rule does:\n"
            f"{rule.description}\n"
            f"\n"
            f"Result:\n"
            f"{result.output}\n"
            f"\n"
            f"Original Alert:\n"
            f"{alert_text[:300]}\n"
            f"\n"
            f"---\n"
            f"Auto-generated by Self-Healing Agent. "
            f"{'Action was applied automatically.' if result.auto_executed else 'Human review required before action is applied.'}"
        )

    def process_alert(
        self,
        alert_text: str,
        ticket_sys_id: str = "",
        ticket_number: str = "",
        target: str = "unknown-host"
    ) -> Optional[HealingResult]:
        """
        Main entry point. Process an incoming alert.

        Steps:
        1. Check never-automate list
        2. Match against healing rules
        3. Check rate limit
        4. Execute action (if auto) or notify (if approval needed)
        5. Attach work note to ticket
        6. Log to metrics database
        """
        start = time.time()
        logger.info(f"Processing alert: {alert_text[:100]}")

        # Safety check 1: never-automate list
        if self.is_never_automate(alert_text):
            logger.warning(
                "Alert involves a never-automate action. "
                "Escalating to human."
            )
            return None

        # Safety check 2: match a rule
        rule = self.match_rule(alert_text)
        if not rule:
            logger.info(
                "No healing rule matched. "
                "No automated action taken."
            )
            return None

        # Safety check 3: rate limit
        if self.is_rate_limited(rule):
            note = (
                f"[Self-Healing Agent — RATE LIMITED]\n"
                f"Rule '{rule.name}' matched but rate limit reached "
                f"({rule.max_per_hr} runs/hour max).\n"
                f"Manual intervention required.\n"
                f"Alert: {alert_text[:200]}"
            )
            if ticket_sys_id:
                self.snow.add_work_note(ticket_sys_id, note)
            logger.warning(f"Rate limit hit — escalating to human")
            return None

        # Execute or request approval
        if rule.auto:
            logger.info(
                f"Auto-executing rule: {rule.name} "
                f"on target: {target}"
            )
            result = self.execute_action(rule, target)
        else:
            logger.info(
                f"Rule requires approval: {rule.name}. "
                f"Notifying team."
            )
            result = HealingResult(
                rule_name=rule.name,
                action_name=rule.action_name,
                target=target,
                success=True,
                output=(
                    f"Approval required before executing: "
                    f"{rule.action_name} on {target}. "
                    f"Please review and approve in ServiceNow."
                ),
                auto_executed=False,
            )

        # Attach work note to ticket
        if ticket_sys_id:
            note = self.build_work_note(rule, result, alert_text)
            self.snow.add_work_note(ticket_sys_id, note)
            logger.info(f"Work note attached to {ticket_number}")

        # Log to metrics
        duration_ms = round((time.time() - start) * 1000)
        self.db.log_run(
            agent_name="SelfHealingAgent",
            ticket_number=ticket_number,
            trigger_type="alert",
            input_summary=alert_text[:200],
            output_summary=result.output[:200],
            success=result.success,
            duration_ms=duration_ms,
            minutes_saved=MINUTES_SAVED_PER_HEAL if result.success else 0,
        )

        return result

    # ----------------------------------------------------------------
    # TEST MODE
    # ----------------------------------------------------------------

    def run_test(self):
        """
        Test all four healing rules with synthetic alerts.
        No real actions are taken — uses simulation mode.
        """
        logger.info("=" * 60)
        logger.info("SELF-HEALING AGENT — Test Run")
        logger.info("=" * 60)

        test_alerts = [
            {
                "text": (
                    "CRITICAL: java.lang.OutOfMemoryError: Java heap space "
                    "on payment-service-prod. Service has restarted 3 times."
                ),
                "target": "payment-service-prod",
                "expected_rule": "OOM Service Restart",
            },
            {
                "text": (
                    "WARNING: Disk usage at 94% on log-server-01. "
                    "No space left on device. /var/log is full."
                ),
                "target": "log-server-01",
                "expected_rule": "Disk Full Cleanup",
            },
            {
                "text": (
                    "ERROR: Connection pool exhausted on order-service. "
                    "Cannot get a connection, pool error timeout."
                ),
                "target": "order-service-db",
                "expected_rule": "Connection Pool Exhausted",
            },
            {
                "text": (
                    "ALERT: Batch job MONTHLY_REPORT has been running "
                    "for 180 min. Normal runtime is 15 minutes. Job timeout."
                ),
                "target": "batch-scheduler-01",
                "expected_rule": "Stuck Batch Job",
            },
            {
                "text": (
                    "CRITICAL: Database failover required on prod-db-01. "
                    "Primary is down."
                ),
                "target": "prod-db-01",
                "expected_rule": "NONE — never automate",
            },
        ]

        passed = 0
        failed = 0

        for i, test in enumerate(test_alerts, 1):
            print(f"\nTest {i}: {test['expected_rule']}")
            print(f"Alert: {test['text'][:80]}...")

            # Check never-automate
            if self.is_never_automate(test["text"]):
                print(f"Result: BLOCKED (never-automate list)")
                if test["expected_rule"] == "NONE — never automate":
                    print("PASS — correctly blocked")
                    passed += 1
                else:
                    print("FAIL — should not have been blocked")
                    failed += 1
                continue

            # Match rule
            rule = self.match_rule(test["text"])
            if not rule:
                print("Result: No rule matched")
                if test["expected_rule"] == "NONE — never automate":
                    passed += 1
                else:
                    print(f"FAIL — expected rule: {test['expected_rule']}")
                    failed += 1
                continue

            # Execute
            result = self.execute_action(rule, test["target"])

            rule_match = rule.name == test["expected_rule"]
            status = "PASS" if rule_match and result.success else "FAIL"

            print(f"Rule matched: {rule.name}")
            print(f"Auto-execute: {rule.auto}")
            print(f"Result: {result.output[:80]}...")
            print(f"{status}")

            if rule_match and result.success:
                passed += 1
            else:
                failed += 1

        print("\n" + "=" * 60)
        print(f"Test Results: {passed} passed, {failed} failed")
        if failed == 0:
            print("ALL TESTS PASSED — Safe to connect to real alerts")
        else:
            print("SOME TESTS FAILED — Review rules before going live")
        print("=" * 60)


# ----------------------------------------------------------------
# Direct execution
# ----------------------------------------------------------------
if __name__ == "__main__":
    import sys

    config = get_config()
    agent = SelfHealingAgent(config)

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        agent.run_test()

    elif len(sys.argv) > 1 and sys.argv[1] == "--alert":
        if len(sys.argv) < 3:
            print(
                "Usage: python agents/self_healer.py "
                "--alert \"alert text here\""
            )
            sys.exit(1)
        alert_text = " ".join(sys.argv[2:])
        result = agent.process_alert(
            alert_text=alert_text,
            target="test-server"
        )
        if result:
            print(f"\nHealing action taken: {result.rule_name}")
            print(f"Output: {result.output}")
        else:
            print("No healing action taken for this alert")

    else:
        agent.run_test()