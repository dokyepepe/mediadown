from pathlib import Path

from PySide6.QtCore import QCoreApplication

from mediadownloader.core.queue_manager import QueueManager
from mediadownloader.models import DownloadItem, DownloadOptions, DownloadStatus
from mediadownloader.services.history_service import HistoryService


class NeverRunEngine:
    def download(self, *args, **kwargs):
        raise AssertionError("A fila pausada não deve executar")


def test_paused_queue_does_not_start(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    history = HistoryService(tmp_path / "queue.sqlite3")
    queue = QueueManager(NeverRunEngine(), history, concurrency=2)  # type: ignore[arg-type]
    queue.pause()
    item = DownloadItem("https://example.com/a", "A", str(tmp_path))
    queue.add(item, DownloadOptions(output_dir=str(tmp_path)))
    assert queue.active_count == 0
    assert len(queue.pending) == 1
    queue.cancel(item.id)
    assert item.status == DownloadStatus.CANCELLED


def test_frozen_queue_ignores_invalid_status_value(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    history = HistoryService(tmp_path / "queue.sqlite3")
    queue = QueueManager(NeverRunEngine(), history, concurrency=2)  # type: ignore[arg-type]
    queue.pause()
    item = DownloadItem("https://example.com/a", "A", str(tmp_path))
    queue.add(item, DownloadOptions(output_dir=str(tmp_path)))
    queue._on_progress(item.id, {"status": "status_inexistente", "progress": 42.0})
    assert item.status == DownloadStatus.QUEUED
    assert item.progress == 42.0


def test_queue_survives_history_write_failure(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    history = HistoryService(tmp_path / "queue.sqlite3")

    class BrokenHistory(HistoryService):
        def upsert(self, item) -> None:
            raise RuntimeError("disco cheio")

    queue = QueueManager(NeverRunEngine(), BrokenHistory(tmp_path / "q2.sqlite3"), concurrency=2)  # type: ignore[arg-type]
    queue.pause()
    item = DownloadItem("https://example.com/a", "A", str(tmp_path))
    queue.add(item, DownloadOptions(output_dir=str(tmp_path)))
    assert item.status == DownloadStatus.QUEUED
    queue.cancel(item.id)
    assert item.status == DownloadStatus.CANCELLED

