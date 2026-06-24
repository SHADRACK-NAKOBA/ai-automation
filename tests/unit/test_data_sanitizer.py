"""
tests/unit/test_data_sanitizer.py
==================================
Unit tests for the PII sanitizer.
These must all pass before any code is deployed.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.data_sanitizer import sanitize_text, sanitize_ticket


class TestSanitizeText:

    def test_removes_email(self):
        result = sanitize_text("Contact john@example.com for help")
        assert "@" not in result
        assert "[EMAIL]" in result

    def test_removes_ip_address(self):
        result = sanitize_text("Server at 192.168.1.100 is down")
        assert "192.168.1.100" not in result
        assert "[IP_ADDRESS]" in result

    def test_removes_password_in_text(self):
        result = sanitize_text("Login with password=secret123")
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_removes_api_token(self):
        result = sanitize_text("token=eyJhbGciOiJSUzI1NiJ9.abc123")
        assert "eyJhbGciOiJSUzI1NiJ9" not in result

    def test_removes_phone_number(self):
        result = sanitize_text("Call me at 555-867-5309")
        assert "555-867-5309" not in result
        assert "[PHONE]" in result

    def test_removes_aws_key(self):
        result = sanitize_text("AWS key is AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[AWS_KEY]" in result

    def test_removes_anthropic_api_key(self):
        result = sanitize_text("key=sk-ant-api03-abcdefghijklmnopqrstuvwx")
        assert "sk-ant-api03" not in result
        assert "[AI_API_KEY]" in result

    def test_safe_text_unchanged(self):
        safe = "The database is running slowly on the production server"
        result = sanitize_text(safe)
        assert result == safe

    def test_empty_string_handled(self):
        assert sanitize_text("") == ""

    def test_none_handled(self):
        assert sanitize_text(None) is None

    def test_multiple_pii_in_one_string(self):
        text = "User john@company.com at 10.0.0.1 used password=abc123"
        result = sanitize_text(text)
        assert "john@company.com" not in result
        assert "10.0.0.1" not in result
        assert "abc123" not in result


class TestSanitizeTicket:

    def test_sanitizes_description_field(self):
        ticket = {
            "number": "INC001",
            "short_description": "Issue reported by john@test.com",
            "description": "User at 192.168.1.1 cannot login"
        }
        result = sanitize_ticket(ticket)
        assert "@" not in result["short_description"]
        assert "192.168.1.1" not in result["description"]

    def test_does_not_mutate_original(self):
        ticket = {"description": "email@test.com"}
        original_desc = ticket["description"]
        sanitize_ticket(ticket)
        assert ticket["description"] == original_desc

    def test_preserves_non_pii_fields(self):
        ticket = {
            "number": "INC001",
            "short_description": "Database is slow",
            "priority": "1"
        }
        result = sanitize_ticket(ticket)
        assert result["number"] == "INC001"
        assert result["priority"] == "1"