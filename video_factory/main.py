"""Entry point for Video Factory."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.asset_manager import AssetManager
from src.llm_engine import LLMEngine, build_llm_settings
from src.pexels_client import PexelsClient
from src.tts_engine import tts_factory
from src.video_renderer import VideoRenderer


def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_settings(settings_path: Path) -> Dict[str, Any]:
    """Load YAML settings file."""
    with settings_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_channels(channels_path: Path) -> List[Dict[str, Any]]:
    """Load channels definition from JSON file."""
    with channels_path.open("r", encoding="utf-8") as file:
        return json.load(file)


async def generate_audio(
    tts_provider_name: str,
    tts_provider: Any,
    text: str,
    voice_id: str,
    output_path: Path,
) -> None:
    """Generate audio using the configured TTS provider."""
    try:
        logging.info("[TTS] Provider=%s Output=%s", tts_provider_name, output_path)
        await tts_provider.generate(text=text, voice_id=voice_id, output_path=str(output_path))
    except Exception as exc:
        logging.exception("[TTS] Failed to generate audio: %s", exc)
        raise


def build_prompt(channel_name: str, theme: str | None = None) -> str:
    """Build a default prompt for the LLM."""
    if theme:
        return f"Crie um roteiro curto e envolvente para o canal {channel_name} com foco em {theme}."
    return f"Crie um roteiro curto e envolvente para o canal {channel_name}."


async def run() -> None:
    """Run the video factory pipeline."""
    setup_logging()
    base_dir = Path(__file__).resolve().parent
    settings_path = base_dir / "config" / "settings.yaml"
    channels_path = base_dir / "config" / "channels.json"

    settings = load_settings(settings_path)
    channels = load_channels(channels_path)

    if not channels:
        logging.error("[CONFIG] No channels configured.")
        return

    channel = channels[0]
    provider_name = settings.get("tts_provider_active", "edge").lower()

    paths = settings.get("paths", {})
    asset_manager = AssetManager(
        assets_dir=paths.get("assets_dir", "./assets"),
        output_dir=paths.get("output_dir", "./output"),
        temp_dir=paths.get("temp_dir", "./temp"),
    )
    asset_manager.ensure_directories()

    assets_settings = settings.get("assets", {})
    images = asset_manager.list_images()
    if not images and assets_settings.get("auto_generate", False):
        theme = assets_settings.get("theme")
        api_key = assets_settings.get("pexels_api_key")
        per_page = assets_settings.get("pexels_per_page", 6)
        if theme and api_key:
            client = PexelsClient(api_key=api_key)
            photos = client.search_photos(query=theme, per_page=per_page)
            for index, photo in enumerate(photos, start=1):
                src = photo.get("src", {})
                image_url = src.get("large") or src.get("original")
                if not image_url:
                    continue
                filename = f"pexels_{index:02d}.jpg"
                client.download_photo(image_url, asset_manager.assets_dir / filename)
        else:
            logging.warning("[ASSETS] Auto-generate enabled but theme or API key missing.")

        images = asset_manager.list_images()

    if not images:
        logging.warning("[ASSETS] No images found. Add assets to proceed.")
        return

    llm_settings = build_llm_settings(settings)
    llm_engine = LLMEngine(**llm_settings)

    prompt = build_prompt(channel["name"], assets_settings.get("theme"))
    script_text = llm_engine.generate_script(prompt)

    tts_provider = tts_factory(str(settings_path))
    voice_id = channel.get("voice_ids", {}).get(provider_name, "")
    if not voice_id:
        raise ValueError(f"No voice ID configured for provider: {provider_name}")

    audio_path = asset_manager.build_temp_path("narration.mp3")
    await generate_audio(
        tts_provider_name=provider_name,
        tts_provider=tts_provider,
        text=script_text,
        voice_id=voice_id,
        output_path=audio_path,
    )

    video_settings = settings.get("video", {})
    renderer = VideoRenderer(
        resolution=video_settings.get("resolution", "1080p"),
        fps=video_settings.get("fps", 30),
        image_duration=video_settings.get("image_duration_seconds", 3),
    )
    output_path = asset_manager.build_output_path("final_video.mp4")
    try:
        renderer.render(images=images, audio_path=audio_path, output_path=output_path)
    except Exception as exc:
        logging.exception("[VIDEO] Failed to render video: %s", exc)
        raise


if __name__ == "__main__":
    asyncio.run(run())
