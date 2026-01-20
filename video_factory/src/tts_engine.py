"""TTS providers and factory."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict

import yaml
from decouple import config

from src.interfaces import TTSProvider

try:
    import edge_tts
except ImportError:  # pragma: no cover - runtime dependency
    edge_tts = None

try:
    from elevenlabs import generate, save, set_api_key
except ImportError:  # pragma: no cover - runtime dependency
    generate = None
    save = None
    set_api_key = None


@dataclass
class EdgeProvider:
    """Text-to-Speech provider using Edge TTS (async)."""

    async def generate(self, text: str, voice_id: str, output_path: str) -> None:
        """Generate audio using Edge TTS and save to output_path."""
        if edge_tts is None:
            raise RuntimeError("edge-tts is not installed.")

        logging.info("[TTS] Generating audio with EdgeTTS: voice=%s", voice_id)
        communicate = edge_tts.Communicate(text=text, voice=voice_id)
        await communicate.save(output_path)


@dataclass
class ElevenProvider:
    """Text-to-Speech provider using ElevenLabs (sync -> async wrapper)."""

    api_key: str

    async def generate(self, text: str, voice_id: str, output_path: str) -> None:
        """Generate audio using ElevenLabs and save to output_path."""
        if generate is None or save is None or set_api_key is None:
            raise RuntimeError("elevenlabs is not installed.")

        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured.")

        set_api_key(self.api_key)
        logging.info("[TTS] Generating audio with ElevenLabs: voice=%s", voice_id)

        def _sync_generate() -> None:
            audio = generate(text=text, voice=voice_id)
            save(audio, output_path)

        await asyncio.to_thread(_sync_generate)


def load_settings(settings_path: str) -> Dict[str, Any]:
    """Load YAML settings from a given path."""
    with open(settings_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def tts_factory(settings_path: str) -> TTSProvider:
    """Instantiate the configured TTS provider based on settings.yaml."""
    settings = load_settings(settings_path)
    provider = settings.get("tts_provider_active", "edge").lower()

    if provider == "elevenlabs":
        api_key = config("ELEVENLABS_API_KEY", default="")
        return ElevenProvider(api_key=api_key)

    return EdgeProvider()
