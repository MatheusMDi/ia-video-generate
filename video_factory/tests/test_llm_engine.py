from unittest import TestCase
from unittest.mock import Mock, patch

import httpx
from openai import RateLimitError

from src.llm_engine import LLMEngine


def build_rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("quota", response=response, body=None)


class TestLLMEngine(TestCase):
    def _config_side_effect(self, key: str, default: str = "") -> str:
        overrides = {
            "OPENAI_API_KEY": "test-key",
            "MAX_RETRIES": "0",
            "RPM_LIMIT": "100",
            "TPM_LIMIT": "10000",
            "RPD_LIMIT": "0",
            "CONCURRENCY_LIMIT": "1",
            "CACHE_TTL": "3600",
            "MAX_PROMPT_CHARS": "2000",
        }
        return overrides.get(key, default)

    def test_generate_script_raises_runtime_error_on_rate_limit(self) -> None:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = build_rate_limit_error()

        with patch("src.llm_engine.config", side_effect=self._config_side_effect):
            with patch("src.llm_engine.OpenAI", return_value=mock_client):
                engine = LLMEngine(model="gpt-4o-mini", max_tokens=10, temperature=0.1)
                with self.assertRaises(RuntimeError) as context:
                    engine.generate_script("teste")

        self.assertIn("rate limit exceeded", str(context.exception).lower())

    def test_generate_script_uses_cache(self) -> None:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value.choices = [
            Mock(message=Mock(content="resultado"))
        ]

        with patch("src.llm_engine.config", side_effect=self._config_side_effect):
            with patch("src.llm_engine.OpenAI", return_value=mock_client):
                engine = LLMEngine(model="gpt-4o-mini", max_tokens=10, temperature=0.1)
                first = engine.generate_script("teste cache")
                second = engine.generate_script("teste cache")

        self.assertEqual(first, "resultado")
        self.assertEqual(second, "resultado")
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)
