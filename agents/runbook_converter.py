"""
agents/runbook_converter.py
============================
Agent #7: Runbook Converter

WHAT IT DOES:
  Takes any manual runbook (text, Word doc content, or Confluence page)
  and converts it into three production-ready artifacts:

  1. ANALYST CHECKLIST
     A numbered step-by-step checklist any L1 analyst can follow.
     Includes time estimates, exact commands, expected outputs,
     and escalation points.

  2. AUTOMATION SCRIPT
     A Python script that automates every safe step.
     Steps requiring human judgment get TODO comments.
     Steps that are automatable get working code templates.

  3. DECISION FLOWCHART
     A Mermaid diagram showing the decision tree.
     When to proceed, when to escalate, when to rollback.

WHY THIS AGENT:
  Manual runbooks sit in folders and nobody reads them.
  This agent turns them into executable, trackable, improvable assets.
  L1 analysts can handle procedures previously requiring L2/L3.
  Tribal knowledge becomes code before it walks out the door.

TIME SAVED: 60 minutes per runbook converted

HOW IT WORKS:
  1. Receives runbook text (paste, file, or ticket description)
  2. Sends to Claude with structured conversion prompt
  3. Claude extracts steps, decisions, and automation opportunities
  4. Three artifacts generated and saved to docs/runbooks/
  5. Summary attached to ServiceNow ticket if provided

USAGE:
  python agents/runbook_converter.py --test
  python agents/runbook_converter.py --file path/to/runbook.txt
  python agents/runbook_converter.py --text "restart the service when..."
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from shared.config import get_config
from shared.metrics_db import MetricsDB
from shared.logger import get_logger

logger = get_logger("runbook_converter")

MINUTES_SAVED_PER_RUNBOOK = 60.0

# ----------------------------------------------------------------
# SAMPLE RUNBOOKS FOR TESTING
# ----------------------------------------------------------------

SAMPLE_RUNBOOK_OOM = """
RUNBOOK: Payment Service OOM Recovery
Version: 1.2
Last Updated: 2025-01-15
Author: Platform Team

WHEN TO USE THIS RUNBOOK:
Use this runbook when the payment service crashes with
OutOfMemoryError or when heap usage exceeds 90%.

PREREQUISITES:
- SSH access to production servers
- kubectl access to the payment-service namespace
- Access to Dynatrace monitoring dashboard
- Contact number for Payments Engineering team lead

STEPS:

1. VERIFY THE ISSUE
   - Log into Dynatrace and confirm heap usage is >90%
   - Check the service is actually down: curl -f https://payments.company.com/health
   - If service is responding, monitor for 5 minutes before proceeding
   - If service is down, proceed to step 2 immediately

2. NOTIFY THE TEAM
   - Post in #incidents Slack channel: "P1: Payment service OOM - investigating"
   - Page the Payments Engineering on-call via PagerDuty
   - Notify your manager if it is outside business hours

3. IMMEDIATE STABILISATION
   - SSH to the affected server: ssh prod-payment-01.company.com
   - Check current JVM settings: ps aux | grep java | grep Xmx
   - Increase heap size in the startup config file:
     /opt/payment-service/config/jvm.options
   - Change -Xmx2g to -Xmx4g
   - Restart the service: sudo systemctl restart payment-service
   - Wait 2 minutes and check health: curl -f https://payments.company.com/health

4. VERIFY RECOVERY
   - Confirm heap usage drops below 70% in Dynatrace
   - Check payment processing has resumed: look for successful transactions in logs
   - Monitor for 15 minutes to confirm stability
   - If service crashes again within 15 minutes, go to step 5

5. ESCALATION (if step 3 did not work)
   - Do NOT restart again - you need to capture a heap dump first
   - Capture heap dump: jmap -dump:format=b,file=/tmp/heap.hprof PID
   - Copy heap dump off server: scp prod-payment-01:/tmp/heap.hprof ./
   - Contact Payments Engineering team lead immediately
   - Do not attempt further fixes without engineering guidance

6. RESOLUTION CONFIRMATION
   - Confirm with Payments team that root cause is identified
   - Update the incident ticket with what was done and outcome
   - Schedule a post-incident review if this is the 3rd occurrence this month

ROLLBACK:
   If increasing heap made things worse:
   - Revert jvm.options to original settings
   - Restart service with original settings
   - Escalate to Payments Engineering immediately

CONTACTS:
   Payments Engineering Lead: ext 4521
   Platform Team: #platform-team Slack
   PagerDuty: payments-oncall policy
"""

SAMPLE_RUNBOOK_DISK = """
RUNBOOK: Disk Space Recovery
Version: 2.0
Last Updated: 2025-02-10

WHEN TO USE:
When disk usage exceeds 85% on any production server.

STEPS:

1. Identify the full disk
   Run: df -h
   Note which filesystem is full

2. Find what is using the space
   Run: du -sh /* 2>/dev/null | sort -rh | head -20
   Usually it is /var/log or /tmp

3. Clear old log files (SAFE TO DO)
   - Check log age: ls -lah /var/log/
   - Delete logs older than 30 days: find /var/log -mtime +30 -delete
   - Check again: df -h

4. Clear temp files (SAFE TO DO)
   - Delete files in /tmp older than 1 day: find /tmp -mtime +1 -delete
   - Check again: df -h

5. If still above 85% - escalate
   - Do NOT delete application files
   - Contact the server owner
   - Open a ticket for storage expansion

TARGET: Get disk below 70% usage
"""


class RunbookConverter:
    """
    Converts manual runbooks into checklists, scripts, and flowcharts.

    USAGE:
      python agents/runbook_converter.py --test
      python agents/runbook_converter.py --file runbook.txt
      python agents/runbook_converter.py --text "your runbook text"
    """

    def __init__(self, config: dict):
        self.config = config
        self.ai = anthropic.Anthropic(api_key=config["anthropic_key"])
        self.db = MetricsDB(config.get("db_path", "data/metrics.db"))
        self.model = config.get("ai_model", "claude-sonnet-4-6")
        self.max_tokens = config.get("ai_max_tokens", 1000)

        # Ensure output directory exists
        Path("docs/runbooks").mkdir(parents=True, exist_ok=True)

        logger.info(f"RunbookConverter ready | model={self.model}")

    # ----------------------------------------------------------------
    # ARTIFACT 1: ANALYST CHECKLIST
    # ----------------------------------------------------------------

    def build_checklist_prompt(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Build prompt for generating the analyst checklist."""
        return f"""You are a senior technical writer converting a manual
runbook into a step-by-step checklist for L1 support analysts.

RUNBOOK NAME: {runbook_name}

ORIGINAL RUNBOOK:
{runbook_text}

Convert this into a numbered checklist that:
1. Any L1 analyst can follow without prior knowledge
2. Has exact commands (not descriptions of commands)
3. Includes time estimates for each step in brackets like [~2 min]
4. Shows what success looks like after each verification step
5. Flags steps requiring senior approval with: ⚠ REQUIRES APPROVAL
6. Flags dangerous/irreversible steps with: 🔴 IRREVERSIBLE
7. Includes a PREREQUISITES section at the top
8. Includes a ROLLBACK section at the bottom
9. Includes contact information section

FORMAT:
# {runbook_name} — Analyst Checklist
**Version:** AI-Generated | **Source:** Original runbook
**Difficulty:** L1 | **Estimated Total Time:** [X minutes]

## Prerequisites
- [ ] [prerequisite 1]
- [ ] [prerequisite 2]

## Steps

### Phase 1: [Phase Name]
- [ ] **Step 1** [~X min]: [Exact action]
  - Command: `exact command here`
  - Expected output: `what you should see`
  - If this fails: [what to do]

[Continue for all steps]

## Rollback
[If something goes wrong, do these steps in reverse order]

## Contacts
[Who to call and when]

## Completion Confirmation
- [ ] All steps completed
- [ ] Incident ticket updated
- [ ] Manager notified if required"""

    def build_script_prompt(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Build prompt for generating the automation script."""
        return f"""You are a senior DevOps engineer converting a manual
runbook into a Python automation script.

RUNBOOK NAME: {runbook_name}

ORIGINAL RUNBOOK:
{runbook_text}

Write a Python script that automates every safe step in this runbook.

RULES:
1. Steps that are SAFE to automate: health checks, log file operations,
   disk space checks, service status checks, file cleanup
2. Steps requiring HUMAN DECISION: service restarts, configuration changes,
   escalations, anything affecting customer data
3. For safe steps: write working Python code
4. For human decision steps: write a TODO comment explaining what is needed
5. Include a dry_run=True parameter that prints what would happen
   without doing it
6. Include proper error handling and logging
7. Include a main() function that runs the full procedure
8. Add a __name__ == "__main__" block

FORMAT:
\"\"\"
{runbook_name} — Automation Script
Auto-generated from manual runbook by Runbook Converter Agent.
Review all TODO sections before running in production.
\"\"\"

import subprocess
import sys
import os
import logging

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN = True  # Set to False to execute real commands

[Rest of the script]"""

    def build_flowchart_prompt(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Build prompt for generating the Mermaid flowchart."""
        return f"""You are a technical architect creating a decision flowchart
for a support runbook.

RUNBOOK NAME: {runbook_name}

ORIGINAL RUNBOOK:
{runbook_text}

Create a Mermaid flowchart (graph TD format) that shows:
1. The starting trigger condition
2. Each decision point as a diamond shape
3. Each action as a rectangle
4. Success paths in green
5. Escalation paths leading to an escalation box
6. Rollback paths when things go wrong

The flowchart must be valid Mermaid syntax starting with:
graph TD

Use these node styles:
- Decision: {{Is service down?}}
- Action: [Restart service]
- Terminal success: ([Incident Resolved])
- Terminal escalation: ([Escalate to Engineering])

Keep it focused on the key decision points — maximum 15 nodes.
Return ONLY the Mermaid code, no explanation."""

    # ----------------------------------------------------------------
    # GENERATION
    # ----------------------------------------------------------------

    def generate_checklist(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Generate the analyst checklist."""
        logger.info("Generating analyst checklist...")
        prompt = self.build_checklist_prompt(runbook_name, runbook_text)
        message = self.ai.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_script(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Generate the automation script."""
        logger.info("Generating automation script...")
        prompt = self.build_script_prompt(runbook_name, runbook_text)
        message = self.ai.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_flowchart(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> str:
        """Generate the Mermaid decision flowchart."""
        logger.info("Generating decision flowchart...")
        prompt = self.build_flowchart_prompt(runbook_name, runbook_text)
        message = self.ai.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    # ----------------------------------------------------------------
    # SAVING
    # ----------------------------------------------------------------

    def save_artifacts(
        self,
        runbook_name: str,
        checklist: str,
        script: str,
        flowchart: str
    ) -> dict:
        """Save all three artifacts to docs/runbooks/."""
        date_str = datetime.now().strftime("%Y_%m_%d")
        safe_name = runbook_name.replace(" ", "_").replace("/", "_")

        paths = {}

        # Save checklist
        checklist_path = (
            Path("docs/runbooks") /
            f"{safe_name}_checklist_{date_str}.md"
        )
        checklist_path.write_text(checklist, encoding="utf-8")
        paths["checklist"] = checklist_path
        logger.info(f"Checklist saved: {checklist_path}")

        # Save automation script
        script_path = (
            Path("docs/runbooks") /
            f"{safe_name}_automation_{date_str}.py"
        )
        script_path.write_text(script, encoding="utf-8")
        paths["script"] = script_path
        logger.info(f"Script saved: {script_path}")

        # Save flowchart
        flowchart_path = (
            Path("docs/runbooks") /
            f"{safe_name}_flowchart_{date_str}.md"
        )
        flowchart_content = (
            f"# {runbook_name} — Decision Flowchart\n\n"
            f"```mermaid\n{flowchart}\n```\n"
        )
        flowchart_path.write_text(flowchart_content, encoding="utf-8")
        paths["flowchart"] = flowchart_path
        logger.info(f"Flowchart saved: {flowchart_path}")

        return paths

    # ----------------------------------------------------------------
    # MAIN ENTRY POINT
    # ----------------------------------------------------------------

    def convert(
        self,
        runbook_name: str,
        runbook_text: str
    ) -> dict:
        """
        Main entry point. Convert a runbook into three artifacts.
        Returns dict with paths to all three saved files.
        """
        start = time.time()
        logger.info(f"Converting runbook: {runbook_name}")
        logger.info(
            f"Runbook length: {len(runbook_text)} characters, "
            f"{len(runbook_text.split(chr(10)))} lines"
        )

        # Generate all three artifacts
        # Note: done sequentially to avoid rate limits
        # In production with higher API limits: use ThreadPoolExecutor
        checklist = self.generate_checklist(runbook_name, runbook_text)
        script = self.generate_script(runbook_name, runbook_text)
        flowchart = self.generate_flowchart(runbook_name, runbook_text)

        # Save all artifacts
        paths = self.save_artifacts(
            runbook_name, checklist, script, flowchart
        )

        # Log metrics
        duration_ms = round((time.time() - start) * 1000)
        self.db.log_run(
            agent_name="RunbookConverter",
            ticket_number="",
            trigger_type="manual",
            input_summary=(
                f"Runbook: {runbook_name} | "
                f"Length: {len(runbook_text)} chars"
            ),
            output_summary=(
                f"3 artifacts generated: checklist, script, flowchart"
            ),
            success=True,
            duration_ms=duration_ms,
            minutes_saved=MINUTES_SAVED_PER_RUNBOOK,
        )

        logger.info(
            f"Conversion complete | "
            f"Duration: {duration_ms}ms | "
            f"3 artifacts saved to docs/runbooks/"
        )

        return {
            "runbook_name": runbook_name,
            "paths": paths,
            "checklist": checklist,
            "script": script,
            "flowchart": flowchart,
            "duration_ms": duration_ms,
        }

    # ----------------------------------------------------------------
    # TEST MODE
    # ----------------------------------------------------------------

    def run_test(self, runbook_choice: str = "oom") -> None:
        """
        Test conversion using built-in sample runbooks.

        runbook_choice: 'oom' or 'disk'
        """
        logger.info("=" * 60)
        logger.info("RUNBOOK CONVERTER — Test Run")
        logger.info("=" * 60)

        if runbook_choice == "disk":
            runbook_name = "Disk Space Recovery"
            runbook_text = SAMPLE_RUNBOOK_DISK
        else:
            runbook_name = "Payment Service OOM Recovery"
            runbook_text = SAMPLE_RUNBOOK_OOM

        logger.info(f"Converting: {runbook_name}")
        logger.info(
            f"Input: {len(runbook_text)} characters"
        )

        # Run the conversion
        result = self.convert(runbook_name, runbook_text)

        # Print results
        print("\n" + "=" * 60)
        print(f"CONVERSION COMPLETE: {runbook_name}")
        print("=" * 60)
        print(f"\n3 artifacts saved to docs/runbooks/:")
        for artifact_type, path in result["paths"].items():
            print(f"  {artifact_type:12}: {path}")

        print(f"\nDuration: {result['duration_ms']}ms")

        print("\n" + "-" * 60)
        print("CHECKLIST PREVIEW (first 30 lines):")
        print("-" * 60)
        lines = result["checklist"].split("\n")
        print("\n".join(lines[:30]))
        if len(lines) > 30:
            print(f"\n... and {len(lines) - 30} more lines")

        print("\n" + "-" * 60)
        print("FLOWCHART:")
        print("-" * 60)
        print(result["flowchart"])

        print("\n" + "-" * 60)
        print("AUTOMATION SCRIPT PREVIEW (first 30 lines):")
        print("-" * 60)
        script_lines = result["script"].split("\n")
        print("\n".join(script_lines[:30]))
        if len(script_lines) > 30:
            print(f"\n... and {len(script_lines) - 30} more lines")

        print("\n" + "=" * 60)
        print("Open the full files:")
        for artifact_type, path in result["paths"].items():
            print(f"  notepad {path}")
        print("=" * 60)

        logger.info("Test complete.")


# ----------------------------------------------------------------
# Direct execution
# ----------------------------------------------------------------
if __name__ == "__main__":
    import sys

    config = get_config()
    agent = RunbookConverter(config)

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        choice = sys.argv[2] if len(sys.argv) > 2 else "oom"
        agent.run_test(choice)

    elif len(sys.argv) > 1 and sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print(
                "Usage: python agents/runbook_converter.py "
                "--file path/to/runbook.txt"
            )
            sys.exit(1)
        filepath = Path(sys.argv[2])
        if not filepath.exists():
            print(f"File not found: {filepath}")
            sys.exit(1)
        runbook_text = filepath.read_text(encoding="utf-8")
        runbook_name = filepath.stem.replace("_", " ").title()
        result = agent.convert(runbook_name, runbook_text)
        print(f"\nConversion complete. Files saved to docs/runbooks/")
        for artifact_type, path in result["paths"].items():
            print(f"  {artifact_type}: {path}")

    elif len(sys.argv) > 1 and sys.argv[1] == "--text":
        if len(sys.argv) < 4:
            print(
                "Usage: python agents/runbook_converter.py "
                "--text \"Runbook Name\" \"runbook text here\""
            )
            sys.exit(1)
        runbook_name = sys.argv[2]
        runbook_text = sys.argv[3]
        result = agent.convert(runbook_name, runbook_text)
        print(f"\nConversion complete. Files saved to docs/runbooks/")
        for artifact_type, path in result["paths"].items():
            print(f"  {artifact_type}: {path}")

    else:
        agent.run_test()