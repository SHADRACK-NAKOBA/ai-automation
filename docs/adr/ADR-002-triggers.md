# ADR-002: Agent Trigger Strategy

**Date:** Project Start
**Status:** Decided

## Context

Agents need to know when to run. Options: polling (check periodically) or
webhooks (get notified instantly when something happens).

## Decision

**Use both, based on urgency:**
- Polling (every 5 min): Ticket Classifier, routine batch tasks
- Webhooks (real-time): Log Harvester, Incident Brief on P1/P2

## Reasoning

**Polling is simpler to build and good enough for classification.**
A 5-minute delay in classification is acceptable. No public URL needed.

**Webhooks are required for P1/P2 response.**
When a P1 fires, the on-call analyst needs context in 90 seconds.
A 5-minute polling delay defeats the purpose of the Incident Brief.
Webhooks require exposing a public HTTPS URL (use ngrok for dev, Cloud Run for prod).

## Implementation

Polling: `scheduler/jobs.py` using APScheduler.
Webhooks: `webhooks/main.py` using Flask.

## Phase approach

Phase 1: Polling only (simpler, gets value immediately).
Phase 2: Add webhooks for P1/P2 agents.
