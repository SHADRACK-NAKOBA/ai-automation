"""
shared/data_sanitizer.py
========================
Strips PII and secrets from ticket data before sending to any AI API.

WHY THIS EXISTS:
  Ticket data often contains customer emails, account numbers, passwords
  in error messages, IP addresses, and other sensitive data.
  We NEVER send raw ticket text to an external API.
  This runs on every ticket before it touches Claude.

WHAT IT STRIPS:
  - Email addresses         → [EMAIL]
  - Credit card numbers     → [CARD_NUMBER]
  - SSNs                    → [SSN]
  - IP addresses            → [IP_ADDRESS]
  - Passwords in text       → [REDACTED]
  - API keys/tokens in text → [REDACTED]

DESIGN DECISION:
  Regex-based, not AI-based. We can't use AI to sanitize data
  before sending it to AI — that's circular. Fast regex is the right tool.
"""

import re
from shared.logger import get_logger

logger = get_logger("data_sanitizer")

# Each tuple: (pattern, replacement)
PII_RULES = [
    # Email addresses
    (r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', '[EMAIL]'),
    # Credit card numbers (Visa, MC, Amex patterns)
    (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[CARD_NUMBER]'),
    # Social Security Numbers
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
    # IP addresses (v4)
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_ADDRESS]'),
    # Passwords in log text
    (r'(?i)password\s*[=:"\s]+\S+', 'password=[REDACTED]'),
    (r'(?i)passwd\s*[=:"\s]+\S+', 'passwd=[REDACTED]'),
    # API keys, tokens, secrets
    (r'(?i)(api[_\-]?key|token|secret|auth)\s*[=:"\s]+\S+', r'\1=[REDACTED]'),
    # Phone numbers (US format)
    (r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]'),
    # AWS Access Keys
    (r'\bAKIA[0-9A-Z]{16}\b', '[AWS_KEY]'),
    # Anthropic and OpenAI API keys
    (r'\bsk-ant-[A-Za-z0-9\-_]{20,}\b', '[AI_API_KEY]'),
    (r'\bsk-[A-Za-z0-9]{32,}\b', '[AI_API_KEY]'),
    # Account/customer IDs that look numeric (8+ digits)
    # NOTE: Comment this out if your ticket numbers are numeric
    # (r'\b\d{8,}\b', '[ACCOUNT_ID]'),
]


def sanitize_text(text: str) -> str:
    """Apply all PII rules to a string."""
    if not text:
        return text
    original_len = len(text)
    for pattern, replacement in PII_RULES:
        text = re.sub(pattern, replacement, text)
    if len(text) != original_len:
        logger.debug("PII patterns applied to text")
    return text


def sanitize_ticket(ticket: dict) -> dict:
    """
    Sanitize all text fields in a ServiceNow ticket dict.
    Returns a new dict — never mutates the original.
    """
    safe = ticket.copy()
    text_fields = [
        "short_description", "description", "close_notes",
        "comments", "work_notes", "additional_comments"
    ]
    for field in text_fields:
        if safe.get(field):
            safe[field] = sanitize_text(str(safe[field]))
    return safe


def sanitize_log(log_text: str, max_length: int = 3000) -> str:
    """
    Sanitize a log string and truncate to max_length.
    Logs often have passwords and tokens in them.
    """
    sanitized = sanitize_text(log_text)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + f"\n...[truncated at {max_length} chars]"
    return sanitized
