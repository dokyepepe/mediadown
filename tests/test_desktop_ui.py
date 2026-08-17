from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QHBoxLayout, QTableWidget

from mediadownloader.services.history_service import HistoryService
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.ui.main_window import MainWindow
from mediadownloader.ui.pages.history_page import HistoryPage
from mediadownloader.ui.pages.home_page import HomePage
from mediadownloader.ui.pages.downloads_page import DownloadsPage
from mediadownloader.ui.pages.settings_page import SettingsSection
from mediadownloader.ui.theme import apply_theme
from mediadownloader.ui.widgets import SidebarButton


class FakeExtractor:
    pass


def test_settings_section_allows_a_title_without_description(qtbot) -> None:
    section = SettingsSection("Seção simples")
    qtbot.addWidget(section)

    assert section.accessibleName() == "Seção simples"


def test_main_window_uses_desktop_dimensions_and_sidebar(monkeypatch, qapp, qtbot, tmp_path: Path) -> None:
    from mediadownloader.services.secure_store import MemorySecretStore
    import mediadownloader.services.spotify_service as spotify_module
    import mediadownloader.services.update_service as update_module

    monkeypatch.setattr(spotify_module, "default_secret_store", MemorySecretStore)
    monkeypatch.setattr(update_module, "components_dir", lambda: tmp_path / "components")
    apply_theme(qapp, "light")
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    window = MainWindow(settings, HistoryService(tmp_path / "history.sqlite3"))
    qtbot.addWidget(window)
    window.show()

    assert window.size().width() >= 1100
    # Window managers may clamp the requested 780 px height to the available
    # desktop work area (for example, 700 px on a 768 px display).
    assert window.size().height() >= window.minimumHeight()
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 620
    assert window.maximumWidth() > 480
    assert len(window.nav_buttons) == 6
    assert all(isinstance(button, SidebarButton) for button in window.nav_buttons)
    assert window.nav_buttons[0].text() == "Início"
    assert window.nav_buttons[3].text() == "Configurações"
    assert window.nav_buttons[4].text() == "Arquivos do site"

    qtbot.mouseClick(window.nav_buttons[3], Qt.MouseButton.LeftButton)
    assert window.stack.currentIndex() == 3
    assert window.nav_buttons[3].isChecked()
    assert "Configurações" in window.windowTitle()
    assert window.settings_page.check_update_button.text() == "Verificar atualização"
    assert window.settings_page.rollback_ytdlp_button.isEnabled() is False
    assert window.settings_page.ytdlp_update_status.wordWrap() is True
    assert "recuperação" in window.settings_page.ytdlp_update_status.text().lower()

    state = window.settings_page.updates._load_state()
    state["pending"] = {"source": "local", "version": "2099.1.1", "path": "pending"}
    state["pending_action"] = "update"
    window.settings_page.updates._write_state(state)
    window.settings_page._update_check_finished("2099.1.1")

    assert "reinicie" in window.settings_page.ytdlp_update_status.text().lower()
    assert window.settings_page.check_update_button.isEnabled() is False


def test_home_uses_horizontal_desktop_url_actions(qapp, qtbot, tmp_path: Path) -> None:
    apply_theme(qapp, "light")
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    page = HomePage(FakeExtractor(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(page)
    page.resize(880, 640)
    page.show()

    url_layout = page.url_input.parentWidget().layout()
    assert any(
        isinstance(url_layout.itemAt(index).layout(), QHBoxLayout)
        and url_layout.itemAt(index).layout().indexOf(page.url_input) >= 0
        for index in range(url_layout.count())
    )


def test_history_is_a_desktop_table(qtbot, tmp_path: Path) -> None:
    history_page = HistoryPage(HistoryService(tmp_path / "history.sqlite3"))
    qtbot.addWidget(history_page)

    assert isinstance(history_page.table, QTableWidget)
    assert history_page.table.columnCount() == 7


def test_empty_download_state_keeps_readable_centered_width(qtbot) -> None:
    # DownloadsPage only needs these signals/properties while it builds the empty state.
    from PySide6.QtCore import QObject, Signal

    class EmptyQueue(QObject):
        item_added = Signal(object)
        item_updated = Signal(object)
        item_finished = Signal(object)
        active_count_changed = Signal(int)
        paused = False
        has_active = False
        items = {}

    page = DownloadsPage(EmptyQueue())  # type: ignore[arg-type]
    qtbot.addWidget(page)
    page.resize(900, 620)
    page.show()

    assert page.empty.content.width() >= 480
    assert page.empty.title_label.width() >= 460
    assert page.empty.subtitle_label.width() >= 460
    assert page.empty.title_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert abs(page.empty.content.geometry().center().x() - page.empty.rect().center().x()) <= 1

    page.resize(1500, 900)
    QApplication.processEvents()

    assert page.empty.content.width() >= 480
    assert abs(page.empty.content.geometry().center().x() - page.empty.rect().center().x()) <= 1


def test_fullscreen_toggle_restores_window_geometry(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    from mediadownloader.services.secure_store import MemorySecretStore
    import mediadownloader.services.spotify_service as spotify_module
    import mediadownloader.services.update_service as update_module

    monkeypatch.setattr(spotify_module, "default_secret_store", MemorySecretStore)
    monkeypatch.setattr(update_module, "components_dir", lambda: tmp_path / "components")
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    window = MainWindow(settings, HistoryService(tmp_path / "history.sqlite3"))
    qtbot.addWidget(window)
    window.setGeometry(80, 60, 1000, 680)
    window.show()
    original = QRect(window.geometry())

    assert window.fullscreen_action.shortcut() == QKeySequence("F11")
    assert window.exit_fullscreen_action.shortcut() == QKeySequence("Esc")

    window.toggle_fullscreen()
    assert window.isFullScreen()

    window.exit_fullscreen()
    qapp.processEvents()
    assert not window.isFullScreen()
    assert window.geometry() == original
