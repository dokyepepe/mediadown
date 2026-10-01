"""History page capabilities that came from the mobile edition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.services import HistoryService
from mediadownloader.ui.pages.history_page import (
    COLUMNS, DATE, FILE, FORMAT, ORIGIN, QUALITY, SIZE, TITLE, HistoryPage,
)


def _stored(
    history: HistoryService,
    tmp_path: Path,
    title: str,
    *,
    extension: str = "mp4",
    file_size: int = 3 * 1024 * 1024,
    minutes: int = 5,
) -> DownloadItem:
    final_file = tmp_path / f"{title.replace(' ', '_')}.{extension}"
    final_file.write_bytes(b"x" * 10)
    item = DownloadItem(
        url=f"https://example.com/{title.replace(' ', '-')}",
        title=title,
        author="Autor",
        output_path=str(tmp_path),
        platform="youtube",
        format=extension,
        quality="1080",
        status=DownloadStatus.COMPLETED,
    )
    item.final_file = str(final_file)
    item.file_size = file_size
    item.thumbnail = ""
    item.completed_at = f"2026-01-0{minutes}T03:04:05"
    history.upsert(item)
    return item


def _page(qapp, qtbot, tmp_path: Path) -> tuple[HistoryPage, HistoryService]:
    history = HistoryService(tmp_path / "history.sqlite3")
    page = HistoryPage(history)
    qtbot.addWidget(page)
    page.resize(1200, 700)
    page.show()
    return page, history


def _silent(monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    )


def test_table_shows_size_and_drops_the_useless_status_column(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)

    page.reload()

    assert [page.table.horizontalHeaderItem(index).text() for index in range(page.table.columnCount())] == COLUMNS
    assert COLUMNS[TITLE] == "Título"
    assert COLUMNS[SIZE] == "Tamanho"
    assert "Status" not in COLUMNS
    assert page.table.item(0, SIZE).text() == "3.0 MB"
    assert page.table.item(0, ORIGIN).text() == "youtube"
    assert page.table.item(0, FORMAT).text() == "MP4"
    assert page.table.item(0, QUALITY).text() == "1080"
    assert page.table.item(0, DATE).text() == "2026-01-05 03:04"
    assert page.table.item(0, FILE).text() == "Video_Alpha.mp4"


def test_size_falls_back_to_the_file_on_disk(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Sem tamanho")
    item.file_size = 0
    item.total_bytes = 0
    history.upsert(item)

    page.reload()

    assert page.table.item(0, SIZE).text() == "10 B"


def test_size_is_a_dash_when_nothing_is_known(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Sem arquivo")
    item.file_size = 0
    item.total_bytes = 0
    item.final_file = str(tmp_path / "nao-existe.mp4")
    history.upsert(item)

    page.reload()

    assert page.table.item(0, SIZE).text() == "—"


def test_checking_a_row_opens_the_selection_bar(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    _stored(history, tmp_path, "Musica Beta", extension="mp3", minutes=6)
    page.reload()

    assert page.selection_bar.isVisible() is False
    page.table.item(0, TITLE).setCheckState(Qt.CheckState.Checked)

    assert len(page.selected) == 1
    assert page.selection_bar.isVisible()
    assert page.selection_label.text() == "1 item selecionado"
    assert page.select_all_button.text() == "Selecionar todos"

    page.select_all_button.click()

    assert len(page.selected) == 2
    assert page.selection_label.text() == "2 itens selecionados"
    assert page.select_all_button.text() == "Limpar seleção"

    page.select_all_button.click()

    assert page.selected == set()
    assert page.selection_bar.isVisible() is False


def test_select_all_only_covers_the_rows_the_search_shows(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    _stored(history, tmp_path, "Musica Beta", extension="mp3", minutes=6)
    page.search.setText("alpha")

    page.select_all_button.click()

    assert len(page.selected) == 1
    assert page.table.rowCount() == 1


def test_clearing_the_selection_unchecks_every_row(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    _stored(history, tmp_path, "Musica Beta", extension="mp3", minutes=6)
    page.reload()
    page.table.item(0, TITLE).setCheckState(Qt.CheckState.Checked)
    page.table.item(1, TITLE).setCheckState(Qt.CheckState.Checked)

    page.clear_selection()

    assert page.selected == set()
    assert all(
        page.table.item(row, TITLE).checkState() is Qt.CheckState.Unchecked
        for row in range(page.table.rowCount())
    )


def test_deleting_a_selection_keeps_the_files(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    first = _stored(history, tmp_path, "Video Alpha", minutes=5)
    second = _stored(history, tmp_path, "Musica Beta", extension="mp3", minutes=6)
    page.reload()
    _silent(monkeypatch)
    page.select_all_button.click()

    page.delete_selected_button.click()

    assert page.table.rowCount() == 0
    assert history.completed() == []
    assert Path(first.final_file).exists()
    assert Path(second.final_file).exists()
    assert "arquivos continuam no computador" in page.notice.text()
    assert page.selection_bar.isVisible() is False


def test_cancelling_the_deletion_keeps_the_history(
    qapp, qtbot, tmp_path: Path, monkeypatch
) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()
    page.table.item(0, TITLE).setCheckState(Qt.CheckState.Checked)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No)
    )

    page.delete_selected_button.click()

    assert page.table.rowCount() == 1


def test_search_reports_when_nothing_matches(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()

    page.search.setText("inexistente")

    assert page.empty.isVisible()
    assert page.empty.title_label.text() == "Nada encontrado"
    assert 'Nenhum registro corresponde a "inexistente".' == page.empty.subtitle_label.text()

    page.search.setText("")

    assert page.empty.isVisible() is False


def test_rename_appends_the_extension_and_moves_the_file(
    qapp, qtbot, tmp_path: Path, monkeypatch
) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("Relatorio Anual", True)),
    )

    page._rename(page._items[item.id])

    target = tmp_path / "Relatorio Anual.mp4"
    assert target.exists()
    assert Path(item.final_file).exists() is False
    assert history.get(item.id).final_file == str(target)
    assert page.table.item(0, FILE).text() == "Relatorio Anual.mp4"
    assert page.notice.text() == "Renomeado para Relatorio Anual.mp4."


def test_rename_keeps_a_typed_extension(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("Relatorio.webm", True)),
    )

    page._rename(page._items[item.id])

    assert (tmp_path / "Relatorio.webm").exists()
    assert page.notice.text() == "Renomeado para Relatorio.webm."


def test_rename_rejects_a_blank_name(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("   ", True)),
    )

    page._rename(page._items[item.id])

    assert page.notice.text() == "Informe um nome para o arquivo."
    assert Path(item.final_file).exists()


def test_rename_of_a_missing_file_only_updates_the_row(
    qapp, qtbot, tmp_path: Path, monkeypatch
) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    Path(item.final_file).unlink()
    page.reload()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("Outro Nome", True)),
    )

    page._rename(page._items[item.id])

    assert history.get(item.id).final_file.endswith("Outro Nome.mp4")
    assert "só o nome no app" in page.notice.text()


def test_rename_reports_a_taken_destination(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    _stored(history, tmp_path, "Video Alpha", minutes=5)
    _stored(history, tmp_path, "Outro", minutes=6)
    page.reload()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("Video_Alpha.mp4", True)),
    )

    page._rename(page._items[page._row_ids[0]])

    assert "Já existe um arquivo com esse nome" in page.notice.text()
    assert page.table.rowCount() == 2


def test_share_copies_the_file_path(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()

    page._share(page._items[item.id])

    assert QApplication.clipboard().text() == item.final_file
    assert "Caminho copiado" in page.notice.text()


def test_share_warns_when_there_is_no_file(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    item.final_file = ""
    item.output_path = ""
    history.upsert(item)
    page.reload()

    page._share(page._items[item.id])

    assert page.notice.text() == "Este item não tem um arquivo para compartilhar."


def test_redownload_emits_the_requested_item(qapp, qtbot, tmp_path: Path) -> None:
    page, history = _page(qapp, qtbot, tmp_path)
    item = _stored(history, tmp_path, "Video Alpha", minutes=5)
    page.reload()
    emitted: list[DownloadItem] = []
    page.redownload_requested.connect(emitted.append)

    page.redownload_requested.emit(page._items[item.id])

    assert [entry.url for entry in emitted] == [item.url]


def test_selection_shortcuts_are_registered(qapp, qtbot, tmp_path: Path) -> None:
    page, _history = _page(qapp, qtbot, tmp_path)
    shortcuts = {action.text(): action.shortcut().toString() for action in page.actions()}

    assert shortcuts["Selecionar todos os itens visíveis"] == "Ctrl+A"
    assert shortcuts["Sair da seleção"] == "Esc"
