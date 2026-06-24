# PROJECT MAP
**AI Automation Catalyst — Application Support Automation**
_Generated: 2026-06-24 | Author: Claude (Cowork)_

---

## Project Overview

A 6-month initiative to automate Application Support using AI agents powered by Anthropic Claude. The system reads ServiceNow tickets, classifies them, harvests logs, generates incident briefs, and tracks ROI — all with a human-in-the-loop safety model.

---

## Folder Structure

```
ai-automation/
├── agents/           AI agents (the core automation logic)
├── dashboard/        CLI/web dashboard for monitoring
├── data/             Mock, synthetic, and live metrics data
├── docs/             All project documentation
│   ├── adr/          Architecture Decision Records
│   └── reports/      Generated leadership reports
├── scheduler/        APScheduler-based polling jobs
├── scripts/          Shell scripts for setup, run, test
├── shared/           Shared library used by all agents
├── tests/            Unit and integration tests
├── tools/            Developer utility scripts
└── webhooks/         Flask webhook server for real-time triggers
```

---

## File-by-File Reference

### Root

| File | Status | What it does |
|------|--------|-------------|
| `README.md` | ✅ Complete | Project overview, quick-start, architecture diagram, agent descriptions, and deployment guide |
| `STEP_BY_STEP_GUIDE.md` | ✅ Complete | Full 6-month execution playbook — day-by-day setup, development, and demo instructions. _Copied to `docs/STEP_BY_STEP_GUIDE.md`; original kept at root_ |
| `requirements.txt` | ✅ Complete | Python dependencies: anthropic, flask, apscheduler, aiohttp, pytest, rich, python-dotenv, tabulate |
| `.env.example` | ✅ Complete | Template for environment variables — copy to `.env` and fill in API keys |
| `.env` | ✅ Present | Local secrets (not committed to git). Contains Anthropic key, ServiceNow credentials, feature flags |
| `.gitignore` | ✅ Complete | Excludes `.env`, `__pycache__`, `*.db`, and other non-committed files |

---

### `agents/` — AI Automation Agents

| File | Status | What it does |
|------|--------|-------------|
| `ticket_classifier.py` | ✅ Complete (16KB) | **Agent #1 — the primary automation target.** Reads unclassified ServiceNow tickets, calls Claude to determine category, priority (P1–P4), assignment team, and confidence score. Auto-applies classification if confidence ≥ 0.75; adds a comment for human review if below threshold. P1 tickets are **never** auto-applied — always require human confirmation. Logs every decision to `metrics.db`. |
| `log_harvester.py` | ⚠️ Empty stub | **Agent #2 — planned.** Intended to gather logs from application servers, correlate with tickets, and summarize relevant errors for analysts. Not yet implemented. |
| `sql_query_bot.py` | ⚠️ Empty stub | **Agent #3 — planned.** Intended to translate natural-language questions into SQL and query the metrics/support database. Not yet implemented. |
| `__init__.py` | ✅ Normal | Package marker (intentionally empty) |

---

### `shared/` — Shared Library

All agents import from this package. Centralising here means bug fixes apply everywhere.

| File | Status | What it does |
|------|--------|-------------|
| `config.py` | ✅ Complete | Central config loader. Reads `.env` / environment variables, validates required keys (`ANTHROPIC_API_KEY`, `SNOW_BASE_URL`), and returns a typed config dict used by every module. |
| `ai_client.py` | ✅ Complete | Thin wrapper around the Anthropic SDK. Sets the model, logs token usage for cost tracking, and provides a mockable interface for tests. If the SDK changes, only this file needs updating. |
| `snow_client.py` | ✅ Complete | ServiceNow REST API client. Supports **live mode** (real ServiceNow instance) and **synthetic mode** (loads from `data/synthetic/tickets.json`). Used by all agents that read or update tickets. |
| `data_sanitizer.py` | ✅ Complete | Strips PII from ticket data before any AI API call. Replaces emails, credit card numbers, SSNs, IP addresses, passwords, and API keys with safe placeholders (`[EMAIL]`, `[REDACTED]`, etc.). |
| `sanitizer.py` | ⚠️ Review needed | Appears to duplicate `data_sanitizer.py` — also strips PII using regex patterns. Likely an earlier version. **Recommend consolidating into one file.** |
| `metrics_db.py` | ✅ Complete | SQLite database layer. Tracks every agent run: action taken, duration, minutes saved, success/failure. Exposes weekly/monthly summary queries for leadership reports. |
| `metrics.py` | ✅ Complete | Higher-level metrics logging interface used by agents. Wraps `metrics_db.py` with convenience methods like `log_classification()` and `log_minutes_saved()`. |
| `logger.py` | ✅ Complete | Standardised logging setup. All agents call `get_logger(__name__)` to get a consistently formatted logger. |
| `__init__.py` | ✅ Normal | Package marker (intentionally empty) |

---

### `webhooks/` — Real-Time Trigger Server

| File | Status | What it does |
|------|--------|-------------|
| `main.py` | ⚠️ Empty stub | **Planned Flask webhook server.** Per ADR-002, webhooks are required for P1/P2 incident response (sub-90-second context delivery). Not yet implemented. Use ngrok in dev, Cloud Run in production. |
| `__init__.py` | ✅ Normal | Package marker (intentionally empty) |

---

### `scheduler/` — Polling Jobs

| File | Status | What it does |
|------|--------|-------------|
| `jobs.py` | ⚠️ Empty stub | **Planned APScheduler job definitions.** Per ADR-002, the Ticket Classifier and other batch agents run on a polling schedule (default: every 5 minutes). Not yet implemented. |
| `__init__.py` | ✅ Normal | Package marker (intentionally empty) |

---

### `dashboard/` — Monitoring UI

| File | Status | What it does |
|------|--------|-------------|
| `app.py` | ⚠️ Empty stub | **Planned dashboard.** Intended to provide a live view of agent activity, ticket throughput, and ROI metrics. Not yet implemented. |

---

### `tools/` — Developer Utilities

| File | Status | What it does |
|------|--------|-------------|
| `test_connections.py` | ✅ Complete | **Run this first.** Verifies all external connections before development: Anthropic API, ServiceNow (or synthetic mode), environment variables, SQLite database, and data files. |
| `seed_data.py` | ✅ Complete | Generates synthetic tickets and log data in `data/synthetic/`. Lets you run the full pipeline without a real ServiceNow instance — essential for demos and local testing. |
| `generate_report.py` | ✅ Complete | Queries `metrics.db` and prints a weekly leadership report: tickets classified, hours saved, agent success rates. Usage: `python tools/generate_report.py` or `--days 30`. |

---

### `scripts/` — Shell Scripts

| File | Status | What it does |
|------|--------|-------------|
| `setup.sh` | ✅ Complete | Full environment setup: creates virtualenv, installs requirements, copies `.env.example` to `.env` if missing, runs `seed_data.py`. |
| `run.sh` | ⚠️ Empty | **Planned.** Intended to start all agents and the scheduler in one command. Not yet implemented. |
| `test.sh` | ⚠️ Empty | **Planned.** Intended to run the full pytest suite. Not yet implemented. |

---

### `data/` — Data Files

| Path | Status | What it does |
|------|--------|-------------|
| `metrics.db` | ✅ Active | SQLite database (28KB) tracking all agent runs and ROI metrics |
| `mock/tickets.json` | ✅ Present | Mock ticket dataset for basic local testing |
| `mock/logs.json` | ✅ Present | Mock log entries for testing log harvester |
| `synthetic/tickets.json` | ✅ Present | Richer synthetic ticket dataset generated by `seed_data.py` |
| `synthetic/logs.json` | ✅ Present | Synthetic log entries matching the ticket scenarios |
| `logs/` | ⚠️ Empty directory | Intended for harvested application logs. Nothing written here yet — depends on `log_harvester.py` being implemented. |

---

### `tests/` — Test Suite

| Path | Status | What it does |
|------|--------|-------------|
| `unit/` | ⚠️ Empty | Directory exists, no test files written yet |
| `integration/` | ⚠️ Empty | Directory exists, no test files written yet |
| `fixtures/` | ⚠️ Empty | Directory exists, no fixture files yet |

---

### `docs/` — Documentation

| Path | Status | What it does |
|------|--------|-------------|
| `STEP_BY_STEP_GUIDE.md` | ✅ Complete | Full 6-month execution guide (copied from root) |
| `PROJECT_MAP.md` | ✅ This file | Summary of every file and its purpose |
| `adr/ADR-001-ai-provider.md` | ✅ Complete | Decision: Use Anthropic Claude (claude-sonnet-4-6). Rationale: best structured JSON output consistency vs GPT-4o and Gemini. Abstracted behind `shared/ai_client.py` for easy swap. |
| `adr/ADR-002-triggers.md` | ✅ Complete | Decision: Polling (every 5 min) for batch agents; webhooks for P1/P2 real-time response. Implementation: `scheduler/jobs.py` + `webhooks/main.py`. |
| `adr/ADR-003-deployment.md` | ✅ Complete | Decision: Docker + VM for development, Cloud Run (serverless) for production. Same container = migration takes < 1 day. |
| `adr/ADR-004-database.md` | ✅ Complete | Decision: SQLite for local dev, PostgreSQL for production. SQLAlchemy abstraction enables one-config migration. pgvector planned for Phase 2 semantic similarity search. |
| `reports/` | ✅ Created | Empty folder ready to receive reports from `tools/generate_report.py` |

---

## Issues & Flags

### ⚠️ Empty Stubs — Not Yet Implemented

These files exist as placeholders but contain no code. They are the next items to build:

| Priority | File | What's needed |
|----------|------|---------------|
| High | `agents/log_harvester.py` | Agent #2 — log correlation and summarisation |
| High | `agents/sql_query_bot.py` | Agent #3 — natural language to SQL |
| High | `scheduler/jobs.py` | APScheduler job definitions for polling |
| High | `webhooks/main.py` | Flask server for P1/P2 real-time triggers |
| Medium | `dashboard/app.py` | Live monitoring dashboard |
| Low | `scripts/run.sh` | One-command agent launcher |
| Low | `scripts/test.sh` | One-command test runner |

### ⚠️ Empty Directories — Waiting on Implementation

| Directory | Blocked by |
|-----------|-----------|
| `data/logs/` | `agents/log_harvester.py` not yet implemented |
| `tests/unit/` | No unit tests written yet |
| `tests/integration/` | No integration tests written yet |
| `tests/fixtures/` | No test fixtures created yet |

### ⚠️ Possible Duplicate — Review Recommended

| Issue | Detail |
|-------|--------|
| `shared/sanitizer.py` vs `shared/data_sanitizer.py` | Both modules strip PII using regex. `data_sanitizer.py` appears to be the canonical version referenced in ADR-001. `sanitizer.py` may be an earlier draft. Recommend reviewing and consolidating into one file. |

### ⚠️ Misnamed Directories — Shell Brace-Expansion Accident

The following directories were created at the root by a failed `mkdir` brace-expansion command. They are completely empty and have no purpose:

```
{agents,shared,data/
{agents,shared,data/mock,webhooks,scheduler,tests/
{agents,shared,data/mock,webhooks,scheduler,tests/fixtures,tools,docs/
{agents,shared,data/mock,webhooks,scheduler,tests/fixtures,tools,docs/adr,scripts}/
{agents,shared,data/{synthetic,logs},webhooks,scheduler,tests/
{agents,shared,data/{synthetic,logs},webhooks,scheduler,tests/{fixtures,unit,integration},tools,docs/
{agents,shared,data/{synthetic,logs},webhooks,scheduler,tests/{fixtures,unit,integration},tools,docs/adr,scripts,dashboard}/
```

**These are safe to delete** (`rm -rf` each one). They contain no files. They were not deleted during this audit pass per the "no deletions" policy — but they clutter `ls` output and should be removed at your earliest convenience.

---

## What's Working Right Now

```
python tools/test_connections.py   # verify setup
python tools/seed_data.py          # generate synthetic data
python agents/ticket_classifier.py # run Agent #1
python tools/generate_report.py    # view ROI report
```

---

_This file is auto-generated. Re-run the PROJECT_MAP audit to refresh after adding new files._
