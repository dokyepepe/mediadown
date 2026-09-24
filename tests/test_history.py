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


def _completed_item(tmp_path: Path, title: str, url: str) -> DownloadItem:
    item = DownloadItem(url, title, str(tmp_path), platform="YouTube", format="mp4", quality="1080")
    item.status = DownloadStatus.COMPLETED
    item.total_bytes = 1_024
    item.created_at = "2026-01-02T03:04:05+00:00"
    item.completed_at = "2026-01-02T03:05:00+00:00"
    item.final_file = str(tmp_path / f"{title}.mp4")
    return item


def test_to_csv_has_portuguese_headers() -> None:
    csv_text = HistoryService.to_csv([])
    lines = csv_text.strip().splitlines()
    assert lines[0] == "id,título,autor,plataforma,formato,qualidade,arquivo,tamanho_bytes,criado_em,concluído_em,url"


def test_to_csv_quotes_fields_with_separators(tmp_path: Path) -> None:
    import csv as csv_module
    from io import StringIO

    item = _completed_item(tmp_path, "Título, com vírgula", "https://example.com/v")
    csv_text = HistoryService.to_csv([item])
    rows = list(csv_module.reader(StringIO(csv_text), lineterminator="\n"))
    assert len(rows) == 2
    assert rows[1][0] == item.id
    assert rows[1][1] == "Título, com vírgula"
    assert rows[1][6] == item.final_file
    assert rows[1][7] == "1024"
    assert rows[1][9] == item.completed_at
    assert rows[1][10] == item.url


def test_to_csv_unfinished_download_reports_empty_completed_at(tmp_path: Path) -> None:
    import csv as csv_module
    from io import StringIO

    item = _completed_item(tmp_path, "Uso", "https://example.com/u")
    item.status = DownloadStatus.ERROR
    item.completed_at = None
    rows = list(csv_module.reader(StringIO(HistoryService.to_csv([item]))))
    assert rows[1][9] == ""

