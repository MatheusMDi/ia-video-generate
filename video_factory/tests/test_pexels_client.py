import logging
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

from src.pexels_client import PexelsClient


class TestPexelsClient(TestCase):
    def setUp(self) -> None:
        self.client = PexelsClient(api_key="test-key")

    def test_search_photos_returns_empty_on_http_error(self) -> None:
        error = HTTPError("https://api.pexels.com/v1/search", 403, "Forbidden", None, None)
        with patch("src.pexels_client.urlopen", side_effect=error):
            with self.assertLogs(level=logging.WARNING) as captured:
                photos = self.client.search_photos(query="tech")
        self.assertEqual(photos, [])
        self.assertTrue(
            any("Search failed" in message for message in captured.output),
            "Expected warning log for failed search",
        )

    def test_download_photo_skips_on_http_error(self) -> None:
        error = HTTPError("https://images.pexels.com/photo.jpg", 403, "Forbidden", None, None)
        destination = Path("/tmp/pexels_test.jpg")
        if destination.exists():
            destination.unlink()
        with patch("src.pexels_client.urlopen", side_effect=error):
            with self.assertLogs(level=logging.WARNING) as captured:
                self.client.download_photo("https://images.pexels.com/photo.jpg", destination)
        self.assertFalse(destination.exists())
        self.assertTrue(
            any("Download failed" in message for message in captured.output),
            "Expected warning log for failed download",
        )

    def test_build_headers_includes_user_agent_and_auth(self) -> None:
        headers = self.client._build_headers()
        self.assertEqual(headers["Authorization"], "test-key")
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)
