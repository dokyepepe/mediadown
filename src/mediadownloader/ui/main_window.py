"""Application shell, navigation, and service composition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSizePolicy, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from mediadownloader.core import DownloadEngine, FFmpegManager, MediaExtractor, QueueManager
from mediadownloader.models import DownloadItem, DownloadOptions, DownloadStatus, MediaInfo, MediaType
from mediadownloader.services import HistoryService, SettingsService, SpotifyService
from mediadownloader.services.clipboard_service import ClipboardService
from mediadownloader.utils.filenames import sanitize_filename
from mediadownloader.utils.paths import asset_path, reveal_in_explorer
from mediadownloader.version import APP_NAME, APP_VERSION

from .pages import AboutPage, DownloadsPage, HistoryPage, HomePage, SettingsPage
from .theme import apply_theme
from .widgets import BottomNavButton, PageHeader, ThemedIconLabel


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsService, history: HistoryService) -> None:
        super().__init__()
        self.settings = settings
        self.history = history
        self.ffmpeg = FFmpegManager()
        self.engine = DownloadEngine(self.ffmpeg)
        self.spotify = SpotifyService(settings)
        self.extractor = MediaExtractor(self.engine, self.spotify)
        self.queue = QueueManager(
            self.engine, history, concurrency=settings.get("downloads.concurrent", 2), parent=self
        )
        self.setWindowTitle(APP_NAME)
        self.setAccessibleName(APP_NAME)
        self.setAccessibleDescription("Utilitário para analisar, baixar e converter mídias.")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        available_width = available.width() if available else 412
        available_height = available.height() if available else 820
        target_width = min(412, available_width)
        target_height = min(820, available_height)
        self.resize(target_width, target_height)
        self.setMinimumSize(min(360, target_width), min(480, target_height))
        self.setMaximumWidth(min(480, available_width))
        icon = QIcon(str(asset_path("app.ico")))
        if not icon.isNull():
            self.setWindowIcon(icon)
        self._build_ui()
        self._build_shortcuts()
        self.clipboard_service = ClipboardService(QApplication.clipboard())
        self.clipboard_service.url_detected.connect(self.home_page.set_detected_url)
        self.queue.item_finished.connect(self._download_finished)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("AppShell")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        app_bar = QFrame()
        app_bar.setObjectName("AppBar")
        brand_layout = QHBoxLayout(app_bar)
        brand_layout.setContentsMargins(16, 10, 16, 10)
        brand_layout.setSpacing(9)
        brand_icon = ThemedIconLabel("brand", 26)
        brand_icon.setFixedSize(30, 30)
        brand = QLabel("Media Downloader")
        brand.setObjectName("BrandName")
        brand.setMinimumWidth(0)
        brand.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        brand_layout.addWidget(brand_icon)
        brand_layout.addWidget(brand, 1)
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("AppVersion")
        brand_layout.addWidget(version)
        root.addWidget(app_bar)

        self.stack = QStackedWidget()
        self.home_page = HomePage(self.extractor, self.settings)
        self.downloads_page = DownloadsPage(self.queue)
        self.history_page = HistoryPage(self.history)
        self.settings_page = SettingsPage(self.settings, self.queue, self.ffmpeg, self.spotify)
        self.about_page = AboutPage()
        pages = [
            ("Início", "home", self.home_page),
            ("Downloads", "downloads", self.downloads_page),
            ("Histórico", "history", self.history_page),
            ("Configurações", "settings", self.settings_page),
            ("Sobre", "info", self.about_page),
        ]
        self.page_titles = [label for label, _icon, _page in pages]
        nav = QFrame()
        nav.setObjectName("BottomNav")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(0)
        group = QButtonGroup(self)
        self.nav_buttons: list[BottomNavButton] = []
        for index, (label, icon_name, page) in enumerate(pages):
            nav_label = "Ajustes" if label == "Configurações" else label
            button = BottomNavButton(nav_label, icon_name)
            button.clicked.connect(lambda checked=False, page_index=index: self._navigate(page_index))
            group.addButton(button)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button, 1)
            self.stack.addWidget(page)
            if index == 0:
                button.setChecked(True)
        root.addWidget(self.stack, 1)
        root.addWidget(nav)
        self.setCentralWidget(central)
        self.home_page.download_requested.connect(self._queue_media)
        self.home_page.configure_spotify_requested.connect(lambda: self._navigate(3))
        self.history_page.redownload_requested.connect(self._redownload)
        self.settings_page.theme_changed.connect(lambda theme: apply_theme(QApplication.instance(), theme))
        self.queue.item_added.connect(lambda _item: self._update_download_nav())
        self.queue.item_updated.connect(lambda _item: self._update_download_nav())
        self.queue.item_finished.connect(lambda _item: self._update_download_nav())
        self.queue.active_count_changed.connect(lambda _count: self._update_download_nav())
        self._update_download_nav()

    def _build_shortcuts(self) -> None:
        settings_action = QAction(self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(lambda: self._navigate(3))
        self.addAction(settings_action)

    def _navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)
            title = self.page_titles[index]
            self.setWindowTitle(f"{APP_NAME} — {title}")
            self.setAccessibleDescription(f"Seção atual: {title}.")
        if index == 2:
            self.history_page.reload()
        header = self.stack.currentWidget().findChild(PageHeader)
        if header is not None:
            header.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_download_nav(self) -> None:
        if len(self.nav_buttons) < 2:
            return
        pending = sum(not item.status.terminal for item in self.queue.items.values())
        button = self.nav_buttons[1]
        description = (
            f"Downloads, {pending} item(ns) ativo(s)." if pending else "Downloads, nenhuma atividade."
        )
        button.setAccessibleName(description)
        button.setToolTip(description)

    def _queue_media(self, media: MediaInfo, options: DownloadOptions, entries: list) -> None:
        if not media.download_supported:
            QMessageBox.information(
                self,
                "Download indisponível",
                "Esta integração fornece metadados e links oficiais, mas não permite "
                "baixar o conteúdo do Spotify.",
            )
            return
        targets = entries or [None]
        output_dir = Path(options.output_dir)
        if media.is_playlist and options.create_playlist_folder:
            output_dir = output_dir / sanitize_filename(media.title)
        for entry in targets:
            item_options = DownloadOptions.from_dict(options.to_dict())
            item_options.output_dir = str(output_dir)
            title = entry.title if entry else media.title
            url = entry.url if entry else media.webpage_url or media.url
            item = DownloadItem(
                url=url,
                title=title,
                author=entry.author if entry and entry.author else media.author,
                thumbnail=entry.thumbnail if entry and entry.thumbnail else media.thumbnail,
                platform=media.platform,
                media_type=options.media_type,
                format=options.audio_format if options.media_type == MediaType.AUDIO else options.video_format,
                quality=(f"{options.audio_quality} kbps" if options.media_type == MediaType.AUDIO else options.video_quality),
                output_path=str(output_dir),
            )
            self.queue.add(item, item_options)
        # Keep the analysis and URL visible. Downloads remain available from the
        # bottom navigation without unexpectedly replacing the form in progress.

    def _redownload(self, old: DownloadItem) -> None:
        options = DownloadOptions.from_dict(old.options)
        item = DownloadItem(
            url=old.url, title=old.title, author=old.author, thumbnail=old.thumbnail,
            platform=old.platform, media_type=old.media_type, format=old.format,
            quality=old.quality, output_path=old.output_path,
        )
        self.queue.add(item, options)
        self._navigate(1)

    def _download_finished(self, item: DownloadItem) -> None:
        self.history_page.reload()
        if item.status == DownloadStatus.COMPLETED:
            if self.settings.get("general.notifications", True) and QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.show()
                self.tray.showMessage("Download concluído", item.title, QSystemTrayIcon.MessageIcon.Information, 5000)
            if self.settings.get("general.open_folder_on_complete", False):
                reveal_in_explorer(item.final_file, select_file=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.queue.has_active and self.settings.get("general.confirm_close_active", True):
            answer = QMessageBox.question(
                self,
                "Downloads ativos",
                "Há downloads na fila. Fechar agora cancelará as operações ativas. Deseja continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.queue.cancel_all()
        event.accept()
