"""Video rendering module using MoviePy."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips


class VideoRenderer:
    """Render videos from images and audio."""

    def __init__(self, resolution: str, fps: int, image_duration: int) -> None:
        """Initialize renderer configuration."""
        self.resolution = resolution
        self.fps = fps
        self.image_duration = image_duration

    def render(self, images: List[Path], audio_path: Path, output_path: Path) -> None:
        """Render a video from images and a narration audio file."""
        if not images:
            raise ValueError("No images available for rendering.")

        logging.info("[VIDEO] Rendering video with %d images", len(images))
        audio_clip = AudioFileClip(str(audio_path))

        clips = [
            ImageClip(str(image)).set_duration(self.image_duration)
            for image in images
        ]
        video_clip = concatenate_videoclips(clips, method="compose")
        video_clip = video_clip.set_audio(audio_clip)
        video_clip.write_videofile(
            str(output_path),
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
        )
        logging.info("[VIDEO] Video saved at %s", output_path)
