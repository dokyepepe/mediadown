from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from mediadownloader.core import QueueManager
from mediadownloader.core.download_gate import GateConfig
from mediadownloader.core.queue_filters import QueueFilter
from mediadownloader.models import DownloadItem, DownloadOptions, DownloadStatus
from mediadownloader.services.history_service import HistoryService
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.ui.pages.downloads_page import DownloadsPage
from mediadownloader.ui.theme import apply_theme
from mediadownloader.ui.widgets.download_card import DownloadCard
from mediadownloader.utils.errors import FriendlyError


class IdleEngine:
    """Engine stub that never downloads, so the queue stays under test control."""

    def download(self, *_args, **_kwargs):  # pragma: no cover - must not be called
        raise AssertionError("a fila não deve iniciar downloads neste teste")


def _item(title: str, output: Path, status: DownloadStatus = DownloadStatus.QUEUED) -> DownloadItem:
    return DownloadItem(
        url=f"https://example.com/{title.replace(' ', '-')}",
        title=title,
        author="Autor",
        output_path=str(output),
        platform="youtube",
        format="mp4",
        quality="720",
        status=status,
    )


@pytest.fixture
def queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QueueManager:
    monkeypatch.setenv("MEDIA_DOWNLOADER_DATA_DIR", str(tmp_path))
    manager = QueueManager(
        IdleEngine(),  # type: ignore[arg-type]
        HistoryService(tmp_path / "history.sqlite3"),
        concurrency=2,
    )
    manager.pause()
    return manager


@pytest.fixture
def page(queue: QueueManager, qapp: QApplication, qtbot) -> DownloadsPage:
    apply_theme(qapp, "light")
    widget = DownloadsPage(queue)
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    return widget


def _add(queue: QueueManager, tmp_path: Path, *titles: str) -> list[str]:
    for title in titles:
        queue.add(_item(title, tmp_path), DownloadOptions(output_dir=str(tmp_path)))
    return [item.title for item, _options in queue.pending]


def _visible_titles(page: DownloadsPage) -> list[str]:
    """Read the titles in the order the cards are laid out, skipping hidden ones."""
    return [
        page.list_layout.itemAt(index).widget().title.text()  # type: ignore[attr-defined]
        for index in range(page.list_layout.count())
        if isinstance(page.list_layout.itemAt(index).widget(), DownloadCard)
        and not page.list_layout.itemAt(index).widget().isHidden()  # type: ignore[attr-defined]
    ]


def test_page_starts_with_the_free_queue_state(page: DownloadsPage) -> None:
    assert page.cards == {}
    assert page.empty.isVisible()
    assert not page.scroll.isVisible()
    assert page.queue_summary.text() == "Fila pronta"
    assert page.pause_button.isEnabled() is False
    assert page.clear_button.isEnabled() is False


def test_chips_show_live_counts_per_filter(page: DownloadsPage, queue: QueueManager, tmp_path: Path) -> None:
    _add(queue, tmp_path, "Receita de bolo", "Musica ao vivo", "Video perdido")
    queue._on_failed(
        [item.id for item in queue.items.values()][2],
        FriendlyError("Falhou", "detalhe tecnico"),
    )

    labels = {
        mode: chip.text() for mode, chip in page.chips.items()
    }

    assert labels[QueueFilter.ALL] == "Todos · 3"
    assert labels[QueueFilter.ACTIVE] == "Em andamento · 2"
    assert labels[QueueFilter.COMPLETED] == "Concluídos · 0"
    assert labels[QueueFilter.FAILED] == "Com erro · 1"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("bolo", ["Receita de bolo"]),
        ("musica", ["Musica ao vivo"]),
        ("youtu", ["Receita de bolo", "Musica ao vivo", "Video perdido"]),
        ("inexistente", []),
    ],
)
def test_search_matches_title_author_platform_and_url(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path, query: str, expected: list[str]
) -> None:
    _add(queue, tmp_path, "Receita de bolo", "Musica ao vivo", "Video perdido")

    page.search.setText(query)

    assert _visible_titles(page) == expected


def test_search_ignores_accents_and_case(page: DownloadsPage, queue: QueueManager, tmp_path: Path) -> None:
    _add(queue, tmp_path, "Video perdido")

    page.search.setText("VIDEO")

    assert _visible_titles(page) == ["Video perdido"]


def test_filter_chip_hides_other_cards_and_explains_empty_result(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Receita de bolo", "Musica ao vivo")

    page.chips[QueueFilter.COMPLETED].click()

    assert _visible_titles(page) == []
    assert page.empty.isVisible()
    assert page.empty.title_label.text() == "Nada corresponde ao filtro"
    assert page.chips[QueueFilter.COMPLETED].isChecked()


def test_moving_a_waiting_item_updates_queue_and_visible_order(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Primeiro", "Segundo", "Terceiro")
    first_id = queue.pending[0][0].id

    assert queue.can_move(first_id, True) is False
    assert queue.can_move(first_id, False) is True
    page.cards[first_id].move_requested.emit(first_id, False)

    assert [item.title for item, _options in queue.pending] == [
        "Segundo",
        "Primeiro",
        "Terceiro",
    ]
    assert _visible_titles(page) == ["Segundo", "Primeiro", "Terceiro"]
    assert page.cards[queue.pending[0][0].id].move_up_button.isVisible() is True
    assert page.cards[queue.pending[0][0].id].move_down_button.isEnabled() is True


def test_primary_action_pauses_and_resumes_without_cancelling(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Receita de bolo")
    item_id = queue.pending[0][0].id
    card = page.cards[item_id]

    assert card.primary_action.text() == "Pausar"
    card.pause_requested.emit(item_id)

    assert queue.items[item_id].status is DownloadStatus.PAUSED
    assert card.primary_action.text() == "Continuar"
    card.resume_requested.emit(item_id)

    assert queue.items[item_id].status is DownloadStatus.QUEUED
    assert card.primary_action.text() == "Pausar"
    assert card.cancel_button.isVisible()


def test_cancel_then_retry_keeps_the_card_and_switches_actions(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Receita de bolo")
    item_id = queue.pending[0][0].id
    card = page.cards[item_id]

    card.cancel_requested.emit(item_id)

    assert queue.items[item_id].status is DownloadStatus.CANCELLED
    assert card.primary_action.text() == "Tentar novamente"
    assert card.remove_button.isVisible()
    assert card.cancel_button.isHidden()
    card.retry_requested.emit(item_id)

    assert queue.items[item_id].status is DownloadStatus.QUEUED


def test_copy_link_puts_the_url_on_the_clipboard(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Receita de bolo")
    item_id = queue.pending[0][0].id
    copied: list[tuple[str, str]] = []
    page.cards[item_id].link_copied.connect(lambda *args: copied.append(args))

    page.cards[item_id].copy_link_button.click()

    assert QApplication.clipboard().text() == queue.items[item_id].url
    assert copied == [(item_id, queue.items[item_id].url)]


def test_clear_completed_keeps_pending_items(page: DownloadsPage, queue: QueueManager, tmp_path: Path) -> None:
    _add(queue, tmp_path, "Pronto", "Pendente")
    ready_id = queue.pending[0][0].id
    queue.items[ready_id].status = DownloadStatus.COMPLETED
    queue.items[ready_id].progress = 1.0
    queue.item_updated.emit(queue.items[ready_id])
    assert page.clear_button.isEnabled()

    page.clear_button.click()

    assert ready_id not in page.cards
    assert len(page.cards) == 1


def test_banner_explains_the_blocked_gate_and_reports_release(
    page: DownloadsPage, queue: QueueManager
) -> None:
    queue.set_gate(
        GateConfig(window_enabled=True, window_start_minute=22 * 60, window_end_minute=6 * 60)
    )

    assert page.gate_banner.isVisible()
    assert "22:00" in page.gate_label.text() or "06:00" in page.gate_label.text()

    queue.gate_changed.emit(False, "")
    assert "liberada" in page.gate_label.text().lower()

    queue.gate_changed.emit(True, "fora da janela")
    assert "fora da janela" in page.gate_label.text()


def test_paused_queue_summary_mentions_pending_items(
    page: DownloadsPage, queue: QueueManager, tmp_path: Path
) -> None:
    _add(queue, tmp_path, "Primeiro", "Segundo")

    assert page.queue_summary.text() == "Fila pausada"
    assert "2 item(ns) aguardando continuação" == page.queue_caption.text()


def test_download_card_processing_states_disable_actions(tmp_path: Path) -> None:
    for status in (
        DownloadStatus.MERGING,
        DownloadStatus.CONVERTING,
        DownloadStatus.FINALIZING,
    ):
        card = DownloadCard(_item("Item", tmp_path, status))

        assert card.primary_action.text() == "Processando…"
        assert card.primary_action.isEnabled() is False
        assert "etapa atual" in card.primary_action.toolTip()
