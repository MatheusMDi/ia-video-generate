"""Pexels API client utilities."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PexelsClient:
    """Simple Pexels API client for fetching photos."""

    def __init__(self, api_key: str) -> None:
        """Initialize the client with a Pexels API key."""
        self.api_key = api_key

    def search_photos(self, query: str, per_page: int = 6, orientation: str = "landscape") -> List[Dict]:
        """Search for photos and return the raw photo entries."""
        params = urlencode({"query": query, "per_page": per_page, "orientation": orientation})
        url = f"https://api.pexels.com/v1/search?{params}"
        request = Request(url, headers={"Authorization": self.api_key})
        logging.info("[PEXELS] Searching photos: query=%s per_page=%s", query, per_page)
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("photos", [])

    def download_photo(self, url: str, destination: Path) -> None:
        """Download a photo to the destination path."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"Authorization": self.api_key})
        with urlopen(request, timeout=60) as response:
            destination.write_bytes(response.read())
        logging.info("[PEXELS] Downloaded %s", destination)
