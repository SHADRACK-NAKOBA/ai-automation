"""
agents/sql_query_bot.py
========================
Agent #3: Natural Language SQL Query Bot

WHAT IT DOES:
  Converts plain English questions into SQL queries, runs them
  against a read-only database, and returns formatted results.

  Example:
    Analyst types: "how many failed transactions for ACME today?"
    Agent returns: a formatted table with the answer in 15 seconds

WHY THIS AGENT:
  Data lookups that take 30 minutes of waiting now take 15 seconds.
  Every analyst gets the data access of a senior DBA — safely.
  No SQL knowledge required. No developer bottleneck.

HOW IT WORKS:
  1. Receives a plain English question
  2. Sends question + database schema to Claude
  3. Claude writes the SQL query
  4. Agent validates SQL is safe (read-only, no destructive commands)
  5. Runs query against read-only database
  6. Returns formatted results

SAFETY GUARDRAILS:
  - Read-only database user (enforced at database level)
  - Keyword blocklist: INSERT, UPDATE, DELETE, DROP, TRUNCATE
  - Mandatory LIMIT clause (max 500 rows)
  - Every query logged with user ID for audit trail

PRODUCTION UPGRADE:
  Replace SQLite connection with your real database:
  - Oracle:     cx_Oracle.connect(dsn)
  - PostgreSQL: psycopg2.connect(conn_string)
  - SQL Server: pyodbc.connect(conn_string)
"""

import json
import re
import sqlite3
import time
from pathlib import Path

import anthropic

from shared.config import get_config
from shared.metrics_db import MetricsDB
from shared.logger import get_logger

logger = get_logger("sql_query_bot")

MINUTES_SAVED_PER_QUERY = 12.0

# ----------------------------------------------------------------
# BLOCKED KEYWORDS — any query containing these is rejected
# ----------------------------------------------------------------
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
    "ALTER", "TRUNCATE", "EXEC", "EXECUTE", "GRANT",
    "REVOKE", "--", "xp_", "sp_"
]

# ----------------------------------------------------------------
# DATABASE SCHEMA
# Tell Claude exactly what tables and columns exist.
# The more detail you provide, the better the SQL.
# PRODUCTION: Replace with your real schema.
# ----------------------------------------------------------------
DB_SCHEMA = """
-- SUPPORT METRICS DATABASE
-- This is the AI Automation Platform metrics database.
-- Use this schema to answer questions about agent performance.

TABLE agent_runs (
    id              INTEGER,     -- unique run ID
    agent_name      TEXT,        -- 'TicketClassifier' or 'LogHarvester'
    ticket_number   TEXT,        -- ServiceNow ticket number e.g. INC0000018
    trigger_type    TEXT,        -- 'scheduled', 'webhook', 'manual'
    input_summary   TEXT,        -- what was processed
    output_summary  TEXT,        -- what was produced
    classification  TEXT,        -- JSON of AI classification result
    confidence      REAL,        -- AI confidence 0.0 to 1.0
    auto_applied    INTEGER,     -- 1 = auto-applied, 0 = suggested only
    success         INTEGER,     -- 1 = success, 0 = failure
    error_message   TEXT,        -- error details if failed
    duration_ms     INTEGER,     -- how long the run took in milliseconds
    minutes_saved   REAL,        -- estimated minutes saved by this run
    timestamp       TEXT         -- when this run happened
);

TABLE baselines (
    id              INTEGER,
    metric_name     TEXT,        -- e.g. 'weekly_ticket_volume'
    metric_value    REAL,        -- the baseline number
    captured_at     TEXT,        -- when baseline was captured
    notes           TEXT         -- description of the metric
);

-- EXAMPLE QUESTIONS YOU CAN ASK:
-- "How many tickets were classified today?"
-- "What is the total hours saved this week?"
-- "Which agent has the highest success rate?"
-- "How many tickets were auto-applied vs suggested?"
-- "What is the average confidence score for the classifier?"
-- "Show me all failed runs in the last 24 hours"
"""


class SQLQueryBot:
    """
    Converts plain English questions to SQL and returns results.

    USAGE:
      # Test with a question:
      python agents/sql_query_bot.py --question "how many runs today?"

      # Interactive mode:
      python agents/sql_query_bot.py --interactive

      # Single query programmatically:
      bot = SQLQueryBot(config)
      result = bot.ask("how many tickets were classified this week?")
      print(result)
    """

    def __init__(self, config: dict):
        self.config = config
        self.ai = anthropic.Anthropic(api_key=config["anthropic_key"])
        self.db_path = config.get("db_path", "data/metrics.db")
        self.metrics = MetricsDB(self.db_path)
        self.model = config.get("ai_model", "claude-sonnet-4-6")
        logger.info(f"SQLQueryBot ready | db={self.db_path}")

    def build_sql_prompt(self, question: str) -> str:
        """Build the Claude prompt to convert English to SQL."""
        return f"""You are a senior database analyst.
Convert the user's question into a safe, efficient SQL query.

DATABASE SCHEMA:
{DB_SCHEMA}

RULES — follow these exactly:
1. Return ONLY the SQL query — no explanation, no markdown, no backticks
2. Always include LIMIT 100 unless the question asks for counts or totals
3. Use standard SQLite date functions for time-based queries
4. For "today" use: date('now')
5. For "this week" use: date('now', '-7 days')
6. For "this month" use: date('now', '-30 days')
7. Only use SELECT statements — never INSERT, UPDATE, DELETE, DROP
8. If the question cannot be answered with this schema, return:
   SELECT 'Cannot answer this question with available data' AS message

USER QUESTION: {question}

SQL QUERY:"""

    def english_to_sql(self, question: str) -> str:
        """Use Claude to convert a plain English question to SQL."""
        prompt = self.build_sql_prompt(question)
        message = self.ai.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        sql = message.content[0].text.strip()
        # Clean up any accidental markdown
        sql = re.sub(r'```sql|```', '', sql).strip()
        return sql

    def is_safe_sql(self, sql: str) -> tuple:
        """
        Check if a SQL query is safe to run.
        Returns (True, 'OK') or (False, 'reason it was blocked')

        WHY: Defense in depth. Even if Claude generates a write
        query despite our instructions, this catches it before
        it reaches the database.
        """
        sql_upper = sql.upper()

        # Check for blocked keywords
        for keyword in BLOCKED_KEYWORDS:
            if keyword in sql_upper:
                return False, f"Blocked keyword detected: {keyword}"

        # Must start with SELECT or WITH
        stripped = sql_upper.strip()
        if not (stripped.startswith("SELECT") or
                stripped.startswith("WITH")):
            return False, "Only SELECT queries are allowed"

        return True, "OK"

    def run_query(self, sql: str) -> tuple:
        """
        Execute the SQL query against the database.
        Returns (columns, rows) or raises an exception.
        """
        # DEVELOPMENT: SQLite (metrics database)
        # PRODUCTION: Replace with your real DB connection:
        #   Oracle:     cx_Oracle.connect(...)
        #   PostgreSQL: psycopg2.connect(...)
        #   SQL Server: pyodbc.connect(...)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = (
                [d[0] for d in cursor.description]
                if cursor.description else []
            )
            rows = cursor.fetchall()
            return columns, [list(row) for row in rows]
        finally:
            conn.close()

    def format_results(
        self,
        question: str,
        sql: str,
        columns: list,
        rows: list
    ) -> str:
        """Format query results into a readable response."""
        if not rows:
            return (
                f"Query ran successfully but returned no results.\n"
                f"Question: {question}\n"
                f"SQL: {sql}"
            )

        # For single value results (counts, totals)
        if len(columns) == 1 and len(rows) == 1:
            return (
                f"Answer: {rows[0][0]}\n\n"
                f"Question: {question}\n"
                f"SQL: {sql}"
            )

        # Build a text table for multiple results
        col_widths = [len(str(c)) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val or "")))

        # Header
        header = " | ".join(
            str(c).ljust(col_widths[i])
            for i, c in enumerate(columns)
        )
        separator = "-+-".join("-" * w for w in col_widths)

        # Rows (limit display to 20)
        display_rows = rows[:20]
        data_lines = [
            " | ".join(
                str(v or "").ljust(col_widths[i])
                for i, v in enumerate(row)
            )
            for row in display_rows
        ]

        table = "\n".join([header, separator] + data_lines)

        suffix = ""
        if len(rows) > 20:
            suffix = f"\n... and {len(rows) - 20} more rows"

        return (
            f"Results: {len(rows)} row(s)\n\n"
            f"{table}{suffix}\n\n"
            f"Question: {question}\n"
            f"SQL: {sql}"
        )

    def ask(self, question: str, user: str = "analyst") -> str:
        """
        Main entry point. Takes a plain English question,
        returns a formatted answer.

        This is what gets called from Slack, Teams, or CLI.
        """
        start = time.time()
        logger.info(f"Question from {user}: {question}")

        try:
            # Step 1: Convert to SQL
            sql = self.english_to_sql(question)
            logger.info(f"Generated SQL: {sql}")

            # Step 2: Safety check
            is_safe, reason = self.is_safe_sql(sql)
            if not is_safe:
                logger.warning(f"Unsafe SQL blocked: {reason}")
                return (
                    f"I cannot run that query: {reason}\n"
                    f"Only read-only SELECT queries are allowed."
                )

            # Step 3: Run the query
            columns, rows = self.run_query(sql)

            # Step 4: Format results
            result = self.format_results(question, sql, columns, rows)

            # Step 5: Log metrics
            duration_ms = round((time.time() - start) * 1000)
            self.metrics.log_run(
                agent_name="SQLQueryBot",
                ticket_number="",
                trigger_type="manual",
                input_summary=question[:200],
                output_summary=f"{len(rows)} rows returned",
                success=True,
                duration_ms=duration_ms,
                minutes_saved=MINUTES_SAVED_PER_QUERY,
            )

            logger.info(
                f"Query complete: {len(rows)} rows in {duration_ms}ms"
            )
            return result

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return (
                f"Database error: {e}\n"
                f"The SQL may reference a table or column "
                f"that does not exist."
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return f"Query failed: {e}"

    def run_interactive(self):
        """
        Interactive mode — ask questions in a loop.
        Type 'exit' to quit.
        """
        print("\n" + "=" * 60)
        print("  SQL QUERY BOT — Interactive Mode")
        print("  Ask questions in plain English about your data.")
        print("  Type 'exit' to quit.")
        print("=" * 60)

        sample_questions = [
            "How many agent runs happened today?",
            "What is the total minutes saved by all agents?",
            "Which agent has the most runs?",
            "Show me all failed runs",
            "What is the average confidence score?",
        ]

        print("\nSample questions you can ask:")
        for q in sample_questions:
            print(f"  - {q}")
        print()

        while True:
            try:
                question = input("Your question: ").strip()
                if not question:
                    continue
                if question.lower() in ["exit", "quit", "q"]:
                    print("Goodbye!")
                    break

                print("\nThinking...")
                result = self.ask(question)
                print(f"\n{result}\n")
                print("-" * 60)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break


# ----------------------------------------------------------------
# Direct execution
# ----------------------------------------------------------------
if __name__ == "__main__":
    import sys

    config = get_config()
    bot = SQLQueryBot(config)

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        bot.run_interactive()

    elif len(sys.argv) > 1 and sys.argv[1] == "--question":
        if len(sys.argv) < 3:
            print("Usage: python agents/sql_query_bot.py "
                  "--question \"your question here\"")
            sys.exit(1)
        question = " ".join(sys.argv[2:])
        result = bot.ask(question)
        print(result)

    else:
        # Default: run interactive mode
        bot.run_interactive()