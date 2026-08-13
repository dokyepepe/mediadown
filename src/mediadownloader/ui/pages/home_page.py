"""Main analyze-and-configure workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt, QUrl, Signal
from PySide6.QtGui import (
    QAccessible, QAccessibleEvent, QDesktopServices, QDragEnterEvent, QDropEvent,
    QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from mediadownloader.core.extractor import MediaExtractor
from mediadownloader.core.workers import AnalyzeWorker
from mediadownloader.models import DownloadOptions, MediaInfo, MediaType
from mediadownloader.services import SettingsService
from mediadownloader.utils.errors import FriendlyError
from mediadownloader.utils.validators import is_valid_url, validate_url

from ..icons import set_button_icon, svg_asset_pixmap, svg_icon
from ..widgets import (
    MediaPreviewCard, PageHeader, PrimaryButton, SecondaryButton, WheelSafeComboBox,
)


class HomePage(QWidget):
    download_requested = Signal(object, object, object)
    analysis_changed = Signal(bool)
    configure_spotify_requested = Signal()

    def __init__(self, engine: MediaExtractor, settings: SettingsService) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.setAcceptDrops(True)
        self.engine = engine
        self.settings = settings
        self.pool = QThreadPool.globalInstance()
        self.media: MediaInfo | None = None
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("Page")
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(34, 28, 34, 34)
        self.layout.setSpacing(18)

        self.layout.addWidget(PageHeader(
            "Baixar mídia", "Cole o link de um vídeo, música ou playlist.", "home"
        ))

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Cole uma URL aqui...")
        self.url_input.setAccessibleName("URL da mídia")
        self.url_input.setAccessibleDescription(
            "Cole uma URL pública suportada e pressione Enter ou o botão Analisar."
        )
        self.url_input.setToolTip("Cole o endereço da mídia (Ctrl+L para focar este campo).")
        self.url_input.addAction(svg_icon("globe", 18), QLineEdit.ActionPosition.LeadingPosition)
        self.url_input.setMinimumHeight(44)
        self.url_input.returnPressed.connect(self.analyze)
        self.paste_button = SecondaryButton("Colar", icon_name="paste")
        self.paste_button.setToolTip("Colar uma URL válida da área de transferência")
        self.paste_button.clicked.connect(self.paste_url)
        self.analyze_button = PrimaryButton("ANALISAR", icon_name="analyze")
        self.analyze_button.setToolTip("Analisar a URL sem bloquear a janela")
        self.analyze_button.clicked.connect(self.analyze)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.paste_button)
        url_row.addWidget(self.analyze_button)
        self.layout.addLayout(url_row)

        self.notice = QLabel()
        self.notice.setObjectName("Notice")
        self.notice.setProperty("state", "info")
        self.notice.setAccessibleName("Mensagem do aplicativo")
        self.notice.setWordWrap(True)
        self.notice.hide()
        self.layout.addWidget(self.notice)

        self.result = QWidget()
        result_layout = QVBoxLayout(self.result)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(16)
        self.preview = MediaPreviewCard()
        result_layout.addWidget(self.preview)

        self.spotify_frame = QFrame()
        self.spotify_frame.setObjectName("Card")
        spotify_layout = QVBoxLayout(self.spotify_frame)
        spotify_layout.setContentsMargins(18, 16, 18, 18)
        spotify_layout.setSpacing(10)
        spotify_header = QHBoxLayout()
        self.spotify_logo = QLabel()
        self.spotify_logo.setObjectName("SpotifyLogo")
        self.spotify_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spotify_logo.setFixedSize(116, 42)
        self.spotify_logo.setPixmap(svg_asset_pixmap(
            "third_party/spotify/Spotify_Full_Logo_RGB_Black.svg", 92, 26
        ))
        spotify_title = QLabel("Conteúdo fornecido pelo Spotify")
        spotify_title.setObjectName("SectionTitle")
        spotify_header.addWidget(self.spotify_logo)
        spotify_header.addWidget(spotify_title)
        spotify_header.addStretch()
        self.spotify_message = QLabel()
        self.spotify_message.setObjectName("WarningText")
        self.spotify_message.setWordWrap(True)
        self.spotify_message.setAccessibleName("Limitações da integração com Spotify")
        spotify_actions = QHBoxLayout()
        self.open_spotify_button = PrimaryButton("ABRIR SPOTIFY", icon_name="external")
        self.open_spotify_button.clicked.connect(self._open_spotify)
        self.copy_spotify_button = SecondaryButton("COPIAR DADOS PARA BUSCA", icon_name="copy")
        self.copy_spotify_button.setToolTip(
            "Copia título e artista; nenhuma pesquisa ou download é iniciado automaticamente."
        )
        self.copy_spotify_button.clicked.connect(self._copy_spotify_search)
        self.configure_spotify_button = SecondaryButton("CONFIGURAR CONTA", icon_name="settings")
        self.configure_spotify_button.clicked.connect(self.configure_spotify_requested)
        spotify_actions.addWidget(self.open_spotify_button)
        spotify_actions.addWidget(self.copy_spotify_button)
        spotify_actions.addWidget(self.configure_spotify_button)
        spotify_actions.addStretch()
        spotify_layout.addLayout(spotify_header)
        spotify_layout.addWidget(self.spotify_message)
        spotify_layout.addLayout(spotify_actions)
        self.spotify_frame.hide()
        result_layout.addWidget(self.spotify_frame)

        self.playlist_frame = QFrame()
        self.playlist_frame.setObjectName("Card")
        playlist_layout = QVBoxLayout(self.playlist_frame)
        playlist_header = QHBoxLayout()
        self.playlist_title = QLabel("Itens da playlist")
        self.playlist_title.setObjectName("SectionTitle")
        self.download_current_button = QPushButton("Baixar item")
        set_button_icon(self.download_current_button, "downloads")
        self.download_current_button.setToolTip("Baixar somente o item destacado na lista")
        self.download_current_button.clicked.connect(self._queue_current_playlist_item)
        self.select_all_button = QPushButton("Incluir todos")
        set_button_icon(self.select_all_button, "check")
        self.select_all_button.clicked.connect(lambda: self._check_all(True))
        self.clear_all_button = QPushButton("Ignorar todos")
        set_button_icon(self.clear_all_button, "cancel")
        self.clear_all_button.clicked.connect(lambda: self._check_all(False))
        playlist_header.addWidget(self.playlist_title)
        playlist_header.addStretch()
        playlist_header.addWidget(self.download_current_button)
        playlist_header.addWidget(self.select_all_button)
        playlist_header.addWidget(self.clear_all_button)
        self.playlist_list = QListWidget()
        self.playlist_list.setAccessibleName("Itens da playlist")
        self.playlist_list.setAccessibleDescription(
            "Marque os itens que deseja adicionar individualmente à fila de downloads."
        )
        self.playlist_list.setMinimumHeight(120)
        self.playlist_list.setMaximumHeight(420)
        self.playlist_list.itemChanged.connect(self._update_playlist_selection)
        self.playlist_list.itemSelectionChanged.connect(self._update_playlist_selection)
        self.playlist_list.itemDoubleClicked.connect(
            lambda _item: self._queue_current_playlist_item()
        )
        playlist_layout.addLayout(playlist_header)
        playlist_layout.addWidget(self.playlist_list)
        result_layout.addWidget(self.playlist_frame)

        self.options_card = QFrame()
        self.options_card.setObjectName("Card")
        options_layout = QVBoxLayout(self.options_card)
        options_layout.setContentsMargins(18, 16, 18, 18)
        options_layout.setSpacing(14)
        type_row = QHBoxLayout()
        type_label = QLabel("Tipo de download")
        type_label.setObjectName("SectionTitle")
        self.video_button = QPushButton("VÍDEO")
        self.audio_button = QPushButton("ÁUDIO")
        self.video_button.setAccessibleName("Baixar como vídeo")
        self.audio_button.setAccessibleName("Baixar como áudio")
        set_button_icon(self.video_button, "video")
        set_button_icon(self.audio_button, "audio")
        self.type_group = QButtonGroup(self)
        for button in (self.video_button, self.audio_button):
            button.setCheckable(True)
            button.setProperty("segment", True)
            self.type_group.addButton(button)
        self.video_button.setChecked(True)
        self.type_group.buttonClicked.connect(self._toggle_media_type)
        type_row.addWidget(type_label)
        type_row.addStretch()
        type_row.addWidget(self.video_button)
        type_row.addWidget(self.audio_button)
        options_layout.addLayout(type_row)

        self.video_options = QWidget()
        video_grid = QGridLayout(self.video_options)
        video_grid.setContentsMargins(0, 0, 0, 0)
        self.video_quality = WheelSafeComboBox()
        self.video_quality.setAccessibleName("Qualidade do vídeo")
        self.video_format = WheelSafeComboBox()
        self.video_format.setAccessibleName("Formato do vídeo")
        self.video_format.addItems(["Automático", "MP4", "MKV", "WEBM"])
        self.video_quality.currentIndexChanged.connect(self._update_format_details)
        self.video_format.currentIndexChanged.connect(self._update_format_details)
        video_grid.addWidget(QLabel("Qualidade"), 0, 0)
        video_grid.addWidget(self.video_quality, 1, 0)
        video_grid.addWidget(QLabel("Formato"), 0, 1)
        video_grid.addWidget(self.video_format, 1, 1)
        self.format_details = QLabel("A melhor combinação disponível será selecionada automaticamente.")
        self.format_details.setObjectName("Muted")
        video_grid.addWidget(self.format_details, 2, 0, 1, 2)
        options_layout.addWidget(self.video_options)

        self.audio_options = QWidget()
        audio_grid = QGridLayout(self.audio_options)
        audio_grid.setContentsMargins(0, 0, 0, 0)
        self.audio_format = WheelSafeComboBox()
        self.audio_format.setAccessibleName("Formato do áudio")
        self.audio_format.addItems(["MP3", "M4A", "AAC", "OPUS", "FLAC", "WAV"])
        self.audio_quality = WheelSafeComboBox()
        self.audio_quality.setAccessibleName("Qualidade do áudio MP3")
        self.audio_quality.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        self.embed_thumbnail = QCheckBox("Incorporar capa")
        self.add_metadata = QCheckBox("Adicionar metadados")
        audio_grid.addWidget(QLabel("Formato"), 0, 0)
        audio_grid.addWidget(self.audio_format, 1, 0)
        audio_grid.addWidget(QLabel("Qualidade MP3"), 0, 1)
        audio_grid.addWidget(self.audio_quality, 1, 1)
        audio_grid.addWidget(self.embed_thumbnail, 2, 0)
        audio_grid.addWidget(self.add_metadata, 2, 1)
        self.audio_options.hide()
        options_layout.addWidget(self.audio_options)

        subtitle_grid = QGridLayout()
        self.subtitle_mode = WheelSafeComboBox()
        self.subtitle_mode.setAccessibleName("Modo de download das legendas")
        self.subtitle_mode.addItem("Não baixar", "none")
        self.subtitle_mode.addItem("Baixar legenda", "download")
        self.subtitle_mode.addItem("Incorporar ao vídeo", "embed")
        self.subtitle_language = WheelSafeComboBox()
        self.subtitle_language.setAccessibleName("Idioma da legenda")
        self.subtitle_language.addItem("Automático", "auto")
        subtitle_grid.addWidget(QLabel("Legendas"), 0, 0)
        subtitle_grid.addWidget(self.subtitle_mode, 1, 0)
        subtitle_grid.addWidget(QLabel("Idioma"), 0, 1)
        subtitle_grid.addWidget(self.subtitle_language, 1, 1)
        options_layout.addLayout(subtitle_grid)
        result_layout.addWidget(self.options_card)

        self.destination_card = QFrame()
        self.destination_card.setObjectName("Card")
        destination_layout = QVBoxLayout(self.destination_card)
        destination_title = QLabel("Destino")
        destination_title.setObjectName("SectionTitle")
        destination_row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setAccessibleName("Pasta de destino")
        self.destination.setAccessibleDescription("Pasta onde o arquivo final será salvo.")
        self.destination.setToolTip("Pasta de destino do download (Ctrl+O para escolher).")
        browse = SecondaryButton("PROCURAR", icon_name="folder")
        browse.setToolTip("Escolher a pasta de destino (Ctrl+O)")
        browse.clicked.connect(self.choose_destination)
        destination_row.addWidget(self.destination, 1)
        destination_row.addWidget(browse)
        self.playlist_folder = QCheckBox("Criar subpasta com o nome da playlist")
        destination_layout.addWidget(destination_title)
        destination_layout.addLayout(destination_row)
        destination_layout.addWidget(self.playlist_folder)
        result_layout.addWidget(self.destination_card)

        self.download_controls = QWidget()
        download_row = QHBoxLayout(self.download_controls)
        download_row.setContentsMargins(0, 0, 0, 0)
        download_row.addStretch()
        self.download_all_button = SecondaryButton("BAIXAR TUDO", icon_name="check")
        self.download_all_button.setToolTip("Adicionar todos os itens da playlist à fila")
        self.download_all_button.clicked.connect(self._queue_all_playlist_items)
        self.download_button = PrimaryButton("BAIXAR", icon_name="downloads")
        self.download_button.setMinimumWidth(180)
        self.download_button.setToolTip("Adicionar somente os itens incluídos à fila")
        self.download_button.clicked.connect(lambda: self.queue_download())
        download_row.addWidget(self.download_all_button)
        download_row.addWidget(self.download_button)
        result_layout.addWidget(self.download_controls)
        self.result.hide()
        self.layout.addWidget(self.result)
        self.layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.url_input.setFocus)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.choose_destination)

        tab_order = [
            self.url_input, self.paste_button, self.analyze_button,
            self.open_spotify_button, self.copy_spotify_button, self.configure_spotify_button,
            self.download_current_button, self.select_all_button, self.clear_all_button,
            self.playlist_list,
            self.video_button, self.audio_button, self.video_quality,
            self.video_format, self.audio_format, self.audio_quality,
            self.embed_thumbnail, self.add_metadata, self.subtitle_mode,
            self.subtitle_language, self.destination, browse,
            self.playlist_folder, self.download_all_button, self.download_button,
        ]
        for current, following in zip(tab_order, tab_order[1:]):
            QWidget.setTabOrder(current, following)

    def _load_defaults(self) -> None:
        self.destination.setText(self.settings.get("general.download_dir"))
        self.embed_thumbnail.setChecked(self.settings.get("downloads.embed_thumbnail", True))
        self.add_metadata.setChecked(self.settings.get("downloads.add_metadata", True))
        self.playlist_folder.setChecked(self.settings.get("downloads.create_playlist_folder", True))
        self.audio_format.setCurrentText(self.settings.get("downloads.audio_format", "mp3").upper())
        self.audio_quality.setCurrentText(f"{self.settings.get('downloads.audio_quality', '192')} kbps")

    def paste_url(self) -> None:
        from PySide6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if is_valid_url(text):
            self.url_input.setText(text)
            self.notice.hide()
        else:
            self._show_notice("A área de transferência não contém uma URL válida.", error=True)

    def set_detected_url(self, url: str) -> None:
        if not self.url_input.text().strip():
            self._show_notice("Link detectado na área de transferência. Use “Colar” para inseri-lo.")

    def analyze(self) -> None:
        valid, message = validate_url(self.url_input.text())
        if not valid:
            self._show_notice(message, error=True)
            return
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("ANALISANDO…")
        # Keep the URL and any existing result in place while the next link is
        # analyzed. Disabling avoids queuing stale data without making the form jump.
        self.result.setEnabled(False)
        self._show_notice("Analisando link…")
        self.analysis_changed.emit(True)
        cookie_source = self.settings.get("cookies.source", "none")
        worker = AnalyzeWorker(
            self.engine,
            self.url_input.text().strip(),
            self.settings.get("network.proxy_url", "") if self.settings.get("network.proxy_type") != "none" else "",
            self.settings.get("cookies.file", "") if cookie_source == "file" else "",
            self.settings.get("cookies.browser", "") if cookie_source == "browser" else "",
        )
        worker.signals.completed.connect(self._analysis_complete)
        worker.signals.failed.connect(self._analysis_failed)
        self.pool.start(worker)

    def _analysis_complete(self, media: MediaInfo) -> None:
        self.media = media
        self.preview.set_media(media)
        if media.download_supported:
            self._populate_quality(media)
            self._populate_subtitles(media)
        self._populate_playlist(media)
        self._configure_result_mode(media)
        self.result.setEnabled(True)
        self.result.show()
        self.notice.hide()
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("ANALISAR")
        self.result.setEnabled(True)
        self.analysis_changed.emit(False)

    def _analysis_failed(self, error: FriendlyError) -> None:
        self._show_notice(error.message, error=True)
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("ANALISAR")
        self.analysis_changed.emit(False)
        if error.details:
            self.notice.setToolTip(error.details)

    def _populate_quality(self, media: MediaInfo) -> None:
        self.video_quality.clear()
        self.video_quality.addItem("Automática (melhor disponível)", "auto")
        for height in media.available_heights:
            label = "2160p / 4K" if height == 2160 else f"{height}p"
            self.video_quality.addItem(label, str(height))
        self._update_format_details()

    def _update_format_details(self, *_: object) -> None:
        if not self.media:
            return
        selected = self.video_quality.currentData()
        height = int(selected) if selected and str(selected).isdigit() else None
        candidates = [item for item in self.media.formats if not height or item.height == height]
        if not candidates:
            self.format_details.setText("A melhor combinação disponível será selecionada automaticamente.")
            return
        video = max(candidates, key=lambda item: item.filesize or 0)
        details = []
        if video.video_codec and video.video_codec != "none":
            details.append(f"Codec: {video.video_codec}")
        if video.fps:
            details.append(f"{video.fps:g} FPS")
        if video.dynamic_range and video.dynamic_range.upper() not in {"SDR", "NONE"}:
            details.append(video.dynamic_range)
        if video.filesize:
            from mediadownloader.utils.formatting import format_bytes
            details.append(f"aprox. {format_bytes(video.filesize)}")
        self.format_details.setText("  •  ".join(details) or "A melhor combinação disponível será selecionada automaticamente.")

    def _populate_subtitles(self, media: MediaInfo) -> None:
        self.subtitle_language.clear()
        self.subtitle_language.addItem("Automático", "auto")
        official = set(media.subtitles)
        automatic = set(media.automatic_captions)
        for language in sorted(official | automatic):
            kind = "oficial" if language in official else "automática"
            self.subtitle_language.addItem(f"{language} — {kind}", language)

    def _populate_playlist(self, media: MediaInfo) -> None:
        self.playlist_list.blockSignals(True)
        self.playlist_list.clear()
        for entry in media.entries:
            author = f" — {entry.author}" if entry.author else ""
            item = QListWidgetItem(f"{entry.index:02d} — {entry.title}{author}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            if media.download_supported:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setToolTip(
                    "Marcado para baixar. Desmarque para ignorar ou destaque e use “Baixar item”."
                )
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.playlist_list.addItem(item)
        self.playlist_list.blockSignals(False)
        if self.playlist_list.count():
            self.playlist_list.setCurrentRow(0)
        visible_rows = min(max(len(media.entries), 3), 10)
        self.playlist_list.setMinimumHeight(visible_rows * 34 + 8)
        self.playlist_title.setText(
            f"Itens da playlist ({len(media.entries)})" if media.entries else "Itens da playlist"
        )
        self.playlist_frame.setVisible(bool(media.entries))
        self.select_all_button.setVisible(media.download_supported)
        self.clear_all_button.setVisible(media.download_supported)
        self.download_current_button.setVisible(media.download_supported)
        self.playlist_folder.setVisible(media.is_playlist and media.download_supported)
        self.playlist_list.setAccessibleDescription(
            "Marque os itens que deseja adicionar à fila."
            if media.download_supported
            else "Use as setas para escolher um item e copiar seus dados para uma busca manual."
        )
        self._update_playlist_selection()

    def _configure_result_mode(self, media: MediaInfo) -> None:
        spotify = bool(media.raw.get("spotify"))
        self.spotify_frame.setVisible(spotify)
        self.options_card.setVisible(media.download_supported)
        self.destination_card.setVisible(media.download_supported)
        self.download_controls.setVisible(media.download_supported)
        self.download_all_button.setVisible(media.is_playlist and media.download_supported)
        if not spotify:
            return
        message = media.source_notice
        if media.is_playlist:
            if media.entries:
                message += (
                    f" Foram importados {len(media.entries)} de {media.playlist_count or len(media.entries)} "
                    "itens autorizados para consulta."
                )
            else:
                message += (
                    " Para consultar os itens de uma playlist, conecte a conta proprietária "
                    "ou colaboradora em Configurações."
                )
        auth_error = str(media.raw.get("spotify_auth_error") or "")
        if auth_error:
            message += f" {auth_error}"
        self.spotify_message.setText(message)
        self.spotify_message.setAccessibleDescription(message)
        self.configure_spotify_button.setVisible(
            media.is_playlist and (not media.entries or bool(auth_error))
        )
        self.copy_spotify_button.setText(
            "COPIAR ITEM PARA BUSCA" if media.entries else "COPIAR DADOS PARA BUSCA"
        )
        self.copy_spotify_button.setAccessibleName(
            "Copiar item para busca" if media.entries else "Copiar dados para busca"
        )

    def _open_spotify(self) -> None:
        if self.media and self.media.webpage_url:
            QDesktopServices.openUrl(QUrl(self.media.webpage_url))

    def _copy_spotify_search(self) -> None:
        if not self.media:
            return
        title, author = self.media.title, self.media.author
        if self.media.entries and self.playlist_list.currentItem():
            entry = self.playlist_list.currentItem().data(Qt.ItemDataRole.UserRole)
            if entry:
                title, author = entry.title, entry.author
        query = " — ".join(part for part in (title, author) if part).strip()
        if not query:
            self._show_notice("Não há metadados suficientes para copiar.", error=True)
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(query)
        self._show_notice(
            "Título e artista copiados. Pesquise manualmente uma publicação autorizada e cole a nova URL."
        )

    def _check_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.playlist_list.blockSignals(True)
        for index in range(self.playlist_list.count()):
            self.playlist_list.item(index).setCheckState(state)
        self.playlist_list.blockSignals(False)
        self._update_playlist_selection()

    def _update_playlist_selection(self, *_: object) -> None:
        included = sum(
            self.playlist_list.item(index).checkState() == Qt.CheckState.Checked
            for index in range(self.playlist_list.count())
        )
        if self.media and self.media.is_playlist and self.media.download_supported:
            self.download_button.setText(f"BAIXAR SELECIONADOS ({included})")
            self.download_button.setAccessibleName(f"Baixar itens selecionados: {included}")
            self.download_button.setEnabled(included > 0)
            self.download_current_button.setEnabled(self.playlist_list.currentItem() is not None)
        else:
            self.download_button.setText("BAIXAR")
            self.download_button.setAccessibleName("Baixar mídia")
            self.download_button.setEnabled(True)

    def _queue_current_playlist_item(self) -> None:
        item = self.playlist_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Playlist", "Escolha um item da playlist.")
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self.queue_download([entry])

    def _queue_all_playlist_items(self) -> None:
        if not self.media or not self.media.entries:
            return
        self._check_all(True)
        self.queue_download(list(self.media.entries))

    def _toggle_media_type(self) -> None:
        audio = self.audio_button.isChecked()
        self.video_options.setVisible(not audio)
        self.audio_options.setVisible(audio)
        self.subtitle_mode.setEnabled(not audio)

    def choose_destination(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Escolher pasta", self.destination.text())
        if directory:
            self.destination.setText(directory)
            self.settings.set("general.download_dir", directory)

    def queue_download(self, entries_override: list | None = None) -> None:
        if not self.media:
            return
        if not self.media.download_supported:
            self._show_notice(
                "O Spotify não permite exportar este áudio. Use Abrir Spotify ou copie os dados para uma busca manual.",
                error=True,
            )
            return
        output = Path(self.destination.text()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._show_notice(f"Não foi possível usar a pasta de destino: {error}", error=True)
            return
        entries = []
        if self.media.is_playlist:
            if entries_override is not None:
                entries = list(entries_override)
            else:
                entries = [
                    self.playlist_list.item(index).data(Qt.ItemDataRole.UserRole)
                    for index in range(self.playlist_list.count())
                    if self.playlist_list.item(index).checkState() == Qt.CheckState.Checked
                ]
            if not entries:
                QMessageBox.information(self, "Playlist", "Selecione pelo menos um item.")
                return
        media_type = MediaType.AUDIO if self.audio_button.isChecked() else MediaType.VIDEO
        video_quality = self.video_quality.currentData() or "auto"
        options = DownloadOptions(
            media_type=media_type,
            video_format=self.video_format.currentText().lower().replace("automático", "auto"),
            video_quality=str(video_quality),
            audio_format=self.audio_format.currentText().lower(),
            audio_quality=self.audio_quality.currentText().split()[0],
            embed_thumbnail=self.embed_thumbnail.isChecked(),
            add_metadata=self.add_metadata.isChecked(),
            subtitle_mode=str(self.subtitle_mode.currentData()),
            subtitle_language=str(self.subtitle_language.currentData()),
            output_dir=str(output),
            filename_template=self.settings.get("filenames.template", "%(title)s.%(ext)s"),
            create_playlist_folder=self.playlist_folder.isChecked(),
            duplicate_policy=self.settings.get("downloads.duplicate_policy", "rename"),
            proxy=self.settings.get("network.proxy_url", "") if self.settings.get("network.proxy_type") != "none" else "",
            cookies_file=self.settings.get("cookies.file", "") if self.settings.get("cookies.source") == "file" else "",
            cookies_browser=self.settings.get("cookies.browser", "") if self.settings.get("cookies.source") == "browser" else "",
        )
        self.download_requested.emit(self.media, options, entries)
        amount = len(entries) if entries else 1
        self._show_notice(
            f"{amount} item(ns) adicionado(s) à fila. Acompanhe o progresso em Downloads."
        )

    def _show_notice(self, message: str, error: bool = False) -> None:
        self.notice.setProperty("state", "error" if error else "info")
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)
        self.notice.update()
        self.notice.setText(message)
        self.notice.setAccessibleDescription(message)
        self.notice.show()
        QAccessible.updateAccessibility(QAccessibleEvent(self.notice, QAccessible.Event.Alert))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText() and is_valid_url(event.mimeData().text().strip()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.url_input.setText(event.mimeData().text().strip())
        event.acceptProposedAction()
