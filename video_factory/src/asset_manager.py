"""Asset management utilities."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List


class AssetManager:
    """Manage image assets and output directories."""

    def __init__(self, assets_dir: str, output_dir: str, temp_dir: str) -> None:
        """Initialize the AssetManager with directory paths."""
        self.assets_dir = Path(assets_dir)
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)

    def ensure_directories(self) -> None:
        """Create required directories if they do not exist."""
        for directory in (self.assets_dir, self.output_dir, self.temp_dir):
            directory.mkdir(parents=True, exist_ok=True)
        logging.info("[ASSETS] Directories ensured: %s", self.assets_dir)

    def list_images(self) -> List[Path]:
        """List available images in the assets directory."""
        supported = {".png", ".jpg", ".jpeg"}
        images = [p for p in self.assets_dir.iterdir() if p.suffix.lower() in supported]
        logging.info("[ASSETS] Found %d images", len(images))
        return images

    def build_output_path(self, filename: str) -> Path:
        """Build a path within the output directory."""
        return self.output_dir / filename

    def build_temp_path(self, filename: str) -> Path:
        """Build a path within the temp directory."""
        return self.temp_dir / filename
