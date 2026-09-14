from mediadownloader.core.downloader import (
    DownloadEngine,
    _ProgressReporter,
    _first_stream,
    _is_container_remux_failure,
    _predict_merged_extension,
)

DASH_INFO = {
    "url": None,
    "ext": "mp4",
    "duration": 300.0,
    "requested_formats": [
        {
            "format_id": "137",
            "url": "https://cdn.example.com/v.mp4",
            "vcodec": "avc1.640028",
            "acodec": "none",
            "ext": "mp4",
            "http_headers": {"User-Agent": "test-agent", "Accept": "text/html"},
        },
        {
            "format_id": "140",
            "url": "https://cdn.example.com/a.m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "ext": "m4a",
        },
    ],
}


class _DashOnlyEngine(DownloadEngine):
    """Rejects every muxed selector; only resolves separate DASH tracks."""

    def _extract_single(self, url, selector, proxy, cookies_file, cookies_browser):
        if selector == "bestvideo+bestaudio":
            return DASH_INFO
        raise RuntimeError("format muxado indisponível")


class _MuxedEngine(DownloadEngine):
    def _extract_single(self, url, selector, proxy, cookies_file, cookies_browser):
        return {
            "url": "https://cdn.example.com/muxed.mp4",
            "ext": "mp4",
            "duration": 60.0,
            "vcodec": "avc1",
            "acodec": "mp4a",
        }


def test_first_stream_picks_the_requested_track() -> None:
    video = _first_stream(DASH_INFO["requested_formats"], video=True, audio=False)
    audio = _first_stream(DASH_INFO["requested_formats"], video=False, audio=True)
    assert video is not None and video["format_id"] == "137"
    assert audio is not None and audio["format_id"] == "140"
    assert _first_stream([], video=True, audio=False) is None
    assert _first_stream(None, video=True, audio=False) is None


def test_preview_source_uses_muxed_stream_when_available() -> None:
    source = _MuxedEngine().preview_source("https://example.com/v")
    assert source.needs_merge is False
    assert source.url == "https://cdn.example.com/muxed.mp4"
    assert source.video_url is None and source.audio_url is None


def test_preview_source_falls_back_to_separate_dash_tracks() -> None:
    source = _DashOnlyEngine().preview_source("https://example.com/v")
    assert source.needs_merge is True
    assert source.has_video is True and source.has_audio is True
    assert source.video_url == "https://cdn.example.com/v.mp4"
    assert source.audio_url == "https://cdn.example.com/a.m4a"
    assert source.headers == {"User-Agent": "test-agent", "Accept": "text/html"}
    assert source.duration == 300.0


def test_progress_reporter_bounds_large_download_event_volume() -> None:
    emitted: list[dict] = []
    now = [10.0]
    reporter = _ProgressReporter(emitted.append, clock=lambda: now[0])

    for index in range(100_001):
        reporter.emit({"status": "downloading", "progress": index / 1000})

    reporter.emit({"status": "finalizing", "progress": 99.0}, force=True)

    assert len(emitted) <= 205
    assert emitted[0]["status"] == "downloading"
    assert emitted[-1]["status"] == "finalizing"


def test_normalize_does_not_retain_large_raw_extractor_response() -> None:
    info = {
        "_type": "playlist",
        "id": "example",
        "title": "Playlist grande",
        "entries": [
            {"url": f"https://example.com/{index}", "title": f"Item {index}"}
            for index in range(500)
        ],
        "unused_large_payload": "x" * 1_000_000,
    }

    media = DownloadEngine()._normalize("https://example.com/list", info)

    assert len(media.entries) == 500
    assert media.raw == {}


def test_predict_merged_extension_adds_no_extension_for_empty() -> None:
    assert _predict_merged_extension([{}]) == "mkv"
    assert _predict_merged_extension([]) == "mkv"


def test_predict_merged_extension_keeps_family_container() -> None:
    mp4 = [{"ext": "mp4", "vcodec": "avc1"}, {"ext": "m4a", "acodec": "mp4a"}]
    webm = [{"ext": "webm", "vcodec": "vp9"}, {"ext": "opus", "acodec": "opus"}]
    assert _predict_merged_extension(mp4) == "mp4"
    assert _predict_merged_extension(webm) == "webm"


def test_predict_merged_extension_falls_back_to_mkv_for_mixed_codecs() -> None:
    mixed = [{"ext": "mp4", "vcodec": "avc1"}, {"ext": "opus", "acodec": "opus"}]
    assert _predict_merged_extension(mixed) == "mkv"


def test_container_remux_failure_detection() -> None:
    from yt_dlp.utils import DownloadError

    assert _is_container_remux_failure(
        DownloadError(
            "ERROR: Postprocessing: Failed to merge formats into webm. "
            "ffmpeg only supports VP8 and VP9 in webm"
        )
    )
    assert _is_container_remux_failure(
        DownloadError("ERROR: Postprocessing: [webm] only VP8 and VP9 are supported")
    )
    assert _is_container_remux_failure(
        DownloadError("ERROR: Postprocessing: The requested container is incompatible with the video")
    )
    assert not _is_container_remux_failure(
        DownloadError("ERROR: Unable to download webpage: 403 Forbidden")
    )
    assert not _is_container_remux_failure(DownloadError("ERROR: Video unavailable"))

