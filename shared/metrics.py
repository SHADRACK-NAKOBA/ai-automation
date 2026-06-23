"""
shared/metrics.py
────────────────────────────────────────────────────────────
Logs every agent action to SQLite for reporting and ROI tracking.

WHY track metrics from day 1:
  "We automated things" is anecdotal. "We returned 47 hours
  to the team this week" is a business case for contract renewal.
  Every agent call logs: what it did, how long, how many
  minutes it saved, and whether it succeeded.

WHY SQLite (not PostgreSQL) for metrics:
  Metrics need to work in local dev with zero infrastructure.
  SQLite is a single file, always available, and handles the
  write volume of agent metrics easily. If you need multi-node
  metrics later, this is a one-function swap.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "metrics.db"


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name       TEXT    NOT NULL,
                ticket_number    TEXT,
                action_taken     TEXT,
                result_summary   TEXT,
                success          INTEGER NOT NULL DEFAULT 0,
                dry_run          INTEGER NOT NULL DEFAULT 0,
                minutes_saved    REAL    DEFAULT 0,
                duration_ms      INTEGER,
                error_message    TEXT,
                timestamp        TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date             TEXT PRIMARY KEY,
                total_runs       INTEGER DEFAULT 0,
                successful_runs  INTEGER DEFAULT 0,
                total_minutes_saved REAL DEFAULT 0
            );
        """)


def log_run(
    agent_name: str,
    ticket_number: str = "",
    action_taken: str = "",
    result_summary: str = "",
    success: bool = True,
    dry_run: bool = False,
    minutes_saved: float = 0,
    duration_ms: int = 0,
    error_message: str = ""
):
    """Log one agent execution."""
    init_db()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO agent_runs
                (agent_name, ticket_number, action_taken, result_summary,
                 success, dry_run, minutes_saved, duration_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_name, ticket_number, action_taken[:500],
            result_summary[:500], int(success), int(dry_run),
            minutes_saved, duration_ms, error_message[:500]
        ))

        today = datetime.utcnow().strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO daily_stats (date, total_runs, successful_runs, total_minutes_saved)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_runs = total_runs + 1,
                successful_runs = successful_runs + ?,
                total_minutes_saved = total_minutes_saved + ?
        """, (today, int(success), minutes_saved, int(success), minutes_saved))


def get_summary(days: int = 7) -> dict:
    """Get metrics for the last N days."""
    init_db()
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    with get_db() as conn:
        by_agent = conn.execute("""
            SELECT
                agent_name,
                COUNT(*) as runs,
                SUM(success) as successes,
                SUM(CASE WHEN dry_run = 0 THEN minutes_saved ELSE 0 END) as minutes_saved,
                AVG(duration_ms) as avg_ms
            FROM agent_runs
            WHERE date(timestamp) >= ?
            GROUP BY agent_name
            ORDER BY minutes_saved DESC
        """, (since,)).fetchall()

        totals = conn.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(success) as total_success,
                SUM(CASE WHEN dry_run = 0 THEN minutes_saved ELSE 0 END) as total_minutes
            FROM agent_runs
            WHERE date(timestamp) >= ?
        """, (since,)).fetchone()

        all_time = conn.execute("""
            SELECT SUM(CASE WHEN dry_run = 0 THEN minutes_saved ELSE 0 END) as total_minutes
            FROM agent_runs WHERE success = 1
        """).fetchone()

    return {
        "period_days": days,
        "by_agent": [dict(row) for row in by_agent],
        "total_runs": totals["total_runs"] or 0,
        "total_success": totals["total_success"] or 0,
        "total_hours_this_period": round((totals["total_minutes"] or 0) / 60, 1),
        "total_hours_all_time": round((all_time["total_minutes"] or 0) / 60, 1),
    }
