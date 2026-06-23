# ADR-004: Metrics Database

**Date:** Project Start
**Status:** Decided

## Decision

**SQLite for local development, PostgreSQL for production.**

## Reasoning

SQLite:
- Zero setup, works immediately
- Perfect for single-process local dev
- Metrics DB is append-only (low write concurrency)
- File can be inspected directly with DB Browser for SQLite

PostgreSQL migration path:
- SQLAlchemy abstraction layer means one config change
- pgvector extension enables semantic similarity search
  (needed for "find similar past incidents" feature in Phase 2)

## Why not start with PostgreSQL immediately?

Setting up Postgres locally (Docker or hosted) adds 30 min of setup friction
at the start. For a solo developer proving the concept, SQLite is the right
starting point. We switch to Postgres when we need multi-process access or
similarity search.
