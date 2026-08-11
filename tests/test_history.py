from pathlib import Path

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.services.history_service import HistoryService


def test_history_round_trip(tmp_path: Path):
    service = HistoryService(tmp_path / "history.sqlite3")
    item = DownloadItem("https://example.com/a", "Título", str(tmp_path))
    item.status = DownloadStatus.COMPLETED
    item.final_file = str(tmp_path / "Título.mp4")
    service.upsert(item)
    restored = service.completed()
    assert len(restored) == 1
    assert restored[0].id == item.id
    assert restored[0].title == "Título"
    service.delete(item.id)
    assert service.list() == []

