"""
shared/metrics_db.py
====================
SQLite database that tracks every agent run.

WHY THIS EXISTS:
  Without tracking, you can't prove ROI.
  Every classification, every log harvest, every healing action
  gets logged here with: what happened, how long it took,
  how many minutes it saved.

  This is what you show leadership on Friday.

TABLES:
  agent_runs    - every individual agent execution
  baselines     - your week-1 'before' metrics

HOW TO VIEW YOUR DATA:
  python tools/generate_report.py
  -- or --
  sqlite3 data/metrics.db "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT 20;"
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from shared.logger import get_logger

logger = get_logger("metrics_db")


def get_connection(db_path: str = "data/metrics.db") -> sqlite3.Connection:
    """Get a database connection, creating the file if needed."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Allows dict-style access
    return conn


def init_db(db_path: str = "data/metrics.db"):
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name          TEXT    NOT NULL,
            ticket_number       TEXT,
            trigger_type        TEXT,   -- 'scheduled', 'webhook', 'manual'
            input_summary       TEXT,
            output_summary      TEXT,
            classification      TEXT,   -- JSON of the result
            confidence          REAL,
            auto_applied        INTEGER DEFAULT 0,  -- 1=auto, 0=flagged
            success             INTEGER DEFAULT 1,  -- 1=ok, 0=error
            error_message       TEXT,
            duration_ms         INTEGER,
            minutes_saved       REAL    DEFAULT 0,
            timestamp           TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS baselines (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name         TEXT    UNIQUE,
            metric_value        REAL,
            captured_at         TEXT    DEFAULT (datetime('now')),
            notes               TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_runs_agent
            ON agent_runs(agent_name);
        CREATE INDEX IF NOT EXISTS idx_runs_timestamp
            ON agent_runs(timestamp);
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")


class MetricsDB:
    def __init__(self, db_path: str = "data/metrics.db"):
        init_db(db_path)
        self.db_path = db_path

    def log_run(
        self,
        agent_name: str,
        ticket_number: str = "",
        trigger_type: str = "scheduled",
        input_summary: str = "",
        output_summary: str = "",
        classification: dict = None,
        confidence: float = 0.0,
        auto_applied: bool = False,
        success: bool = True,
        error_message: str = "",
        duration_ms: int = 0,
        minutes_saved: float = 0.0,
    ):
        """Log a single agent run to the database."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                INSERT INTO agent_runs
                (agent_name, ticket_number, trigger_type, input_summary,
                 output_summary, classification, confidence, auto_applied,
                 success, error_message, duration_ms, minutes_saved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_name,
                ticket_number,
                trigger_type,
                input_summary[:500] if input_summary else "",
                output_summary[:500] if output_summary else "",
                json.dumps(classification) if classification else None,
                confidence,
                int(auto_applied),
                int(success),
                error_message[:500] if error_message else "",
                duration_ms,
                minutes_saved,
            ))
            conn.commit()
        finally:
            conn.close()

    def get_summary(self, days: int = 7) -> dict:
        """Get a summary of agent activity for the last N days."""
        conn = get_connection(self.db_path)
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        try:
            rows = conn.execute("""
                SELECT
                    agent_name,
                    COUNT(*)                    AS total_runs,
                    SUM(success)                AS successful,
                    SUM(auto_applied)           AS auto_applied,
                    SUM(minutes_saved)          AS total_minutes_saved,
                    AVG(confidence)             AS avg_confidence,
                    AVG(duration_ms)            AS avg_duration_ms
                FROM agent_runs
                WHERE timestamp > ?
                GROUP BY agent_name
                ORDER BY total_minutes_saved DESC
            """, (since,)).fetchall()

            agents = [dict(r) for r in rows]
            total_minutes = sum(a["total_minutes_saved"] or 0 for a in agents)

            return {
                "period_days": days,
                "by_agent": agents,
                "total_runs": sum(a["total_runs"] for a in agents),
                "total_minutes_saved": total_minutes,
                "total_hours_saved": round(total_minutes / 60, 2),
            }
        finally:
            conn.close()

    def get_cumulative_hours(self) -> float:
        """Total hours saved since the project started."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT SUM(minutes_saved)/60.0 FROM agent_runs WHERE success=1"
            ).fetchone()
            return round(row[0] or 0.0, 2)
        finally:
            conn.close()

    def set_baseline(self, metric_name: str, value: float, notes: str = ""):
        """Record a 'before' baseline metric."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                INSERT INTO baselines (metric_name, metric_value, notes)
                VALUES (?, ?, ?)
                ON CONFLICT(metric_name) DO UPDATE SET
                    metric_value = excluded.metric_value,
                    notes = excluded.notes,
                    captured_at = datetime('now')
            """, (metric_name, value, notes))
            conn.commit()
            logger.info(f"Baseline set: {metric_name} = {value}")
        finally:
            conn.close()

    def get_baselines(self) -> list:
        """Get all baseline metrics."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM baselines ORDER BY metric_name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
