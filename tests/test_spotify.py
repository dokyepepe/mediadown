"""Spotify integration tests use deterministic API doubles, never live content."""

from __future__ import annotations

import json
import threading
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from mediadownloader.core.downloader import DownloadEngine
from mediadownloader.core.extractor import MediaExtractor
from mediadownloader.models import DownloadItem, DownloadOptions, MediaInfo, PlaylistEntry
from mediadownloader.services.secure_store import MemorySecretStore
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.services.spotify_service import SpotifyService
from mediadownloader.ui.pages.home_page import HomePage
from mediadownloader.utils.errors import FriendlyError
from mediadownloader.utils.validators import is_spotify_url


CLIENT_ID = "A" * 32
PLAYLIST_ID = "37i9dQZF1DXcBWIGoYBM5M"


def _service(tmp_path) -> tuple[SpotifyService, SettingsService, MemorySecretStore]:
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("spotify.client_id", CLIENT_ID)
    store = MemorySecretStore()
    return SpotifyService(settings, store), settings, store


def test_spotify_url_recognition_and_parsing() -> None:
    urls = [
        "https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6?si=abc",
        "https://open.spotify.com/intl-pt/album/4aawyAB9vmqN3uQ7FjRGTy",
        f"https://open.spotify.com/embed/playlist/{PLAYLIST_ID}",
        "https://spotify.link/example",
    ]
    assert all(is_spotify_url(url) for url in urls)
    assert SpotifyService.parse_resource(urls[0]).kind == "track"
    assert SpotifyService.parse_resource(urls[1]).kind == "album"
    assert SpotifyService.parse_resource(urls[2]).resource_id == PLAYLIST_ID
    assert SpotifyService.parse_resource("https://example.com/track/abc") is None


def test_public_spotify_analysis_uses_oembed_without_login(tmp_path) -> None:
    service, _, _ = _service(tmp_path)

    def request(url, method="GET", headers=None, form=None):
        assert url.startswith(SpotifyService.OEMBED_URL)
        return {
            "title": "Faixa de exemplo",
            "thumbnail_url": "https://i.scdn.co/image/example",
            "iframe_url": "https://open.spotify.com/embed/track/6rqhFgbbKwnb9MLmUQDhG6",
        }

    service._request_json = request  # type: ignore[method-assign]
    media = service.analyze("https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")

    assert media.platform == "Spotify"
    assert media.title == "Faixa de exemplo"
    assert not media.download_supported
    assert not media.is_playlist
    assert media.raw["spotify"] is True


def test_authorized_playlist_imports_attributed_metadata(tmp_path) -> None:
    service, _, store = _service(tmp_path)
    store.write(json.dumps({
        "client_id": CLIENT_ID,
        "access_token": "protected-access-token",
        "refresh_token": "protected-refresh-token",
        "expires_at": int(time.time()) + 3600,
        "profile_name": "Usuário de teste",
    }))

    def request(url, method="GET", headers=None, form=None):
        if url.startswith(SpotifyService.OEMBED_URL):
            return {
                "title": "Minha playlist",
                "thumbnail_url": "https://i.scdn.co/image/playlist",
                "iframe_url": f"https://open.spotify.com/embed/playlist/{PLAYLIST_ID}",
            }
        assert headers == {"Authorization": "Bearer protected-access-token"}
        if "/items?" in url:
            return {
                "total": 42,
                "items": [{
                    "item": {
                        "type": "track",
                        "name": "Música autorizada",
                        "duration_ms": 185000,
                        "artists": [{"name": "Artista"}],
                        "album": {
                            "name": "Álbum",
                            "images": [{"url": "https://i.scdn.co/image/album"}],
                        },
                        "external_urls": {"spotify": "https://open.spotify.com/track/example"},
                    }
                }],
            }
        return {
            "name": "Minha playlist",
            "owner": {"display_name": "Usuário de teste"},
            "images": [{"url": "https://i.scdn.co/image/playlist"}],
            "external_urls": {"spotify": f"https://open.spotify.com/playlist/{PLAYLIST_ID}"},
            "items": {"total": 42},
        }

    service._request_json = request  # type: ignore[method-assign]
    media = service.analyze(f"https://open.spotify.com/playlist/{PLAYLIST_ID}")

    assert media.is_playlist
    assert media.playlist_count == 42
    assert len(media.entries) == 1
    assert media.entries[0].title == "Música autorizada"
    assert media.entries[0].author == "Artista"
    assert media.entries[0].album == "Álbum"
    assert media.raw["spotify_authenticated"] is True
    assert not media.download_supported


def test_expired_token_is_refreshed_and_remains_outside_settings(tmp_path) -> None:
    service, settings, store = _service(tmp_path)
    store.write(json.dumps({
        "client_id": CLIENT_ID,
        "access_token": "old-token",
        "refresh_token": "refresh-token",
        "expires_at": 1,
    }))

    def request(url, method="GET", headers=None, form=None):
        assert url == SpotifyService.TOKEN_URL
        assert method == "POST"
        assert form["grant_type"] == "refresh_token"
        return {"access_token": "new-token", "expires_in": 3600, "token_type": "Bearer"}

    service._request_json = request  # type: ignore[method-assign]

    assert service._access_token() == "new-token"
    assert json.loads(store.read())["refresh_token"] == "refresh-token"
    persisted_settings = settings.path.read_text(encoding="utf-8")
    assert "new-token" not in persisted_settings
    assert "refresh-token" not in persisted_settings


def test_media_extractor_routes_spotify_away_from_ytdlp() -> None:
    calls: list[str] = []

    class FakeDownloadEngine:
        def analyze(self, url, proxy="", cookies_file="", cookies_browser=""):
            calls.append("yt-dlp")
            return MediaInfo(url=url, title="Normal")

    class FakeSpotify:
        def analyze(self, url):
            calls.append("spotify")
            return MediaInfo(url=url, title="Spotify", platform="Spotify", download_supported=False)

    extractor = MediaExtractor(FakeDownloadEngine(), FakeSpotify())  # type: ignore[arg-type]
    spotify = extractor.analyze("https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")
    regular = extractor.analyze("https://example.com/video")

    assert calls == ["spotify", "yt-dlp"]
    assert not spotify.download_supported
    assert regular.download_supported


def test_download_engine_refuses_spotify_before_touching_backend(tmp_path) -> None:
    class FakeFFmpeg:
        available = True

    engine = DownloadEngine(FakeFFmpeg())  # type: ignore[arg-type]
    item = DownloadItem(
        url="https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6",
        title="Faixa",
        output_path=str(tmp_path),
    )
    options = DownloadOptions(output_dir=str(tmp_path))

    with pytest.raises(FriendlyError) as caught:
        engine.download(item, options, lambda _data: None, threading.Event())

    assert caught.value.code == "spotify_download_unsupported"
    assert list(tmp_path.iterdir()) == []


def test_spotify_result_is_metadata_only_in_home_page(qtbot, tmp_path) -> None:
    class FakeExtractor:
        pass

    page = HomePage(FakeExtractor(), SettingsService(tmp_path / "settings.json"))  # type: ignore[arg-type]
    qtbot.addWidget(page)
    media = MediaInfo(
        url="https://open.spotify.com/playlist/example",
        webpage_url="https://open.spotify.com/playlist/example",
        title="Playlist autorizada",
        author="Conta",
        platform="Spotify",
        is_playlist=True,
        playlist_count=1,
        entries=[PlaylistEntry(
            url="https://open.spotify.com/track/example",
            title="Faixa de teste",
            author="Artista de teste",
            index=1,
        )],
        download_supported=False,
        source_notice="Somente metadados.",
        raw={"spotify": True, "spotify_authenticated": True},
    )

    page._analysis_complete(media)

    assert page.options_card.isHidden()
    assert page.destination_card.isHidden()
    assert page.download_controls.isHidden()
    assert not page.spotify_frame.isHidden()
    assert page.playlist_list.count() == 1
    assert not page.playlist_list.item(0).flags() & Qt.ItemFlag.ItemIsUserCheckable

    page.playlist_list.setCurrentRow(0)
    page._copy_spotify_search()
    assert QApplication.clipboard().text() == "Faixa de teste — Artista de teste"

    queued = QSignalSpy(page.download_requested)
    page.queue_download()
    assert queued.count() == 0
