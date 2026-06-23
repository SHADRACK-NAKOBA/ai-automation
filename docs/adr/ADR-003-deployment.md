# ADR-003: Deployment Target

**Date:** Project Start
**Status:** Decided

## Decision

**Docker container on a VM for development, Cloud Run (serverless) for production.**

## Reasoning

Start with Docker + VM:
- Easier to debug (persistent logs, SSH access, no cold starts)
- Familiar tooling
- Can run locally with docker-compose

Migrate to Cloud Run when:
- Agents are stable and debugged
- Traffic patterns are understood
- Cost optimization matters

Docker ensures this migration takes < 1 day (same container, different host).

## Local development

`docker-compose.yml` runs everything locally with one command.
No cloud account required to develop and test.
