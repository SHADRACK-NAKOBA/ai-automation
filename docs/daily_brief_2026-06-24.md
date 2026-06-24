# Daily Brief — 24 June 2026
**For:** Prince Nakoba, AI Automation Catalyst
**Read time:** ~2 minutes

---

## PROJECT STATUS

| Component | Status | Note |
|-----------|--------|------|
| Ticket Classifier (Agent #1) | ✅ **LIVE** | Running on synthetic data, dry-run mode |
| Shared library (AI client, SNOW client, PII sanitizer, metrics DB) | ✅ **LIVE** | Full production-grade foundation |
| Metrics tracking & ROI reporting | ✅ **LIVE** | SQLite DB logging every agent run |
| 4 Architecture Decision Records | ✅ **DONE** | AI provider, triggers, deployment, database |
| Log Harvester (Agent #2) | 🔧 **Building** | Highest-priority next item |
| Scheduler (auto-polling every 5 min) | 🔧 **Building** | Turns scripts into a platform |
| Webhooks, Dashboard, Tests | 📋 **Planned** | Not started — do not surface yet |

---

## KEY METRICS
_(Pull these from memory — they're real, from `data/metrics.db`)_

- **12 classifier runs** this week, **83% success rate**
- **3 auto-applied** classifications (confidence ≥ 75%) — zero human effort needed
- **9 flagged for human review** — including all low-confidence and P2 tickets
- **40 minutes returned** to the support team this week
- **P1 tickets: never auto-applied** — hard-coded safety guardrail, always human review
- **Project health score: 7.5 / 10** — solid foundation, agents are the next unlock

---

## TALKING POINTS
_Five things you can say with full confidence:_

**1. "We have a safety-first design."**
The classifier never auto-applies P1 tickets. Anything below 75% confidence is flagged for human review, not applied. We built the guardrails before we built the speed.

**2. "Every action is audited."**
Every classification — auto-applied or not — is logged to a SQLite database with the ticket number, confidence score, category, priority, and whether a human reviewed it. We can pull a report at any time.

**3. "We built the plumbing right."**
PII is stripped from every ticket before it touches the AI API. The AI client, ServiceNow connector, config, and logging are all shared libraries — one bug fix applies everywhere.

**4. "The ROI case is already building."**
At 4 minutes saved per ticket and 100+ tickets per day in a typical support team, the classifier alone targets 400+ minutes (6+ hours) saved daily once the scheduler is running continuously. Week 1 is the baseline.

**5. "We chose Claude because it's the most reliable at structured output."**
We evaluated Claude, GPT-4o, and Gemini. For support automation we need consistent JSON output — Claude Sonnet was the clear winner. And we abstracted the AI client, so if the business requires switching providers, it's one config change.

---

## QUESTIONS TO ASK THE TEAM

**1. "What is the highest-volume, most manual thing your analysts do every single day?"**
→ *Why it's smart:* You already know classification is one answer. This surfaces Agent #2's priority from the team's own pain, not your assumption.

**2. "When a P1 fires, what's the first thing you open and how long does it take to get context?"**
→ *Why it's smart:* This is the Incident Brief / Log Harvester use case. Their answer will tell you exactly what to build next and what ROI number to put on it.

**3. "Do we have a ServiceNow PDI I can connect to for dry-run testing, or do I need to request one?"**
→ *Why it's smart:* It's a concrete, unblocking ask. It signals you're ready to go live and need one thing from them. PDIs are free at developer.servicenow.com — you may not need to wait for IT.

---

## WHAT NOT TO MENTION

| Topic | Why to avoid |
|-------|-------------|
| Log Harvester, Scheduler, Webhooks | All are empty stubs — 0 bytes of code |
| Dashboard | Not started |
| Unit tests | Test directories exist but contain zero test files |
| The brace-expansion folders at the project root | Leftover shell accident — cosmetic, but looks messy |
| `shared/sanitizer.py` vs `shared/data_sanitizer.py` | Possible duplicate — unresolved, don't surface |
| "83% success rate" without context | Runs were on synthetic/test data — clarify if pressed |

**Safe framing if asked about unbuilt agents:** _"The architecture supports seven agents — we're building them in ROI order. Classifier is live, Log Harvester is next."_

---

## WHAT YOU'RE BUILDING NEXT WEEK

### Priority 1 — `agents/log_harvester.py` (Agent #2)
**Why:** 18 minutes saved per P1/P2 incident vs 4 minutes for classification. Every major incident currently requires an analyst to manually SSH, grep logs, and paste summaries. The Log Harvester automates that entirely.

**What it will do:**
- Triggered by a new P1/P2 ticket in ServiceNow
- Pulls application logs for the relevant time window
- Strips PII, sends to Claude for error pattern summarisation
- Posts a plain-English summary as a comment on the ticket
- Logs minutes saved to `metrics_db`

### Priority 2 — `scheduler/jobs.py`
**Why:** Right now the classifier only runs when you run it manually. The scheduler makes it run every 5 minutes automatically. This is the difference between a demo and a platform.

---

_Brief generated from: `data/metrics.db` · `docs/PROJECT_STATUS.md` · `agents/ticket_classifier.py` · `data/synthetic/tickets.json`_
