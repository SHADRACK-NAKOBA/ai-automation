"""
tools/test_connections.py
=========================
Run this FIRST before anything else.
Verifies every external connection works before you build on top of them.

USAGE:
  python tools/test_connections.py

WHAT IT TESTS:
  1. Anthropic Claude API  — can we call the AI?
  2. ServiceNow           — can we read tickets? (or synthetic mode)
  3. Environment          — are all required variables set?
  4. Database             — can we write metrics?
  5. Data files           — is synthetic data present?
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.logger import get_logger

logger = get_logger("test_connections")


def test_environment():
    """Check all required environment variables."""
    print("\n── Test 1: Environment Variables ────────────────────────")
    from shared.config import get_config
    try:
        config = get_config()
        print(f"  ✅ ANTHROPIC_API_KEY     present (ends in ...{config['anthropic_key'][-4:]})")
        print(f"  ✅ SNOW_BASE_URL         {config['snow_base']}")
        print(f"  ℹ️  DRY_RUN              {config['dry_run']}")
        print(f"  ℹ️  ENVIRONMENT          {config['environment']}")
        return config
    except EnvironmentError as e:
        print(f"  ❌ {e}")
        return None


def test_claude_api(config):
    """Verify the Anthropic API key works."""
    print("\n── Test 2: Claude API ───────────────────────────────────")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config["anthropic_key"])
        start = time.time()
        msg = client.messages.create(
            model=config.get("ai_model", "claude-sonnet-4-6"),
            max_tokens=20,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        ms = round((time.time() - start) * 1000)
        response = msg.content[0].text.strip()
        print(f"  ✅ Claude API working | Response: '{response}' | Latency: {ms}ms")
        return True
    except Exception as e:
        print(f"  ❌ Claude API failed: {e}")
        print("     → Check your ANTHROPIC_API_KEY in .env")
        return False


def test_servicenow(config):
    """Test ServiceNow connectivity (or synthetic mode)."""
    print("\n── Test 3: ServiceNow ───────────────────────────────────")
    try:
        from shared.snow_client import ServiceNowClient
        client = ServiceNowClient(config)
        ok = client.test_connection()

        if ok:
            tickets = client.get_unclassified_tickets(limit=3)
            mode = "SYNTHETIC" if client.use_synthetic else "LIVE"
            print(f"  ✅ ServiceNow [{mode}] | Sample tickets fetched: {len(tickets)}")
            if tickets:
                print(f"     First ticket: {tickets[0].get('number')} — {tickets[0].get('short_description', '')[:50]}")
        return ok
    except Exception as e:
        print(f"  ❌ ServiceNow error: {e}")
        return False


def test_database(config):
    """Test SQLite metrics database."""
    print("\n── Test 4: Metrics Database ─────────────────────────────")
    try:
        from shared.metrics_db import MetricsDB
        db = MetricsDB(config.get("db_path", "data/metrics.db"))
        db.log_run(
            agent_name="ConnectionTest",
            ticket_number="TEST001",
            trigger_type="manual",
            input_summary="Connection test run",
            output_summary="Test successful",
            success=True,
            minutes_saved=0,
        )
        summary = db.get_summary(days=1)
        print(f"  ✅ Database working | Path: {config.get('db_path', 'data/metrics.db')}")
        print(f"     Total runs today: {summary['total_runs']}")
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


def test_synthetic_data():
    """Verify synthetic data files exist."""
    print("\n── Test 5: Synthetic Data Files ─────────────────────────")
    path = Path("data/synthetic/tickets.json")
    if path.exists():
        import json
        with open(path) as f:
            tickets = json.load(f)
        print(f"  ✅ Synthetic tickets: {path} ({len(tickets)} tickets)")
        return True
    else:
        print(f"  ⚠️  Synthetic data not found at {path}")
        print("     → Run: python tools/seed_data.py")
        return False


def test_data_sanitizer():
    """Test the PII sanitizer."""
    print("\n── Test 6: Data Sanitizer ───────────────────────────────")
    from shared.data_sanitizer import sanitize_text
    test_input = "User john@example.com called from 192.168.1.1 with password=secret123"
    result = sanitize_text(test_input)
    has_email = "@" not in result
    has_ip = "192.168" not in result
    has_password = "secret123" not in result
    if has_email and has_ip and has_password:
        print(f"  ✅ Sanitizer working")
        print(f"     Input:  {test_input}")
        print(f"     Output: {result}")
        return True
    else:
        print(f"  ❌ Sanitizer not removing PII correctly")
        print(f"     Output: {result}")
        return False


def main():
    print("=" * 60)
    print("  AI AUTOMATION — Connection Tests")
    print("=" * 60)

    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    from dotenv import load_dotenv
    load_dotenv()

    results = {}

    config = test_environment()
    results["environment"] = config is not None

    if config:
        results["claude_api"] = test_claude_api(config)
        results["servicenow"] = test_servicenow(config)
        results["database"] = test_database(config)
    else:
        results["claude_api"] = False
        results["servicenow"] = False
        results["database"] = False

    results["synthetic_data"] = test_synthetic_data()
    results["sanitizer"] = test_data_sanitizer()

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    all_pass = True
    for test, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon}  {test}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  ✅ All tests passed. You're ready to run agents.")
        print("  Next: python agents/ticket_classifier.py")
    else:
        print("  ❌ Some tests failed. Fix the issues above before proceeding.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
