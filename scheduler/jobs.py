"""
scheduler/jobs.py
=================
Production scheduler that runs all agents automatically.

WHAT IT DOES:
  Runs the Ticket Classifier every 5 minutes and the Log Harvester
  every 2 minutes without any human intervention.

HOW TO START IT:
  python scheduler/jobs.py

HOW TO STOP IT:
  Press Ctrl+C in the terminal

HOW TO RUN IN BACKGROUND (so terminal stays free):
  Windows:  start /B python scheduler/jobs.py
  Mac/Linux: nohup python scheduler/jobs.py &

PRODUCTION DEPLOYMENT:
  On a company server: set up as a Windows Service or Linux systemd
  service so it starts automatically on reboot.
"""

import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from shared.config import get_config
from shared.logger import get_logger
from shared.metrics_db import MetricsDB

logger = get_logger("scheduler")


# ----------------------------------------------------------------
# JOB FUNCTIONS
# ----------------------------------------------------------------

def run_ticket_classifier():
    """
    Job 1: Runs every 5 minutes.
    Fetches all unclassified tickets and classifies them with AI.
    """
    from agents.ticket_classifier import TicketClassifier
    try:
        logger.info("--- Classifier job starting ---")
        config = get_config()
        agent = TicketClassifier(config)
        stats = agent.run()
        logger.info(f"--- Classifier job complete: {stats} ---")
    except Exception as e:
        logger.error(f"Classifier job FAILED: {e}")


def run_log_harvester():
    """
    Job 2: Runs every 2 minutes.
    Finds new P1/P2 tickets without a Log Brief and processes them.
    """
    from agents.log_harvester import LogHarvester
    from shared.snow_client import ServiceNowClient
    try:
        logger.info("--- Log Harvester job starting ---")
        config = get_config()
        snow = ServiceNowClient(config)
        agent = LogHarvester(config)

        # Find P1/P2 tickets that do not yet have a Log Brief
        tickets = snow.get_incidents(
            query=(
                "priority=1^ORpriority=2"
                "^state!=6^state!=7"
                "^work_notesNOT LIKELog Brief"
            ),
            limit=10
        )

        if not tickets:
            logger.info("No P1/P2 tickets need Log Briefs right now")
            return

        logger.info(f"Found {len(tickets)} P1/P2 tickets to process")
        success_count = 0
        for ticket in tickets:
            ok = agent.process_incident(ticket["sys_id"])
            if ok:
                success_count += 1

        logger.info(
            f"--- Log Harvester complete: "
            f"{success_count}/{len(tickets)} successful ---"
        )
    except Exception as e:
        logger.error(f"Log Harvester job FAILED: {e}")


def run_weekly_report():
    """
    Job 3: Runs every Monday at 7am.
    Generates the weekly metrics report, saves it, and emails it
    to your manager automatically.
    """
    from pathlib import Path
    from shared.email_sender import EmailSender

    try:
        logger.info("--- Weekly report job starting ---")
        config = get_config()
        db = MetricsDB(config.get("db_path", "data/metrics.db"))
        summary = db.get_summary(days=7)
        cumulative = db.get_cumulative_hours()

        hours_saved = summary.get("total_hours_saved", 0)
        total_runs  = summary.get("total_runs", 0)

        # Build report content
        report_lines = [
            f"# AI Automation Weekly Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## Headline Metrics",
            f"- Total runs this week: {total_runs}",
            f"- Hours saved this week: {hours_saved:.1f}h",
            f"- Hours saved all-time: {cumulative:.1f}h",
            f"- Est. value (@$50/hr): ${hours_saved * 50:,.0f}",
            f"",
            f"## By Agent",
        ]
        for agent in summary.get("by_agent", []):
            mins = agent.get("total_minutes_saved", 0) or 0
            report_lines.append(
                f"- {agent['agent_name']}: "
                f"{agent.get('total_runs', 0)} runs, "
                f"{mins:.0f} minutes saved"
            )
        report_lines += [
            f"",
            f"## Baseline Comparison",
            f"- Weekly ticket volume baseline: 380",
            f"- Avg P1 MTTR baseline: 4.2 hours",
            f"- SLA compliance baseline: 74%",
            f"",
            f"---",
            f"*Generated automatically every Monday at 7am*",
        ]

        # Save report to file
        reports_dir = Path("docs/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"weekly_report_"
            f"{datetime.now().strftime('%Y_%m_%d')}.md"
        )
        filepath = reports_dir / filename
        filepath.write_text("\n".join(report_lines))
        logger.info(f"Report saved: {filepath}")

        # Send email to manager
        sender = EmailSender(config)
        email_sent = sender.send_weekly_report(
            report_content="\n".join(report_lines),
            hours_saved=hours_saved,
            total_runs=total_runs,
            cumulative_hours=cumulative,
            attachment_path=str(filepath)
        )

        if email_sent:
            logger.info("Weekly report emailed to manager successfully")
        else:
            logger.warning(
                "Weekly report saved but email not sent — "
                "check EMAIL settings in .env"
            )

        logger.info("--- Weekly report job complete ---")

    except Exception as e:
        logger.error(f"Weekly report job FAILED: {e}")


def health_check():
    """
    Job 4: Runs every 15 minutes.
    Verifies all external connections are healthy.
    Logs a warning if anything is down.
    """
    import requests
    from shared.snow_client import ServiceNowClient
    try:
        config = get_config()

        # Check ServiceNow
        snow = ServiceNowClient(config)
        snow_ok = snow.test_connection()

        # Check Claude API
        import anthropic
        try:
            client = anthropic.Anthropic(api_key=config["anthropic_key"])
            client.messages.create(
                model=config.get("ai_model", "claude-sonnet-4-6"),
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}]
            )
            claude_ok = True
        except Exception:
            claude_ok = False

        if snow_ok and claude_ok:
            logger.info(
                f"Health check PASSED | "
                f"ServiceNow: OK | Claude API: OK"
            )
        else:
            logger.warning(
                f"Health check WARNING | "
                f"ServiceNow: {'OK' if snow_ok else 'DOWN'} | "
                f"Claude API: {'OK' if claude_ok else 'DOWN'}"
            )

    except Exception as e:
        logger.error(f"Health check FAILED: {e}")


# ----------------------------------------------------------------
# EVENT LISTENER — logs every job success and failure
# ----------------------------------------------------------------

def job_listener(event):
    """Called after every job runs — logs success or failure."""
    if event.exception:
        logger.error(
            f"JOB FAILED: {event.job_id} | "
            f"Error: {event.exception}"
        )
    else:
        logger.info(f"JOB COMPLETED: {event.job_id}")


# ----------------------------------------------------------------
# MAIN SCHEDULER SETUP
# ----------------------------------------------------------------

def create_scheduler() -> BlockingScheduler:
    """
    Create and configure the scheduler with all jobs.

    WHY BLOCKING SCHEDULER:
      BlockingScheduler holds the terminal open and keeps running
      until you press Ctrl+C. This is correct for a process you
      want to run continuously in the foreground or as a service.
    """
    scheduler = BlockingScheduler()

    # Add event listener for logging
    scheduler.add_listener(
        job_listener,
        EVENT_JOB_ERROR | EVENT_JOB_EXECUTED
    )

    # Job 1: Ticket Classifier — every 5 minutes
    scheduler.add_job(
        func=run_ticket_classifier,
        trigger="interval",
        minutes=5,
        id="ticket_classifier",
        name="Ticket Auto-Classifier",
        max_instances=1,       # Never run two at the same time
        coalesce=True,         # Skip missed runs if system was down
        misfire_grace_time=60  # Allow 60 seconds late start
    )

    # Job 2: Log Harvester — every 2 minutes
    scheduler.add_job(
        func=run_log_harvester,
        trigger="interval",
        minutes=2,
        id="log_harvester",
        name="Log Harvester",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60
    )

    # Job 3: Weekly Report — every Monday at 7am
    scheduler.add_job(
        func=run_weekly_report,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        id="weekly_report",
        name="Weekly Report Generator"
    )

    # Job 4: Health Check — every 15 minutes
    scheduler.add_job(
        func=health_check,
        trigger="interval",
        minutes=15,
        id="health_check",
        name="System Health Check",
        max_instances=1
    )

    return scheduler


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  AI AUTOMATION SCHEDULER — Starting")
    logger.info("=" * 60)
    logger.info("  Jobs configured:")
    logger.info("  - Ticket Classifier : every 5 minutes")
    logger.info("  - Log Harvester     : every 2 minutes")
    logger.info("  - Weekly Report     : every Monday 7am")
    logger.info("  - Health Check      : every 15 minutes")
    logger.info("  Press Ctrl+C to stop")
    logger.info("=" * 60)

    # Run the first classifier immediately on startup
    # so you do not wait 5 minutes for the first run
    logger.info("Running initial classifier on startup...")
    run_ticket_classifier()

    # Start the scheduler
    scheduler = create_scheduler()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (Ctrl+C)")
        scheduler.shutdown()
        logger.info("Shutdown complete")