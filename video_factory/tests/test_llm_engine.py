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
    def test_generate_script_raises_runtime_error_on_rate_limit(self) -> None:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = build_rate_limit_error()

        with patch("src.llm_engine.config", return_value="test-key"):
            with patch("src.llm_engine.OpenAI", return_value=mock_client):
                engine = LLMEngine(model="gpt-4o-mini", max_tokens=10, temperature=0.1)
                with self.assertRaises(RuntimeError) as context:
                    engine.generate_script("teste")

        self.assertIn("quota exceeded", str(context.exception).lower())
