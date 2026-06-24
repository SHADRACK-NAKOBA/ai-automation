# AI Automation Platform
### Application Support Automation — Agent Library

An end-to-end AI automation platform for IT Application Support teams.
Eliminates manual triage, log analysis, and repetitive support tasks using AI agents.

---

## What This Does

| Agent | What It Automates | Time Saved/Run | Status |
|-------|-------------------|----------------|--------|
| Ticket Classifier | Auto-categorizes and prioritizes incoming tickets | ~4 min | ✅ Built |
| Log Harvester | Pulls and summarizes logs when incidents fire | ~18 min | 🔧 In Progress |
| SQL Query Bot | Answers data questions in plain English via Slack | ~12 min | 📋 Planned |
| Self-Healing Agent | Executes pre-approved fix scripts on known failures | ~25 min | 📋 Planned |
| RCA Generator | Drafts post-incident reviews from ticket history | ~40 min | 📋 Planned |
| Incident Brief | Delivers 90-second war-room context on P1s | ~22 min | 📋 Planned |
| Runbook Converter | Converts manual runbooks → automated workflows | ~60 min | 📋 Planned |

---

## Quick Start

### Step 1 — Prerequisites
- Python 3.9+
- Git
- An [Anthropic API key](https://console.anthropic.com)
- A ServiceNow instance (or use built-in synthetic data for local testing)

### Step 2 — Clone and Setup
```bash
git clone https://github.com/YOUR_USERNAME/ai-automation.git
cd ai-automation
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Step 3 — Configure
```bash
# Edit .env with your actual values
nano .env   # or: code .env / open -e .env
```

Minimum required for local testing with synthetic data:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
SNOW_BASE_URL=https://placeholder.service-now.com
DRY_RUN=true
```

For real ServiceNow (PDI or production):
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
SNOW_BASE_URL=https://YOUR_INSTANCE.service-now.com
SNOW_USERNAME=admin
SNOW_PASSWORD=your-pdi-password
DRY_RUN=true    # Keep true until accuracy test passes
```

### Step 4 — Test Connections
```bash
source venv/bin/activate
python tools/test_connections.py
```
All 6 tests should pass before you run any agent.

### Step 5 — Run Accuracy Test (ALWAYS before going live)
```bash
python agents/ticket_classifier.py --accuracy-test
```
Target: >80% category accuracy, >85% priority accuracy.
If below target, tune the prompt in `agents/ticket_classifier.py`.

### Step 6 — Run Agent (Dry Run First)
```bash
# Dry run — reads tickets, classifies, DOES NOT write to ServiceNow
python agents/ticket_classifier.py

# Review the output. When confident:
# Set DRY_RUN=false in .env
# Then run again to go live
```

### Step 7 — View Your Metrics
```bash
python tools/generate_report.py
```

---

## Project Structure

```
ai-automation/
├── agents/                  # One file per AI agent
│   ├── ticket_classifier.py # Agent #1 — auto-classify tickets
│   ├── log_harvester.py     # Agent #2 — pull and summarize logs
│   └── sql_query_bot.py     # Agent #3 — natural language DB queries
├── shared/                  # Shared modules used by all agents
│   ├── config.py            # Environment variable loader
│   ├── snow_client.py       # ServiceNow API client (+ synthetic mode)
│   ├── data_sanitizer.py    # PII removal before AI calls
│   ├── metrics_db.py        # SQLite tracking of all agent runs
│   └── logger.py            # Centralized logging
├── data/
│   ├── synthetic/           # Sample data for local testing (no SNOW needed)
│   │   ├── tickets.json     # 12 realistic incident tickets
│   │   └── logs.json        # Sample application logs
│   └── metrics.db           # Auto-created SQLite database (git-ignored)
├── docs/
│   └── adr/                 # Architecture Decision Records
│       ├── ADR-001-ai-provider.md
│       ├── ADR-002-triggers.md
│       ├── ADR-003-deployment.md
│       └── ADR-004-database.md
├── tools/
│   ├── test_connections.py  # Run first — verifies all connections
│   ├── seed_data.py         # Creates synthetic data files
│   └── generate_report.py   # Weekly leadership report
├── webhooks/                # Flask webhook receivers (Phase 2)
├── scheduler/               # APScheduler for polling agents
├── tests/                   # Unit and integration tests
├── scripts/
│   ├── setup.sh             # One-time environment setup
│   ├── run.sh               # Run all agents
│   └── test.sh              # Run test suite
├── .env.example             # Template — copy to .env
├── .env                     # Your secrets — NEVER committed
├── .gitignore
└── requirements.txt
```

---

## Architecture Decisions

See `docs/adr/` for detailed reasoning behind every major decision.

| Decision | Choice | Why |
|----------|--------|-----|
| AI Provider | Anthropic Claude | Best instruction-following for structured JSON output |
| Trigger method | Polling + Webhooks | Polling for batch, webhooks for real-time P1/P2 |
| Deployment | Docker → Cloud Run | Dev ergonomics first, serverless migration later |
| Database | SQLite → PostgreSQL | SQLite for local dev, Postgres for production |
| Auth method | Basic Auth (dev), Token (prod) | Simplest first, upgrade path ready |

---

## Development Workflow

### Always develop in this order:
1. **Write the function** — implement the logic
2. **Test with synthetic data** — run against `data/synthetic/tickets.json`
3. **Run accuracy test** — `python agents/ticket_classifier.py --accuracy-test`
4. **Connect to PDI (dev ServiceNow)** — set `SNOW_USERNAME` in `.env`
5. **Run in dry_run=true** — reads from real SNOW, logs what would happen
6. **Get analyst review** — show dry run results to a team member
7. **Enable dry_run=false** — go live on low-priority tickets first (P3/P4)
8. **Monitor for 48 hours** — check classifications are correct
9. **Enable full scope** — remove P3/P4 restriction

### Never skip step 3 or 6.

---

## Getting a Free ServiceNow PDI

A Personal Developer Instance is completely free and ready in minutes:

1. Go to [developer.servicenow.com](https://developer.servicenow.com)
2. Click **"Sign Up and Start Building"**
3. Fill in: First name, Last name, Email, Password, Country
4. Verify your email
5. Log in → click **"Request Instance"** (top right)
6. Select the latest release version → click **"Request"**
7. Wait ~2 minutes for provisioning
8. Copy the URL (e.g., `https://dev12345.service-now.com`) and admin password
9. Add to your `.env`:
   ```
   SNOW_BASE_URL=https://dev12345.service-now.com
   SNOW_USERNAME=admin
   SNOW_PASSWORD=the-password-shown-on-screen
   ```

**Important:** Log into your PDI at least every 10 days or it gets reclaimed.

---

## Key Concepts

### Dry Run Mode
All agents support `DRY_RUN=true`. In dry run:
- Tickets are read from ServiceNow normally
- AI classifications are computed normally
- **Nothing is written back to ServiceNow**
- All results are logged to the console and metrics DB

Always start with dry run. Only disable after reviewing results.

### Confidence Threshold
The classifier uses a 0.75 (75%) confidence threshold:
- `>= 75%`: Classification is auto-applied to the ticket
- `< 75%`: AI adds a "suggestion only" comment for human review
- `P1` tickets: **NEVER** auto-applied regardless of confidence

Change the threshold: `CLASSIFIER_CONFIDENCE_THRESHOLD=0.80` in `.env`

### Synthetic Mode
If no `SNOW_USERNAME` is set in `.env`, the ServiceNow client automatically
loads from `data/synthetic/tickets.json`. This lets you run the full pipeline
without any ServiceNow access.

---

## Testing

```bash
# Run all tests
./scripts/test.sh

# Run specific test file
pytest tests/unit/test_classifier.py -v

# Run with coverage
pytest tests/ --cov=agents --cov=shared --cov-report=term-missing
```

---

## Contributing

This is a personal learning/portfolio project.
Structure follows production engineering practices:
- Every major decision documented in `docs/adr/`
- PII never sent to external APIs (see `shared/data_sanitizer.py`)
- All writes guarded by dry_run mode
- Metrics tracked from day one
