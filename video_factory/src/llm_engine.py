"""LLM client for script generation."""
from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from decouple import config
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

DEFAULT_RPM_LIMIT = "<COLE AQUI: requests por minuto do meu Free tier>"
DEFAULT_TPM_LIMIT = "<COLE AQUI: tokens por minuto do meu Free tier>"
DEFAULT_RPD_LIMIT = "<COLE AQUI: requests por dia, se existir no painel>"
DEFAULT_CONCURRENCY_LIMIT = "<COLE AQUI: concorrência máxima, se existir>"


def _parse_int_env(name: str, default_value: str, fallback: int) -> int:
    value = config(name, default=default_value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        logging.warning("[LLM] Invalid %s value %r. Using fallback=%s.", name, value, fallback)
        return fallback


def _estimate_tokens(text: str, max_output_tokens: int) -> int:
    return max(1, len(text) // 4) + max_output_tokens


@dataclass
class CacheEntry:
    expires_at: float
    value: str


class ResponseCache:
    def __init__(self, ttl_seconds: int, disk_path: Optional[Path]) -> None:
        self._ttl_seconds = ttl_seconds
        self._disk_path = disk_path
        self._lock = threading.Lock()
        self._cache: Dict[str, CacheEntry] = {}
        if self._disk_path:
            self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        if not self._disk_path or not self._disk_path.exists():
            return
        try:
            payload = json.loads(self._disk_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.warning("[LLM] Failed to load cache file: %s", exc)
            return
        now = time.time()
        for key, entry in payload.items():
            expires_at = entry.get("expires_at", 0.0)
            if expires_at > now:
                self._cache[key] = CacheEntry(expires_at=expires_at, value=entry.get("value", ""))

    def _persist(self) -> None:
        if not self._disk_path:
            return
        payload = {key: {"expires_at": entry.expires_at, "value": entry.value} for key, entry in self._cache.items()}
        try:
            self._disk_path.parent.mkdir(parents=True, exist_ok=True)
            self._disk_path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError as exc:
            logging.warning("[LLM] Failed to write cache file: %s", exc)

    def get(self, key: str) -> Optional[str]:
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
            if not entry or entry.expires_at <= now:
                if entry:
                    self._cache.pop(key, None)
                    self._persist()
                return None
            return entry.value

    def set(self, key: str, value: str) -> None:
        expires_at = time.time() + self._ttl_seconds
        with self._lock:
            self._cache[key] = CacheEntry(expires_at=expires_at, value=value)
            self._persist()


class RateLimiter:
    def __init__(self, rpm_limit: int, tpm_limit: int, rpd_limit: int, concurrency_limit: int) -> None:
        self._rpm_limit = max(1, rpm_limit)
        self._tpm_limit = max(1, tpm_limit)
        self._rpd_limit = max(0, rpd_limit)
        self._concurrency = max(1, concurrency_limit)
        self._request_tokens = float(self._rpm_limit)
        self._token_tokens = float(self._tpm_limit)
        self._last_refill = time.time()
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(self._concurrency)
        self._day = time.strftime("%Y-%m-%d")
        self._daily_requests = 0

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._request_tokens = min(self._rpm_limit, self._request_tokens + (self._rpm_limit / 60.0) * elapsed)
        self._token_tokens = min(self._tpm_limit, self._token_tokens + (self._tpm_limit / 60.0) * elapsed)
        self._last_refill = now

    def _check_daily_reset(self) -> None:
        current_day = time.strftime("%Y-%m-%d")
        if current_day != self._day:
            self._day = current_day
            self._daily_requests = 0

    @contextmanager
    def acquire(self, tokens_needed: int) -> Iterator[None]:
        if tokens_needed > self._tpm_limit:
            raise RuntimeError(
                "Estimated tokens exceed TPM limit. Reduce MAX_OUTPUT_TOKENS or prompt size."
            )
        self._semaphore.acquire()
        try:
            while True:
                with self._lock:
                    self._check_daily_reset()
                    if self._rpd_limit and self._daily_requests >= self._rpd_limit:
                        raise RuntimeError("Daily request limit exceeded (RPD_LIMIT).")
                    self._refill()
                    if self._request_tokens >= 1 and self._token_tokens >= tokens_needed:
                        self._request_tokens -= 1
                        self._token_tokens -= tokens_needed
                        self._daily_requests += 1
                        break
                    deficit_requests = max(0.0, 1 - self._request_tokens)
                    deficit_tokens = max(0.0, tokens_needed - self._token_tokens)
                wait_request = (deficit_requests / self._rpm_limit) * 60.0 if deficit_requests else 0.0
                wait_tokens = (deficit_tokens / self._tpm_limit) * 60.0 if deficit_tokens else 0.0
                wait_time = max(wait_request, wait_tokens, 0.25)
                logging.info("[LLM] Rate limit reached. Waiting %.2fs", wait_time)
                time.sleep(wait_time)
            yield
        finally:
            self._semaphore.release()


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
        self._max_prompt_chars = _parse_int_env("MAX_PROMPT_CHARS", "2000", 2000)
        self._max_retries = _parse_int_env("MAX_RETRIES", "6", 6)
        self._rpm_limit = _parse_int_env("RPM_LIMIT", DEFAULT_RPM_LIMIT, 3)
        self._tpm_limit = _parse_int_env("TPM_LIMIT", DEFAULT_TPM_LIMIT, 1000)
        self._rpd_limit = _parse_int_env("RPD_LIMIT", DEFAULT_RPD_LIMIT, 0)
        self._concurrency_limit = _parse_int_env("CONCURRENCY_LIMIT", DEFAULT_CONCURRENCY_LIMIT, 1)
        self._cache_ttl = _parse_int_env("CACHE_TTL", "3600", 3600)
        cache_path = config("CACHE_PATH", default="").strip()
        self._cache = ResponseCache(
            ttl_seconds=self._cache_ttl,
            disk_path=Path(cache_path) if cache_path else None,
        )
        self._rate_limiter = RateLimiter(
            rpm_limit=self._rpm_limit,
            tpm_limit=self._tpm_limit,
            rpd_limit=self._rpd_limit,
            concurrency_limit=self._concurrency_limit,
        )

    def _prepare_prompt(self, prompt: str) -> str:
        if len(prompt) <= self._max_prompt_chars:
            return prompt
        logging.info("[LLM] Prompt too long (%s chars). Truncating.", len(prompt))
        head = prompt[: self._max_prompt_chars // 2]
        tail = prompt[-self._max_prompt_chars // 2 :]
        return f"{head}\n...\n{tail}"

    def _cache_key(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "prompt": prompt,
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def generate_script(self, prompt: str) -> str:
        """Generate a script from a given prompt."""
        prepared_prompt = self._prepare_prompt(prompt)
        cache_key = self._cache_key(prepared_prompt)
        cached = self._cache.get(cache_key)
        if cached:
            logging.info("[LLM] Cache hit for prompt.")
            return cached

        estimated_tokens = _estimate_tokens(prepared_prompt, self._max_tokens)
        logging.info(
            "[LLM] Generating script. Estimated tokens=%s, max_output_tokens=%s",
            estimated_tokens,
            self._max_tokens,
        )
        attempt = 0
        while True:
            with self._rate_limiter.acquire(estimated_tokens):
                try:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        messages=[{"role": "user", "content": prepared_prompt}],
                        max_tokens=self._max_tokens,
                        temperature=self._temperature,
                    )
                    content = response.choices[0].message.content.strip()
                    self._cache.set(cache_key, content)
                    return content
                except RateLimitError as exc:
                    attempt += 1
                    if attempt > self._max_retries:
                        message = "OpenAI rate limit exceeded after retries."
                        logging.error("[LLM] %s", message)
                        raise RuntimeError(message) from exc
                    retry_after = None
                    if exc.response is not None:
                        retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        wait_time = float(retry_after)
                    else:
                        base = 0.5 * (2 ** (attempt - 1))
                        wait_time = base + random.uniform(0, base)
                    logging.warning(
                        "[LLM] Rate limited (429). Retrying in %.2fs (attempt %s/%s).",
                        wait_time,
                        attempt,
                        self._max_retries,
                    )
                    time.sleep(wait_time)
                except (APIConnectionError, APITimeoutError) as exc:
                    message = "OpenAI request failed due to a network timeout."
                    logging.error("[LLM] %s", message)
                    raise RuntimeError(message) from exc


def build_llm_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Extract LLM settings from a settings dictionary."""
    llm_settings = settings.get("llm", {})
    env_max_tokens = _parse_int_env("MAX_OUTPUT_TOKENS", "256", 256)
    return {
        "model": config("OPENAI_MODEL", default="gpt-4o-mini"),
        "max_tokens": int(llm_settings.get("max_tokens", env_max_tokens)),
        "temperature": llm_settings.get("temperature", 0.7),
    }
