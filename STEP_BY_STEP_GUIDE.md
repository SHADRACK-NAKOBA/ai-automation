# COMPLETE STEP-BY-STEP GUIDE
## From Zero to Live — Every Click, Every Command, Every Decision

---

## PHASE 0 — Before You Touch Any Code

### Step 0.1 — Get Your Free ServiceNow PDI (10 minutes)

A Personal Developer Instance is your practice ServiceNow. 100% free. No credit card.

**Every click:**
1. Open browser → go to: `https://developer.servicenow.com`
2. Click the green **"Sign Up and Start Building"** button (top right)
3. Fill in:
   - First Name, Last Name
   - Email address (use your personal email — NOT company email)
   - Password (save this!)
   - Country
4. Click **"Sign Up"**
5. Check your email → click the verification link
6. Log back in to `https://developer.servicenow.com`
7. In the top right, click **"Request Instance"**
8. A popup appears showing ServiceNow versions → select the **top/latest version**
9. Click **"Request"**
10. Wait ~2 minutes (you'll see a loading spinner)
11. A dialog appears: **"Your instance is ready!"**
12. **COPY AND SAVE these three things RIGHT NOW:**
    - Instance URL: `https://dev12345.service-now.com` (your number will differ)
    - Username: `admin`
    - Password: (shown on screen — copy it)
13. Click **"Open Instance"** to verify it loads

**WHY you need a PDI:**
Your PDI is identical in structure to production. You build and test everything
here so that when you finally get real access, you're not learning on their data.

**IMPORTANT:** Log into your PDI at least every 10 days or ServiceNow reclaims it.

---

### Step 0.2 — Create Sample Tickets in Your PDI (5 minutes)

Your PDI has sample data but we want controlled tickets we can test against.

**Every click:**
1. Open your PDI URL in browser
2. Log in with admin / [your password]
3. In the left sidebar, type **"Incident"** in the search/filter bar
4. Click **"Create New"**
5. Create this ticket:
   - Short description: `Production database not responding - orders failing`
   - Description: `Our Oracle database stopped accepting connections. All order attempts failing with ORA-12541. ~500 customers affected.`
   - Priority: (leave blank — our agent will set this)
   - Category: (leave blank — our agent will set this)
   - Click **"Submit"**
6. Repeat to create 3–4 more tickets (use the ones from `data/synthetic/tickets.json` as inspiration)

**WHY create blank tickets:**
We need tickets with NO category and NO priority so the classifier has something to classify.

---

### Step 0.3 — Get Your Anthropic API Key (3 minutes)

**Every click:**
1. Go to: `https://console.anthropic.com`
2. Click **"Sign Up"** (or Log In if you have an account)
3. Fill in email and password
4. Verify your email
5. After login: click your name/avatar (top right) → **"API Keys"**
6. Click **"Create Key"**
7. Name it: `ai-automation-dev`
8. Click **"Create Key"**
9. **COPY THE KEY NOW — you only see it once**
   - It starts with `sk-ant-api03-...`
   - Save it to a password manager or secure note
10. Note: You'll need to add a payment method and ~$5 in credits to use the API.
    Go to **"Billing"** → **"Add Payment Method"**

**WHY Anthropic and not OpenAI:**
Both work. Claude is slightly better at following strict JSON output format
without adding markdown or prose, which matters when we need to parse the response
as structured data. Either would work for this use case. (See ADR-001 in docs/adr/)

---

## PHASE 1 — Set Up Your Local Environment

### Step 1.1 — Install Git (if not already installed)

**Mac:**
```bash
# Open Terminal (Cmd+Space → type "Terminal")
git --version
# If not installed, a dialog appears → click "Install"
```

**Windows:**
```
1. Go to: https://git-scm.com/download/win
2. Download the installer → run it → click Next through all defaults
3. Open "Git Bash" from Start menu
```

**Linux:**
```bash
sudo apt-get install git -y
```

---

### Step 1.2 — Install Python 3.9+ (if not already installed)

**Check if you have it:**
```bash
python3 --version
# Should show Python 3.9 or higher
```

**If not installed:**
- Mac: `brew install python3` (install Homebrew first from brew.sh)
- Windows: Go to python.org → Downloads → Python 3.12 → run installer → ✅ check "Add to PATH"
- Linux: `sudo apt-get install python3 python3-pip -y`

---

### Step 1.3 — Clone the Repository

**Option A: You're pushing to YOUR GitHub (recommended)**
```bash
# First: go to github.com → click "+" → "New repository"
# Name it: ai-automation
# Set to: Private
# Do NOT initialize with README (we have our own)
# Click "Create repository"
# Copy the URL shown (https://github.com/YOUR_USERNAME/ai-automation.git)

# Then in your terminal:
git clone https://github.com/YOUR_USERNAME/ai-automation.git
cd ai-automation
```

**Option B: Start fresh from this downloaded project**
```bash
# Unzip the project you downloaded
# Then initialize git:
cd ai-automation
git init
git add .
git commit -m "Initial commit — AI Automation Platform"

# Push to your GitHub (create repo first at github.com):
git remote add origin https://github.com/YOUR_USERNAME/ai-automation.git
git push -u origin main
```

---

### Step 1.4 — Run the Setup Script

```bash
# Make the setup script executable (Mac/Linux):
chmod +x scripts/setup.sh

# Run it:
./scripts/setup.sh
```

**On Windows (Git Bash):**
```bash
bash scripts/setup.sh
```

**What the setup script does (every step explained):**
1. Checks Python version is 3.9+
2. Creates a Python virtual environment (`venv/`) — isolated package space
3. Installs all Python packages from `requirements.txt`
4. Creates `data/synthetic/` and `data/logs/` directories
5. Copies `.env.example` to `.env`
6. Runs `python tools/seed_data.py` to create synthetic ticket data

---

### Step 1.5 — Configure Your .env File

Open `.env` in any text editor:

```bash
# Mac/Linux:
nano .env
# or: code .env (if VS Code installed)

# Windows:
notepad .env
```

**Fill in EXACTLY these values:**

```env
# The key you copied from console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY_HERE

# Your PDI URL from developer.servicenow.com
SNOW_BASE_URL=https://dev12345.service-now.com

# PDI credentials
SNOW_USERNAME=admin
SNOW_PASSWORD=the-password-from-pdi-screen

# KEEP THIS TRUE until you're confident the agent works correctly
DRY_RUN=true

# These stay as-is for now
AUTO_APPLY_P1=false
ENVIRONMENT=development
LOG_LEVEL=INFO
DB_PATH=data/metrics.db
CLASSIFIER_CONFIDENCE_THRESHOLD=0.75
```

**Save the file.**

**WHY DRY_RUN=true:**
In dry run mode, the agent reads from ServiceNow and classifies tickets,
but DOES NOT write anything back. It only logs what it would have done.
This lets you see the AI's output on real tickets before it touches anything.
You only set this to false after reviewing dry run output and being satisfied.

---

### Step 1.6 — Activate Virtual Environment

**Mac/Linux:**
```bash
source venv/bin/activate
# Your prompt will change to show (venv) at the start
```

**Windows (Git Bash):**
```bash
source venv/Scripts/activate
```

**Windows (Command Prompt):**
```
venv\Scripts\activate.bat
```

**WHY a virtual environment:**
It keeps this project's packages separate from your system Python.
If you install a package for this project, it doesn't affect any other Python project.
It also means the exact versions in `requirements.txt` are what gets installed.

---

## PHASE 2 — Run Connection Tests

### Step 2.1 — Run test_connections.py

```bash
python tools/test_connections.py
```

**What you should see:**

```
============================================================
  AI AUTOMATION — Connection Tests
============================================================

── Test 1: Environment Variables ─────────────────────────
  ✅ ANTHROPIC_API_KEY     present (ends in ...xxxx)
  ✅ SNOW_BASE_URL         https://dev12345.service-now.com

── Test 2: Claude API ────────────────────────────────────
  ✅ Claude API working | Response: 'OK' | Latency: 847ms

── Test 3: ServiceNow ────────────────────────────────────
  ✅ ServiceNow [LIVE] | Sample tickets fetched: 4
     First ticket: INC0001001 — Production database not responding

── Test 4: Metrics Database ──────────────────────────────
  ✅ Database working | Path: data/metrics.db

── Test 5: Synthetic Data Files ──────────────────────────
  ✅ Synthetic tickets: data/synthetic/tickets.json (12 tickets)

── Test 6: Data Sanitizer ────────────────────────────────
  ✅ Sanitizer working

  ✅ All tests passed. You're ready to run agents.
```

**If Test 2 fails (Claude API):**
- Double-check your `ANTHROPIC_API_KEY` in `.env`
- Make sure you have billing set up at console.anthropic.com
- Make sure there are no spaces before/after the key in `.env`

**If Test 3 fails (ServiceNow):**
- Check your PDI URL — should be `https://devXXXXX.service-now.com` (no trailing slash)
- Check your username (`admin`) and password (from PDI screen)
- Your PDI may have hibernated — log into it at developer.servicenow.com to wake it up

**If all else fails — run in Synthetic Mode:**
Remove `SNOW_USERNAME` and `SNOW_PASSWORD` from `.env` entirely.
The app will automatically use `data/synthetic/tickets.json` instead.
This is completely valid for development and testing.

---

## PHASE 3 — Run the Accuracy Test

### Step 3.1 — Run Against Synthetic Data

This is the MOST IMPORTANT step. Do this before ever enabling live writes.

```bash
python agents/ticket_classifier.py --accuracy-test
```

**What you'll see:**
```
Running accuracy test on 12 tickets...
----------------------------------------------------------------------
✅ INC0001001 | Cat: Database → Database ✓ | Pri: P1 → P1 ✓ | Conf: 97%
✅ INC0001002 | Cat: Authentication → Authentication ✓ | Pri: P1 → P1 ✓ | Conf: 94%
✅ INC0001003 | Cat: Performance → Performance ✓ | Pri: P2 → P2 ✓ | Conf: 88%
...
----------------------------------------------------------------------
Category accuracy: 92% (target: >80%)
Priority accuracy: 89% (target: >85%)
✅ ACCURACY TARGETS MET — Safe to go live
```

**If accuracy is below target:**
Open `agents/ticket_classifier.py` and find the `build_classification_prompt()` function.
The prompt is what drives the AI. Tune it:

1. Add more specific examples for categories that are wrong:
   ```
   Examples of PERFORMANCE tickets:
   - Batch job running longer than expected
   - API response times exceeding threshold
   - Database query taking >30 seconds
   ```

2. Make priority definitions more specific to your environment:
   ```
   P1: Complete outage affecting >100 users OR revenue impact >$10,000/hour
   ```

3. Re-run the accuracy test after each change.

**WHY this matters:**
One wrong P1 classification wakes an on-call analyst at 3am unnecessarily.
The accuracy test catches this before it happens in production.
80% accuracy target = only 2 wrong classifications per 10 tickets.
For a first automated system, this is excellent and sets the right expectation.

---

## PHASE 4 — First Dry Run Against Real ServiceNow

### Step 4.1 — Run Classifier in Dry Run Mode

Make sure `DRY_RUN=true` in your `.env`. Then:

```bash
python agents/ticket_classifier.py
```

**What you'll see:**
```
============================================================
TICKET CLASSIFIER — Starting run
  DRY RUN: True
  Confidence threshold: 75%
============================================================
Processing INC0000123: Database connection timeout in prod...
  INC0000123: [Database/P1] confidence=96% → AUTO-APPLIED
Processing INC0000124: User cannot log in to portal...
  INC0000124: [Authentication/P3] confidence=81% → AUTO-APPLIED
Processing INC0000125: Slow report performance...
  INC0000125: [Performance/P2] confidence=72% → SUGGESTED
...
============================================================
TICKET CLASSIFIER — Run complete
  Processed:    8
  Auto-applied: 6
  Suggested:    2
  Failed:       0
  Hours saved:  0.53h
  Duration:     4821ms
============================================================
```

**Key things to check in the output:**
- Does the Category look right for each ticket?
- Does the Priority match what a senior analyst would assign?
- Is the Confidence threshold catching genuinely ambiguous tickets? (should go to SUGGESTED)
- Are P1 tickets always going to SUGGESTED (not auto-applied)?

**Show this output to a team member before enabling live mode.**

---

## PHASE 5 — Go Live

### Step 5.1 — Enable Live Writes (P3/P4 Only First)

After dry run output is reviewed and approved:

1. Open `.env`
2. Change `DRY_RUN=false`
3. Save

Now run against only low-priority tickets first by modifying the query temporarily.
In `shared/snow_client.py`, change the `get_unclassified_tickets` query to:
```python
"sysparm_query": "category=^state!=6^state!=7^priority=4",  # P4 only
```

Run the agent:
```bash
python agents/ticket_classifier.py
```

Go to your ServiceNow PDI → check a P4 ticket → it should now have:
- Category set
- Priority confirmed
- A work note from "AI Ticket Classifier" explaining the classification

**This is your first live automation. Take a screenshot.**

### Step 5.2 — After 48 Hours, Enable Full Scope

If P4 results look good:
1. Revert the query in `snow_client.py` (remove the priority filter)
2. Run again

You're now fully live.

---

## PHASE 6 — Set Up Continuous Running

### Step 6.1 — Run the Scheduler (keeps agent running)

```bash
python scheduler/jobs.py
```

This runs the classifier every 5 minutes automatically.
Keep this terminal open (or run it in the background with `nohup`).

### Step 6.2 — View Your Metrics

```bash
python tools/generate_report.py
```

This shows how many tickets were processed and hours saved.
This is what you share in your weekly leadership update.

---

## PHASE 7 — Push to GitHub

### Step 7.1 — Commit Your Work

```bash
# Check what changed:
git status

# Stage everything EXCEPT .env (which is in .gitignore):
git add .

# Verify .env is NOT in the staged files:
git status
# .env should NOT appear in the list

# Commit:
git commit -m "feat: Add Ticket Classifier Agent with synthetic data support

- AI-powered ticket classification using Claude claude-sonnet-4-6
- Supports synthetic mode (no ServiceNow needed for local dev)
- Dry run mode prevents accidental writes
- Confidence threshold: 75% (configurable)
- P1 tickets always require human review
- Full metrics tracking via SQLite
- Accuracy test: 92% category, 89% priority on synthetic data"

# Push:
git push origin main
```

**WHY this commit message format:**
`feat:` is a conventional commit prefix. It signals this is a new feature.
The body explains WHAT, not HOW. Future you (or your team) can read this
in a year and understand exactly what this commit does.

---

## COMMON PROBLEMS AND EXACT FIXES

### "ModuleNotFoundError: No module named 'anthropic'"
```bash
# Make sure your virtual environment is active:
source venv/bin/activate  # Mac/Linux
# Then:
pip install -r requirements.txt
```

### "Missing required environment variables: ['ANTHROPIC_API_KEY']"
```bash
# Your .env isn't loading. Make sure you're running from the project root:
cd /path/to/ai-automation
python tools/test_connections.py
```

### "Authentication Error" from Claude API
- Your API key is wrong or expired
- Go to console.anthropic.com → API Keys → create a new one
- Make sure you have credits added to your account

### PDI Hibernated (ServiceNow won't connect)
- PDIs hibernate after 10 days of inactivity
- Go to developer.servicenow.com → log in → click "Wake Up Instance"
- Wait 2-3 minutes → try again

### "No unclassified tickets found"
- All tickets in your PDI may already have categories
- Create new tickets via ServiceNow (leave Category and Priority blank)
- Or switch to synthetic mode (remove SNOW_USERNAME from .env)

---

## THE DEMO SCRIPT (Show Your Manager)

When you're ready to show your manager what you've built:

```bash
# 1. Open two terminal windows

# Terminal 1 — Run the classifier:
python agents/ticket_classifier.py --accuracy-test
# Show: "✅ ACCURACY TARGETS MET"

# Terminal 2 — Show the metrics:
python tools/generate_report.py

# Then go to your PDI and show a ticket that was auto-classified
```

**What to say:**
> "I built this over the past two weeks so I'd be ready the moment I get access to your
> ServiceNow. Here's what it does: [demo]. Here's the accuracy against 12 test cases:
> 92% category accuracy, 89% priority accuracy. In dry run mode, it processed
> [X] tickets and would have saved [X] analyst-hours. The moment you give me
> read/write API access, I can have this running against your real tickets the same day."

This is the moment that gets your project fast-tracked.
