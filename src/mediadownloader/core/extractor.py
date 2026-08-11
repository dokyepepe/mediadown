"""Route media analysis to the appropriate isolated extractor service."""

from __future__ import annotations

from mediadownloader.models import MediaInfo
from mediadownloader.services.spotify_service import SpotifyService
from mediadownloader.utils.validators import is_spotify_url

from .downloader import DownloadEngine


class MediaExtractor:
    """Facade that keeps provider-specific analysis out of the UI."""

    def __init__(self, download_engine: DownloadEngine, spotify: SpotifyService) -> None:
        self.download_engine = download_engine
        self.spotify = spotify

    def analyze(
        self,
        url: str,
        proxy: str = "",
        cookies_file: str = "",
        cookies_browser: str = "",
    ) -> MediaInfo:
        if is_spotify_url(url):
            return self.spotify.analyze(url)
        return self.download_engine.analyze(url, proxy, cookies_file, cookies_browser)
