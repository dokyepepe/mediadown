from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QScrollArea, QScroller

from mediadownloader.models import DownloadItem, DownloadStatus, MediaInfo, PlaylistEntry
from mediadownloader.services.history_service import HistoryService
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.ui.main_window import MainWindow
from mediadownloader.ui.pages.downloads_page import DownloadsPage
from mediadownloader.ui.pages.history_page import HistoryPage
from mediadownloader.ui.pages.home_page import HomePage
from mediadownloader.ui.theme import apply_theme
from mediadownloader.ui.widgets import DownloadCard


class FakeExtractor:
    pass


class QueueDouble:
    has_active = False
    paused = False

    def __init__(self) -> None:
        from PySide6.QtCore import QObject, Signal

        class Signals(QObject):
            item_added = Signal(object)
            item_updated = Signal(object)
            item_finished = Signal(object)
            active_count_changed = Signal(int)

        self.signals = Signals()
        self.item_added = self.signals.item_added
        self.item_updated = self.signals.item_updated
        self.item_finished = self.signals.item_finished
        self.active_count_changed = self.signals.active_count_changed
        self.items: dict[str, DownloadItem] = {}

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def cancel_all(self) -> None:
        pass

    def clear_completed(self) -> None:
        pass

    def cancel(self, _item_id: str) -> None:
        pass

    def retry(self, _item_id: str) -> None:
        pass

    def remove(self, _item_id: str) -> None:
        pass


def _assert_no_horizontal_scroll(page) -> None:
    for area in page.findChildren(QScrollArea):
        assert area.horizontalScrollBar().maximum() == 0


def test_home_analyzed_playlist_fits_360_pixels(qapp, qtbot, tmp_path: Path) -> None:
    apply_theme(qapp, "light")
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    page = HomePage(FakeExtractor(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(page)
    page.resize(360, 640)
    page.show()
    media = MediaInfo(
        url="https://example.com/playlist",
        title="TítuloSemEspaços" * 12,
        author="AutorSemEspaços" * 10,
        is_playlist=True,
        playlist_count=8,
        entries=[
            PlaylistEntry(f"https://example.com/{index}", f"ItemSemEspaços{index}" * 10, index)
            for index in range(1, 9)
        ],
    )
    page._analysis_complete(media)
    qtbot.wait(1)

    _assert_no_horizontal_scroll(page)
    assert page.playlist_list.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
    assert page.playlist_list.horizontalScrollBar().maximum() == 0
    scroll = page.findChild(QScrollArea)
    assert QScroller.grabbedGesture(scroll.viewport()) != 0


def test_compact_download_card_builds_with_touch_targets(qapp, qtbot, tmp_path: Path) -> None:
    apply_theme(qapp, "light")
    item = DownloadItem("https://example.com/video", "Título", str(tmp_path))
    card = DownloadCard(item)
    qtbot.addWidget(card)
    card.resize(328, card.sizeHint().height())
    card.show()
    qtbot.wait(1)

    assert card.thumbnail.width() <= card.width()
    for button in (
        card.primary_action, card.folder_button, card.copy_details_button, card.remove_button,
    ):
        assert button.minimumSizeHint().height() >= 44


def test_downloads_and_history_empty_states_fit_360_pixels(qapp, qtbot, tmp_path: Path) -> None:
    apply_theme(qapp, "light")
    downloads = DownloadsPage(QueueDouble())  # type: ignore[arg-type]
    history = HistoryPage(HistoryService(tmp_path / "history.sqlite3"))
    for page in (downloads, history):
        qtbot.addWidget(page)
        page.resize(360, 640)
        page.show()
        qtbot.wait(1)
        assert page.minimumSizeHint().width() <= 360
        _assert_no_horizontal_scroll(page)


def test_history_limits_initial_card_batch(qtbot, tmp_path: Path) -> None:
    history = HistoryService(tmp_path / "history.sqlite3")
    for index in range(75):
        item = DownloadItem("https://example.com", f"Item {index}", str(tmp_path))
        item.status = DownloadStatus.COMPLETED
        history.upsert(item)
    page = HistoryPage(history)
    qtbot.addWidget(page)

    assert len(page.cards) == 50
    assert page.more_button.isVisibleTo(page)


def test_main_window_uses_bottom_navigation(monkeypatch, qapp, qtbot, tmp_path: Path) -> None:
    from mediadownloader.services.secure_store import MemorySecretStore
    import mediadownloader.services.spotify_service as spotify_module

    monkeypatch.setattr(spotify_module, "default_secret_store", MemorySecretStore)
    apply_theme(qapp, "light")
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    window = MainWindow(settings, HistoryService(tmp_path / "history.sqlite3"))
    qtbot.addWidget(window)
    window.show()

    assert len(window.nav_buttons) == 5
    assert window.minimumWidth() <= 360
    assert window.minimumSizeHint().width() <= 360
    assert window.maximumWidth() <= 480
    assert all(button.minimumHeight() >= 44 for button in window.nav_buttons)
    for index in range(window.stack.count()):
        page = window.stack.widget(index)
        for scroll in page.findChildren(QScrollArea):
            assert QScroller.grabbedGesture(scroll.viewport()) != 0
    qtbot.mouseClick(window.nav_buttons[3], Qt.MouseButton.LeftButton)
    assert window.stack.currentIndex() == 3
    assert window.nav_buttons[3].isChecked()
    assert "Configurações" in window.windowTitle()

    queued = DownloadItem("https://example.com/retry", "Repetido", str(tmp_path))
    queued.status = DownloadStatus.QUEUED
    window.queue.items[queued.id] = queued
    window.queue.item_updated.emit(queued)
    qapp.processEvents()
    assert "1 item(ns) ativo(s)" in window.nav_buttons[1].accessibleName()


def test_history_folder_action_falls_back_to_output_path(monkeypatch, qtbot, tmp_path: Path) -> None:
    import mediadownloader.ui.pages.history_page as history_module

    calls: list[tuple[object, bool]] = []
    monkeypatch.setattr(
        history_module,
        "reveal_in_explorer",
        lambda path, select_file=False: calls.append((path, select_file)),
    )
    page = HistoryPage(HistoryService(tmp_path / "history.sqlite3"))
    qtbot.addWidget(page)
    item = DownloadItem("https://example.com", "Antigo", str(tmp_path))
    item.status = DownloadStatus.COMPLETED
    item.final_file = ""

    page._open_folder(item)

    assert calls == [(str(tmp_path), False)]
