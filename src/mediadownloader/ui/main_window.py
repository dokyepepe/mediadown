"""Application shell, navigation, and service composition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
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
from .icons import svg_pixmap
from .widgets import SidebarButton


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
        self.resize(1100, 720)
        self.setMinimumSize(900, 620)
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
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 20, 14, 16)
        side.setSpacing(5)
        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(7, 3, 4, 3)
        brand_layout.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setPixmap(svg_pixmap("brand", 30, "#2E8B57"))
        brand_icon.setFixedSize(34, 34)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("Media Downloader")
        brand.setObjectName("BrandName")
        brand_caption = QLabel("MÍDIA • ÁUDIO • VÍDEO")
        brand_caption.setObjectName("BrandCaption")
        brand_text.addWidget(brand)
        brand_text.addWidget(brand_caption)
        brand_layout.addWidget(brand_icon)
        brand_layout.addLayout(brand_text, 1)
        side.addWidget(brand_widget)
        side.addSpacing(14)
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
        group = QButtonGroup(self)
        for index, (label, icon_name, page) in enumerate(pages):
            button = SidebarButton(label, icon_name)
            button.clicked.connect(lambda checked=False, page_index=index: self._navigate(page_index))
            group.addButton(button)
            side.addWidget(button)
            self.stack.addWidget(page)
            if index == 0:
                button.setChecked(True)
        side.addStretch()
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("Muted")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(version)
        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.home_page.download_requested.connect(self._queue_media)
        self.home_page.configure_spotify_requested.connect(lambda: self._navigate(3))
        self.history_page.redownload_requested.connect(self._redownload)
        self.settings_page.theme_changed.connect(lambda theme: apply_theme(QApplication.instance(), theme))

    def _build_shortcuts(self) -> None:
        settings_action = QAction(self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(lambda: self._navigate(3))
        self.addAction(settings_action)

    def _navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 2:
            self.history_page.reload()

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
                author=media.author,
                thumbnail=entry.thumbnail if entry and entry.thumbnail else media.thumbnail,
                platform=media.platform,
                media_type=options.media_type,
                format=options.audio_format if options.media_type == MediaType.AUDIO else options.video_format,
                quality=(f"{options.audio_quality} kbps" if options.media_type == MediaType.AUDIO else options.video_quality),
                output_path=str(output_dir),
            )
            self.queue.add(item, item_options)
        self._navigate(1)

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
