from mediadownloader.core.downloader import DownloadEngine, _ProgressReporter


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

