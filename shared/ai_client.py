"""
shared/ai_client.py
────────────────────────────────────────────────────────────
Thin wrapper around the Anthropic Claude API.

WHY wrap the SDK instead of calling it directly in agents:
  1. Single place to set the model — change model for all
     agents in one line.
  2. Built-in token logging for cost tracking.
  3. Easy to mock in tests.
  4. If Anthropic changes the SDK interface, one file to fix.
"""

import json
import logging
import time
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        """
        WHY claude-sonnet-4-6 as default:
          - Excellent reasoning for classification and summarization
          - ~4x cheaper than Opus
          - Fast enough for real-time agent work
          - Use Haiku only for very high-volume simple tasks
        """
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1000,
        as_json: bool = False
    ) -> str:
        """
        Send a prompt to Claude and return the text response.

        Args:
            prompt:     The user message.
            system:     Optional system prompt (sets Claude's role/context).
            max_tokens: Maximum tokens in the response.
            as_json:    If True, strips markdown fences and parses/re-serializes
                        to validate JSON before returning the string.

        Returns:
            The response text as a string.
        """
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        start = time.time()
        response = self._client.messages.create(**kwargs)
        elapsed = (time.time() - start) * 1000

        # Track token usage for cost reporting
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        logger.debug(
            f"Claude: {response.usage.input_tokens}in / "
            f"{response.usage.output_tokens}out / {elapsed:.0f}ms"
        )

        text = response.content[0].text.strip()

        if as_json:
            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first line (```json or ```) and last line (```)
                text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
            # Validate it's real JSON
            json.loads(text)

        return text

    def complete_json(self, prompt: str, system: Optional[str] = None, max_tokens: int = 1000) -> dict:
        """Convenience: complete and parse to dict in one call."""
        text = self.complete(prompt, system=system, max_tokens=max_tokens, as_json=True)
        return json.loads(text)

    def estimate_cost(self) -> dict:
        """
        Estimate cost based on token usage.
        Claude Sonnet 4.6 pricing (as of 2025):
          Input:  $3 per million tokens
          Output: $15 per million tokens
        """
        input_cost = (self.total_input_tokens / 1_000_000) * 3.00
        output_cost = (self.total_output_tokens / 1_000_000) * 15.00
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
            "total_cost_usd": round(input_cost + output_cost, 4),
        }

    def ping(self) -> bool:
        """Test that the API key works."""
        try:
            self.complete("Say OK", max_tokens=5)
            return True
        except Exception:
            return False
