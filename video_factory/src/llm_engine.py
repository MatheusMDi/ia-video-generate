"""LLM client for script generation."""
from __future__ import annotations

import logging
from typing import Any, Dict

from decouple import config
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError


class LLMEngine:
    """Client for generating scripts using OpenAI."""

    def __init__(self, model: str, max_tokens: int, temperature: float) -> None:
        """Initialize the LLM client with configuration."""
        api_key = config("OPENAI_API_KEY", default="")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def generate_script(self, prompt: str) -> str:
        """Generate a script from a given prompt."""
        logging.info("[LLM] Generating script for prompt: %s", prompt)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )
        except RateLimitError as exc:
            message = "OpenAI quota exceeded. Check your plan and billing details."
            logging.error("[LLM] %s", message)
            raise RuntimeError(message) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            message = "OpenAI request failed due to a network timeout."
            logging.error("[LLM] %s", message)
            raise RuntimeError(message) from exc
        return response.choices[0].message.content.strip()


def build_llm_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Extract LLM settings from a settings dictionary."""
    llm_settings = settings.get("llm", {})
    return {
        "model": config("OPENAI_MODEL", default="gpt-4o-mini"),
        "max_tokens": llm_settings.get("max_tokens", 500),
        "temperature": llm_settings.get("temperature", 0.7),
    }
