"""Interfaces for pluggable services."""
from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    """Interface for Text-to-Speech providers."""

    async def generate(self, text: str, voice_id: str, output_path: str) -> None:
        """Generate audio from text and save to output_path."""
        raise NotImplementedError
