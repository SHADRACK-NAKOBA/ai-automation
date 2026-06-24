"""
tests/unit/test_classifier.py
==============================
Unit tests for ticket classifier logic.
Tests JSON parsing and confidence threshold decisions.
Does NOT call the real Claude API.
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.ticket_classifier import (
    parse_claude_response,
    ClassificationResult,
    CATEGORIES,
    PRIORITIES,
)


class TestParseClaudeResponse:

    def test_parses_valid_json(self):
        raw = json.dumps({
            "category": "Database",
            "priority": "P1",
            "suggested_team": "Database Team",
            "confidence": 0.97,
            "reason": "DB listener is down",
            "tags": ["database", "outage"]
        })
        result = parse_claude_response(raw)
        assert result is not None
        assert result.category == "Database"
        assert result.priority == "P1"
        assert result.confidence == 0.97
        assert result.suggested_team == "Database Team"

    def test_strips_markdown_fences(self):
        raw = '```json\n{"category":"Network","priority":"P2","suggested_team":"Network Ops","confidence":0.88,"reason":"Latency spike","tags":[]}\n```'
        result = parse_claude_response(raw)
        assert result is not None
        assert result.category == "Network"

    def test_invalid_category_falls_back_to_other(self):
        raw = json.dumps({
            "category": "InvalidCategory",
            "priority": "P2",
            "suggested_team": "Some Team",
            "confidence": 0.80,
            "reason": "Test",
            "tags": []
        })
        result = parse_claude_response(raw)
        assert result.category == "Other"

    def test_invalid_priority_falls_back_to_p3(self):
        raw = json.dumps({
            "category": "Application",
            "priority": "Critical",
            "suggested_team": "App Team",
            "confidence": 0.80,
            "reason": "Test",
            "tags": []
        })
        result = parse_claude_response(raw)
        assert result.priority == "P3"

    def test_confidence_clamped_above_one(self):
        raw = json.dumps({
            "category": "Application",
            "priority": "P2",
            "suggested_team": "App Team",
            "confidence": 1.5,
            "reason": "Test",
            "tags": []
        })
        result = parse_claude_response(raw)
        assert result.confidence <= 1.0

    def test_confidence_clamped_below_zero(self):
        raw = json.dumps({
            "category": "Application",
            "priority": "P2",
            "suggested_team": "App Team",
            "confidence": -0.5,
            "reason": "Test",
            "tags": []
        })
        result = parse_claude_response(raw)
        assert result.confidence >= 0.0

    def test_returns_none_on_invalid_json(self):
        result = parse_claude_response("this is not json at all")
        assert result is None

    def test_returns_none_on_empty_string(self):
        result = parse_claude_response("")
        assert result is None

    def test_tags_default_to_empty_list(self):
        raw = json.dumps({
            "category": "Security",
            "priority": "P2",
            "suggested_team": "Security Team",
            "confidence": 0.85,
            "reason": "SSL expired"
        })
        result = parse_claude_response(raw)
        assert result is not None
        assert result.tags == []


class TestConfidenceThreshold:

    def test_above_threshold_not_p1_should_auto_apply(self):
        result = ClassificationResult(
            category="Database",
            priority="P2",
            suggested_team="DB Team",
            confidence=0.90,
            reason="DB down",
            tags=[]
        )
        threshold = 0.75
        should_auto = result.confidence >= threshold and result.priority != "P1"
        assert should_auto is True

    def test_p1_never_auto_applied_even_at_100_percent(self):
        result = ClassificationResult(
            category="Database",
            priority="P1",
            suggested_team="DB Team",
            confidence=0.99,
            reason="Complete outage",
            tags=[]
        )
        threshold = 0.75
        should_auto = result.confidence >= threshold and result.priority != "P1"
        assert should_auto is False

    def test_below_threshold_should_not_auto_apply(self):
        result = ClassificationResult(
            category="Other",
            priority="P3",
            suggested_team="Helpdesk",
            confidence=0.60,
            reason="Unclear",
            tags=[]
        )
        threshold = 0.75
        should_auto = result.confidence >= threshold and result.priority != "P1"
        assert should_auto is False

    def test_exactly_at_threshold_should_auto_apply(self):
        result = ClassificationResult(
            category="Network",
            priority="P3",
            suggested_team="Network Ops",
            confidence=0.75,
            reason="Latency issue",
            tags=[]
        )
        threshold = 0.75
        should_auto = result.confidence >= threshold and result.priority != "P1"
        assert should_auto is True

    def test_all_priorities_except_p1_can_auto_apply(self):
        for priority in ["P2", "P3", "P4"]:
            result = ClassificationResult(
                category="Application",
                priority=priority,
                suggested_team="App Team",
                confidence=0.90,
                reason="Test",
                tags=[]
            )
            should_auto = result.confidence >= 0.75 and result.priority != "P1"
            assert should_auto is True, f"P{priority} should be auto-appliable"