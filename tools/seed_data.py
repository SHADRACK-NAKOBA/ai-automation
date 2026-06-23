"""
tools/seed_data.py
==================
Creates all synthetic data files needed to run the project
without a real ServiceNow instance.

WHY SYNTHETIC DATA:
  You need to prove to yourself (and your manager) that the agents
  work BEFORE you get access to real data.
  Synthetic data lets you:
  - Run the full pipeline end-to-end
  - Test accuracy against known expected values
  - Demo to stakeholders without touching production
  - Iterate on prompts without consuming real API quota

USAGE:
  python tools/seed_data.py
"""

import json
from pathlib import Path

# This is already written to data/synthetic/tickets.json by setup
# This script just verifies it and adds any missing synthetic data

def verify_tickets():
    path = Path("data/synthetic/tickets.json")
    if not path.exists():
        print(f"  ❌ Missing: {path}")
        print("     tickets.json should have been created during project setup.")
        return False
    with open(path) as f:
        tickets = json.load(f)
    print(f"  ✅ Synthetic tickets: {len(tickets)} tickets at {path}")
    return True


def create_synthetic_logs():
    """Create sample log data for testing the Log Harvester agent."""
    path = Path("data/synthetic/logs.json")
    path.parent.mkdir(parents=True, exist_ok=True)

    logs = [
        {
            "service": "payment-service-prod",
            "timestamp": "2025-06-10T14:30:01Z",
            "level": "ERROR",
            "message": "java.lang.OutOfMemoryError: Java heap space",
            "thread": "pool-1-thread-42",
            "class": "com.company.payment.ProcessorService"
        },
        {
            "service": "payment-service-prod",
            "timestamp": "2025-06-10T14:30:02Z",
            "level": "ERROR",
            "message": "GC overhead limit exceeded — heap at 97%",
            "thread": "GC-thread-1",
            "class": "java.lang.Runtime"
        },
        {
            "service": "payment-service-prod",
            "timestamp": "2025-06-10T14:30:03Z",
            "level": "FATAL",
            "message": "Application shutting down due to memory error",
            "thread": "main",
            "class": "com.company.payment.Application"
        },
        {
            "service": "auth-service-prod",
            "timestamp": "2025-06-10T09:14:55Z",
            "level": "ERROR",
            "message": "java.lang.NullPointerException at AuthService.validateToken(AuthService.java:142)",
            "thread": "http-nio-8080-exec-7",
            "class": "com.company.auth.AuthService"
        },
        {
            "service": "auth-service-prod",
            "timestamp": "2025-06-10T09:15:00Z",
            "level": "ERROR",
            "message": "Token validation failed: token object is null",
            "thread": "http-nio-8080-exec-8",
            "class": "com.company.auth.TokenValidator"
        },
        {
            "service": "prod-oracle-db-01",
            "timestamp": "2025-06-10T14:32:05Z",
            "level": "ERROR",
            "message": "ORA-12541: TNS:no listener",
            "thread": "connection-pool-1",
            "class": "oracle.jdbc.driver.OracleDriver"
        },
    ]

    with open(path, "w") as f:
        json.dump(logs, f, indent=2)
    print(f"  ✅ Synthetic logs: {len(logs)} log entries at {path}")


def create_synthetic_metrics_baseline():
    """Pre-populate baseline metrics for demo purposes."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from shared.metrics_db import MetricsDB
        db = MetricsDB("data/metrics.db")

        baselines = [
            ("weekly_ticket_volume", 380, "Avg tickets/week before automation"),
            ("avg_mttr_p1_hours", 4.2, "Average hours to resolve P1 before automation"),
            ("avg_mttr_p2_hours", 18.5, "Average hours to resolve P2 before automation"),
            ("sla_compliance_pct", 74.0, "% tickets resolved within SLA before automation"),
            ("manual_classification_minutes", 4.0, "Minutes to manually classify one ticket"),
            ("manual_log_hunt_minutes", 18.0, "Minutes to manually gather logs for P1/P2"),
        ]

        for name, value, notes in baselines:
            db.set_baseline(name, value, notes)

        print(f"  ✅ Baseline metrics seeded: {len(baselines)} metrics")
    except Exception as e:
        print(f"  ⚠️  Could not seed baselines: {e}")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)

    print("\n  Seeding synthetic data...")
    verify_tickets()
    create_synthetic_logs()
    create_synthetic_metrics_baseline()
    print("  Done.\n")
