"""
tools/generate_report.py
========================
Generate a weekly leadership report from the metrics database.

USAGE:
  python tools/generate_report.py
  python tools/generate_report.py --days 30

This is the report you send to leadership every Friday.
It shows exactly what the agents did and how many hours were saved.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv()

from shared.metrics_db import MetricsDB
from shared.config import get_config


def generate_report(days: int = 7):
    config = get_config()
    db = MetricsDB(config.get("db_path", "data/metrics.db"))

    summary = db.get_summary(days=days)
    cumulative_hours = db.get_cumulative_hours()
    baselines = db.get_baselines()

    width = 65
    line = "─" * width

    print()
    print("=" * width)
    print(f"  AI AUTOMATION PLATFORM — {days}-Day Report")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * width)

    # Headline numbers
    print(f"\n  HEADLINE METRICS (Last {days} days)")
    print(f"  {line}")
    print(f"  Total agent runs:        {summary['total_runs']:>8,}")
    print(f"  Hours saved this period: {summary['total_hours_saved']:>8.1f} hrs")
    print(f"  Hours saved all-time:    {cumulative_hours:>8.1f} hrs")
    if summary['total_hours_saved'] > 0:
        value_at_50 = summary['total_hours_saved'] * 50
        print(f"  Est. value (@$50/hr):   ${value_at_50:>8,.0f}")

    # By agent breakdown
    if summary["by_agent"]:
        print(f"\n  BY AGENT")
        print(f"  {line}")
        header = f"  {'Agent':<30} {'Runs':>6} {'Success':>8} {'Min Saved':>10} {'Conf':>6}"
        print(header)
        print(f"  {line}")
        for agent in summary["by_agent"]:
            runs = agent["total_runs"] or 0
            success = agent["successful"] or 0
            mins = agent["total_minutes_saved"] or 0
            conf = agent["avg_confidence"] or 0
            rate = f"{success/max(runs,1):.0%}"
            print(
                f"  {agent['agent_name']:<30} {runs:>6,} {rate:>8} "
                f"{mins:>10.0f} {conf:>5.0%}"
            )

    # Baselines comparison
    if baselines:
        print(f"\n  BASELINE COMPARISON")
        print(f"  {line}")
        print(f"  {'Metric':<35} {'Baseline':>12}")
        print(f"  {line}")
        for b in baselines:
            print(f"  {b['metric_name']:<35} {b['metric_value']:>12.1f}")
        print(f"\n  (Compare current metrics to baseline to show improvement)")

    # What's next
    print(f"\n  NOTES FOR LEADERSHIP UPDATE")
    print(f"  {line}")
    print(f"  • Agents running in DRY_RUN=false (live) mode")
    print(f"  • All P1 tickets still require human confirmation")
    print(f"  • Classification confidence threshold: 75%")
    print(f"  • Next agent being built: Log Harvester (Week 4)")
    print()
    print("=" * width)
    print()


if __name__ == "__main__":
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])
    generate_report(days)
