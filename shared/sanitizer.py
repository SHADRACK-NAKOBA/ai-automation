"""
shared/sanitizer.py
────────────────────────────────────────────────────────────
Strips PII and secrets from text before sending to any AI API.

WHY this module exists:
  In enterprise support, tickets contain real customer data —
  email addresses, account numbers, credit card digits, and API
  keys pasted into tickets by mistake. Before we send ANY ticket
  text to Claude, every sensitive pattern is replaced with a
  safe placeholder. This means the AI never sees real PII,
  protecting both your customers and your company.

  This is not optional. Run every ticket through sanitize()
  before calling ai_client.classify() or any other AI function.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SanitizationReport:
    original_length: int
    sanitized_length: int
    patterns_found: list[str]
    text: str


# Each tuple: (regex pattern, replacement string, pattern name)
PII_RULES = [
    # Credit / Debit cards
    (r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",                      "[CARD_NUMBER]",    "credit_card"),
    # US Social Security Numbers
    (r"\b\d{3}-\d{2}-\d{4}\b",                             "[SSN]",            "ssn"),
    # Email addresses
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[EMAIL]",      "email"),
    # IPv4 addresses
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",           "[IP_ADDRESS]",     "ip_address"),
    # Phone numbers (US and international patterns)
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]",   "phone"),
    # Passwords / secrets in key=value format
    (r"(?i)password[\s:=\"']+\S+",                         "password=[REDACTED]", "password"),
    (r"(?i)passwd[\s:=\"']+\S+",                           "passwd=[REDACTED]",   "passwd"),
    (r"(?i)secret[\s:=\"']+\S+",                           "secret=[REDACTED]",   "secret"),
    (r"(?i)api[_\-]?key[\s:=\"']+\S+",                    "api_key=[REDACTED]",  "api_key"),
    (r"(?i)token[\s:=\"']+\S+",                            "token=[REDACTED]",    "token"),
    (r"(?i)auth[\s:=\"']+\S+",                             "auth=[REDACTED]",     "auth"),
    # AWS-style keys
    (r"\bAKIA[0-9A-Z]{16}\b",                              "[AWS_KEY]",        "aws_key"),
    # Anthropic / OpenAI style keys
    (r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b",                   "[AI_API_KEY]",     "ai_key"),
    (r"\bsk-[A-Za-z0-9]{32,}\b",                          "[AI_API_KEY]",     "ai_key"),
]


def sanitize(text: str) -> str:
    """
    Remove PII patterns from a string.
    Returns the sanitized text.
    """
    if not text:
        return text
    for pattern, replacement, _ in PII_RULES:
        text = re.sub(pattern, replacement, text)
    return text


def sanitize_with_report(text: str) -> SanitizationReport:
    """
    Sanitize text and return a report of what was found.
    Useful for auditing and tuning.
    """
    original_length = len(text)
    found = []
    result = text

    for pattern, replacement, name in PII_RULES:
        new_result = re.sub(pattern, replacement, result)
        if new_result != result:
            found.append(name)
        result = new_result

    return SanitizationReport(
        original_length=original_length,
        sanitized_length=len(result),
        patterns_found=found,
        text=result
    )


def sanitize_ticket(ticket: dict) -> dict:
    """
    Sanitize all text fields in a ServiceNow ticket dict.
    Returns a new dict — never modifies the original.
    """
    text_fields = [
        "short_description", "description", "close_notes",
        "comments", "work_notes", "resolution_notes"
    ]
    safe = ticket.copy()
    for field in text_fields:
        if field in safe and safe[field]:
            safe[field] = sanitize(str(safe[field]))
    return safe
