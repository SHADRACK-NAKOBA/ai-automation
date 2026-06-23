# ADR-001: AI Provider Selection

**Date:** Project Start
**Status:** Decided
**Decided by:** AI Automation Catalyst

## Context

We need an AI API to power ticket classification, log analysis, and other agents.
Several providers are available: Anthropic (Claude), OpenAI (GPT-4o), Google (Gemini/Vertex AI).

## Decision

**Use Anthropic Claude (claude-sonnet-4-6)** for all AI inference.

## Reasoning

| Criteria | Claude | GPT-4o | Gemini |
|----------|--------|--------|--------|
| Instruction following (structured JSON output) | Excellent | Very Good | Good |
| Latency | Fast | Fast | Fast |
| Cost (Sonnet tier) | Competitive | Similar | Lower |
| Context window | 200K tokens | 128K | 1M |
| Safety/refusal on edge cases | Conservative | Moderate | Moderate |

For support automation, we need **precise, structured JSON output** on every call.
Claude Sonnet is the most consistent at following complex JSON schemas without adding
markdown or preamble.

## Abstraction Layer

The AI client is abstracted behind `shared/ai_client.py`.
This means if we need to switch providers (e.g., for on-premises deployment using
Vertex AI or OCI Generative AI), we change ONE file, not 7 agent files.

## Security

External API: Data must be sanitized before sending.
See `shared/data_sanitizer.py` — runs on every ticket before any AI call.

## Alternatives Considered

- **OpenAI GPT-4o**: Very close. Would be equivalent choice. Claude slightly better
  at following strict JSON format in early testing.
- **Vertex AI (Google Cloud)**: Preferred if we must keep data in GCP environment.
  Switch is one config change due to abstraction layer.
- **Local/on-prem LLM (Ollama)**: Viable for sensitive data. Much slower.
  Keep as fallback option if security blocks external APIs.
