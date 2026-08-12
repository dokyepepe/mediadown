"""Persistent preferences and controlled component management."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from mediadownloader.core import FFmpegManager, QueueManager
from mediadownloader.services import SettingsService, SpotifyService
from mediadownloader.services.update_service import UpdateService
from mediadownloader.utils.filenames import validate_template
from mediadownloader.version import APP_VERSION

from ..icons import set_button_icon
from ..widgets import (
    PageHeader, PrimaryButton, ThemedIconLabel, WheelSafeComboBox, WheelSafeSpinBox,
    enable_touch_scrolling,
)


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class TaskWorker(QRunnable):
    def __init__(self, function) -> None:
        super().__init__()
        self.function = function
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self.function())
        except Exception as error:
            self.signals.failed.emit(str(error))


class SettingsSection(QFrame):
    def __init__(self, title: str, description: str = "", icon_name: str = "settings") -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 14, 14, 16)
        heading = QHBoxLayout()
        heading_icon = ThemedIconLabel(icon_name, 20)
        heading_icon.setFixedWidth(26)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        heading.addWidget(heading_icon)
        heading.addWidget(title_label)
        heading.addStretch()
        self.layout.addLayout(heading)
        if description:
            label = QLabel(description)
            label.setObjectName("Muted")
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.layout.addWidget(label)
        self.form = QFormLayout()
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setVerticalSpacing(9)
        self.layout.addLayout(self.form)


class SettingsPage(QWidget):
    theme_changed = Signal(str)

    def __init__(
        self,
        settings: SettingsService,
        queue: QueueManager,
        ffmpeg: FFmpegManager,
        spotify: SpotifyService,
    ) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.settings = settings
        self.queue = queue
        self.ffmpeg = ffmpeg
        self.spotify = spotify
        self.updates = UpdateService()
        self.pool = QThreadPool.globalInstance()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        enable_touch_scrolling(scroll)
        content = QWidget()
        content.setObjectName("Page")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 18, 16, 22)
        root.setSpacing(12)
        root.addWidget(PageHeader(
            "Configurações", "Preferências locais do aplicativo.", "settings"
        ))

        general = SettingsSection("Geral", icon_name="settings")
        self.language = WheelSafeComboBox(); self.language.addItem("Português (Brasil)", "pt_BR")
        self.theme = WheelSafeComboBox(); self.theme.addItem("Sistema", "system"); self.theme.addItem("Claro", "light"); self.theme.addItem("Escuro", "dark")
        self.download_dir = QLineEdit()
        directory_row = QWidget(); directory_layout = QHBoxLayout(directory_row); directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.addWidget(self.download_dir, 1)
        browse = QPushButton("Procurar"); set_button_icon(browse, "folder"); browse.clicked.connect(self._browse_download_dir); directory_layout.addWidget(browse)
        self.open_folder = QCheckBox("Abrir pasta ao concluir")
        self.notifications = QCheckBox("Mostrar notificação")
        self.confirm_close = QCheckBox("Confirmar ao fechar")
        general.form.addRow("Idioma", self.language)
        general.form.addRow("Tema", self.theme)
        general.form.addRow("Pasta padrão", directory_row)
        general.form.addRow("", self.open_folder)
        general.form.addRow("", self.notifications)
        general.form.addRow("", self.confirm_close)
        root.addWidget(general)

        downloads = SettingsSection("Downloads", icon_name="downloads")
        self.concurrent = WheelSafeSpinBox(); self.concurrent.setRange(1, 5)
        self.video_format = WheelSafeComboBox(); self.video_format.addItems(["auto", "mp4", "mkv", "webm"])
        self.video_quality = WheelSafeComboBox(); self.video_quality.addItems(["auto", "2160", "1440", "1080", "720", "480", "360"])
        self.audio_format = WheelSafeComboBox(); self.audio_format.addItems(["mp3", "m4a", "aac", "opus", "flac", "wav"])
        self.audio_quality = WheelSafeComboBox(); self.audio_quality.addItems(["128", "192", "256", "320"])
        self.embed_thumbnail = QCheckBox("Incorporar capa")
        self.add_metadata = QCheckBox("Adicionar metadados")
        downloads.form.addRow("Downloads simultâneos", self.concurrent)
        downloads.form.addRow("Formato de vídeo", self.video_format)
        downloads.form.addRow("Qualidade de vídeo", self.video_quality)
        downloads.form.addRow("Formato de áudio", self.audio_format)
        downloads.form.addRow("Qualidade MP3", self.audio_quality)
        downloads.form.addRow("", self.embed_thumbnail)
        downloads.form.addRow("", self.add_metadata)
        root.addWidget(downloads)

        filenames = SettingsSection("Nome dos arquivos", "Use campos compatíveis com o yt-dlp. Nomes inválidos no Windows são sanitizados pela engine.", "file")
        self.template_preset = WheelSafeComboBox()
        self.template_preset.addItem("Título", "%(title)s.%(ext)s")
        self.template_preset.addItem("Título - Autor", "%(title)s - %(uploader)s.%(ext)s")
        self.template_preset.addItem("Autor - Título", "%(uploader)s - %(title)s.%(ext)s")
        self.template_preset.addItem("Playlist/01 - Título", "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s")
        self.filename_template = QLineEdit()
        self.template_preset.currentIndexChanged.connect(lambda: self.filename_template.setText(str(self.template_preset.currentData())))
        self.duplicate_policy = WheelSafeComboBox(); self.duplicate_policy.addItem("Renomear automaticamente", "rename"); self.duplicate_policy.addItem("Ignorar", "skip"); self.duplicate_policy.addItem("Substituir", "overwrite")
        filenames.form.addRow("Preset", self.template_preset)
        filenames.form.addRow("Template avançado", self.filename_template)
        filenames.form.addRow("Arquivo existente", self.duplicate_policy)
        root.addWidget(filenames)

        network = SettingsSection("Rede", icon_name="globe")
        self.proxy_type = WheelSafeComboBox(); self.proxy_type.addItem("Nenhum", "none"); self.proxy_type.addItem("HTTP", "http"); self.proxy_type.addItem("HTTPS", "https"); self.proxy_type.addItem("SOCKS", "socks")
        self.proxy_url = QLineEdit(); self.proxy_url.setPlaceholderText("http://host:porta (evite credenciais no campo)")
        network.form.addRow("Proxy", self.proxy_type)
        network.form.addRow("Endereço", self.proxy_url)
        root.addWidget(network)

        cookies = SettingsSection("Cookies", "Use apenas para serviços nos quais você possui acesso legítimo. Nada é importado sem sua ação explícita.", "shield")
        self.cookie_source = WheelSafeComboBox(); self.cookie_source.addItem("Nenhum", "none"); self.cookie_source.addItem("Importar cookies.txt", "file"); self.cookie_source.addItem("Importar do navegador", "browser")
        self.cookies_file = QLineEdit()
        cookie_file_row = QWidget(); cookie_layout = QHBoxLayout(cookie_file_row); cookie_layout.setContentsMargins(0, 0, 0, 0); cookie_layout.addWidget(self.cookies_file, 1)
        self.choose_cookie = QPushButton("Escolher"); set_button_icon(self.choose_cookie, "file"); self.choose_cookie.clicked.connect(self._browse_cookies); cookie_layout.addWidget(self.choose_cookie)
        self.browser = WheelSafeComboBox(); self.browser.addItems(["chrome", "edge", "firefox", "brave", "opera", "vivaldi"])
        cookies.form.addRow("Fonte", self.cookie_source)
        cookies.form.addRow("cookies.txt", cookie_file_row)
        cookies.form.addRow("Navegador", self.browser)
        root.addWidget(cookies)

        spotify = SettingsSection(
            "Spotify",
            "Integração oficial somente para metadados e playlists que pertencem à sua conta ou nas quais você colabora. "
            "O áudio do Spotify nunca é baixado. O Client ID é público; tokens ficam protegidos no Gerenciador de Credenciais do Windows.",
            "audio",
        )
        self.spotify_client_id = QLineEdit()
        self.spotify_client_id.setPlaceholderText(
            "Client ID do aplicativo criado no Spotify Developer Dashboard"
        )
        self.spotify_client_id.setMaxLength(64)
        self.spotify_redirect = QLineEdit(SpotifyService.REDIRECT_URI)
        self.spotify_redirect.setReadOnly(True)
        self.spotify_redirect.setToolTip(
            "Cadastre exatamente este endereço nas Redirect URIs do aplicativo Spotify."
        )
        self.spotify_status = QLabel()
        self.spotify_status.setObjectName("Muted")
        spotify_actions = QWidget()
        spotify_action_layout = QVBoxLayout(spotify_actions)
        spotify_action_layout.setContentsMargins(0, 0, 0, 0)
        spotify_action_layout.setSpacing(8)
        account_actions = QVBoxLayout()
        account_actions.setContentsMargins(0, 0, 0, 0)
        self.spotify_connect = QPushButton("Conectar conta")
        set_button_icon(self.spotify_connect, "external")
        self.spotify_connect.clicked.connect(self._connect_spotify)
        self.spotify_disconnect = QPushButton("Desconectar")
        set_button_icon(self.spotify_disconnect, "cancel")
        self.spotify_disconnect.clicked.connect(self._disconnect_spotify)
        self.spotify_dashboard = QPushButton("Abrir painel")
        set_button_icon(self.spotify_dashboard, "external")
        self.spotify_dashboard.setAccessibleName("Abrir painel de desenvolvedor do Spotify")
        self.spotify_dashboard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://developer.spotify.com/dashboard"))
        )
        account_actions.addWidget(self.spotify_connect)
        account_actions.addWidget(self.spotify_disconnect)
        spotify_action_layout.addLayout(account_actions)
        spotify_action_layout.addWidget(self.spotify_dashboard)
        spotify.form.addRow("Client ID", self.spotify_client_id)
        spotify.form.addRow("Redirect URI", self.spotify_redirect)
        spotify.form.addRow("Estado", self.spotify_status)
        spotify.form.addRow("", spotify_actions)
        root.addWidget(spotify)

        components = SettingsSection("Componentes", icon_name="info")
        self.app_version = QLabel(APP_VERSION)
        self.ytdlp_version = QLabel(self.updates.current_ytdlp_version())
        self.ffmpeg_version = QLabel(self.ffmpeg.version())
        component_actions = QWidget(); action_layout = QVBoxLayout(component_actions); action_layout.setContentsMargins(0, 0, 0, 0)
        check_update = QPushButton("Verificar"); set_button_icon(check_update, "analyze"); check_update.clicked.connect(self._check_update)
        update = QPushButton("Atualizar yt-dlp"); set_button_icon(update, "downloads"); update.clicked.connect(self._update_ytdlp)
        action_layout.addWidget(check_update); action_layout.addWidget(update)
        components.form.addRow("Aplicativo", self.app_version)
        components.form.addRow("yt-dlp", self.ytdlp_version)
        components.form.addRow("FFmpeg", self.ffmpeg_version)
        components.form.addRow("", component_actions)
        root.addWidget(components)

        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        save_bar = QFrame()
        save_bar.setObjectName("StickyFooter")
        save_layout = QVBoxLayout(save_bar)
        save_layout.setContentsMargins(16, 10, 16, 10)
        self.save_button = PrimaryButton("SALVAR CONFIGURAÇÕES", icon_name="check")
        self.save_button.clicked.connect(self.save)
        save_layout.addWidget(self.save_button)
        outer.addWidget(save_bar)
        self._load()
        self.proxy_type.currentIndexChanged.connect(self._update_dependencies)
        self.cookie_source.currentIndexChanged.connect(self._update_dependencies)
        self._update_dependencies()
        self._configure_accessibility()

    def _configure_accessibility(self) -> None:
        """Add explicit names for screen readers where visual form labels are indirect."""
        controls = {
            self.language: "Idioma da interface",
            self.theme: "Tema da interface",
            self.download_dir: "Pasta padrão de downloads",
            self.concurrent: "Quantidade de downloads simultâneos",
            self.video_format: "Formato padrão de vídeo",
            self.video_quality: "Qualidade padrão de vídeo",
            self.audio_format: "Formato padrão de áudio",
            self.audio_quality: "Qualidade padrão de áudio MP3",
            self.template_preset: "Preset de nome de arquivo",
            self.filename_template: "Template avançado de nome de arquivo",
            self.duplicate_policy: "Ação para arquivo existente",
            self.proxy_type: "Tipo de proxy",
            self.proxy_url: "Endereço do proxy",
            self.cookie_source: "Fonte de cookies autorizada",
            self.cookies_file: "Caminho do arquivo cookies.txt",
            self.browser: "Navegador para importar cookies",
            self.spotify_client_id: "Client ID do Spotify",
            self.spotify_redirect: "Endereço local de retorno do Spotify",
        }
        for control, name in controls.items():
            control.setAccessibleName(name)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setMinimumWidth(0)
            checkbox.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for line_edit in self.findChildren(QLineEdit):
            line_edit.setMinimumWidth(0)
        self.theme.setToolTip("A alteração é aplicada ao salvar as configurações.")
        self.concurrent.setToolTip("A roda do mouse não altera este valor; use as setas ou digite.")

    def _update_dependencies(self, *_: object) -> None:
        proxy_enabled = self.proxy_type.currentData() != "none"
        self.proxy_url.setEnabled(proxy_enabled)
        self.proxy_url.setAccessibleDescription(
            "Endereço do proxy selecionado." if proxy_enabled else "Ative um tipo de proxy para editar."
        )
        cookie_source = self.cookie_source.currentData()
        file_enabled = cookie_source == "file"
        browser_enabled = cookie_source == "browser"
        self.cookies_file.setEnabled(file_enabled)
        self.choose_cookie.setEnabled(file_enabled)
        self.browser.setEnabled(browser_enabled)

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load(self) -> None:
        self._select_data(self.theme, self.settings.get("general.theme", "system"))
        self.download_dir.setText(self.settings.get("general.download_dir"))
        self.open_folder.setChecked(self.settings.get("general.open_folder_on_complete", False))
        self.notifications.setChecked(self.settings.get("general.notifications", True))
        self.confirm_close.setChecked(self.settings.get("general.confirm_close_active", True))
        self.concurrent.setValue(self.settings.get("downloads.concurrent", 2))
        for combo, key in ((self.video_format, "video_format"), (self.video_quality, "video_quality"), (self.audio_format, "audio_format"), (self.audio_quality, "audio_quality")):
            combo.setCurrentText(str(self.settings.get(f"downloads.{key}", combo.itemText(0))))
        self.embed_thumbnail.setChecked(self.settings.get("downloads.embed_thumbnail", True))
        self.add_metadata.setChecked(self.settings.get("downloads.add_metadata", True))
        self.filename_template.setText(self.settings.get("filenames.template", "%(title)s.%(ext)s"))
        self._select_data(self.duplicate_policy, self.settings.get("downloads.duplicate_policy", "rename"))
        self._select_data(self.proxy_type, self.settings.get("network.proxy_type", "none"))
        self.proxy_url.setText(self.settings.get("network.proxy_url", ""))
        self._select_data(self.cookie_source, self.settings.get("cookies.source", "none"))
        self.cookies_file.setText(self.settings.get("cookies.file", ""))
        self.browser.setCurrentText(self.settings.get("cookies.browser", "chrome"))
        self.spotify_client_id.setText(self.settings.get("spotify.client_id", ""))
        self._refresh_spotify_status()

    def save(self) -> None:
        valid, message = validate_template(self.filename_template.text())
        if not valid:
            QMessageBox.warning(self, "Template inválido", message)
            return
        self.settings.update_section("general", {
            "language": "pt_BR", "theme": self.theme.currentData(), "download_dir": self.download_dir.text(),
            "open_folder_on_complete": self.open_folder.isChecked(), "notifications": self.notifications.isChecked(),
            "confirm_close_active": self.confirm_close.isChecked(),
        })
        self.settings.update_section("downloads", {
            "concurrent": self.concurrent.value(), "video_format": self.video_format.currentText(),
            "video_quality": self.video_quality.currentText(), "audio_format": self.audio_format.currentText(),
            "audio_quality": self.audio_quality.currentText(), "embed_thumbnail": self.embed_thumbnail.isChecked(),
            "add_metadata": self.add_metadata.isChecked(), "duplicate_policy": self.duplicate_policy.currentData(),
        })
        self.settings.update_section("filenames", {"template": self.filename_template.text()})
        self.settings.update_section("network", {"proxy_type": self.proxy_type.currentData(), "proxy_url": self.proxy_url.text().strip()})
        self.settings.update_section("cookies", {"source": self.cookie_source.currentData(), "file": self.cookies_file.text(), "browser": self.browser.currentText()})
        self.settings.update_section("spotify", {"client_id": self.spotify_client_id.text().strip()})
        self.queue.set_concurrency(self.concurrent.value())
        self.theme_changed.emit(str(self.theme.currentData()))
        QMessageBox.information(self, "Configurações", "Configurações salvas.")

    def _connect_spotify(self) -> None:
        client_id = self.spotify_client_id.text().strip()
        if not self.spotify.valid_client_id(client_id):
            QMessageBox.warning(
                self,
                "Spotify",
                "Informe um Client ID válido. Cadastre também a Redirect URI exibida no Spotify Developer Dashboard.",
            )
            self.spotify_client_id.setFocus()
            return
        self.settings.set("spotify.client_id", client_id)
        self.spotify_connect.setEnabled(False)
        self.spotify_status.setText("Aguardando autorização no navegador…")
        worker = TaskWorker(self.spotify.authorize)
        worker.signals.done.connect(self._spotify_connected)
        worker.signals.failed.connect(self._spotify_connection_failed)
        self.pool.start(worker)

    def _spotify_connected(self, profile: object) -> None:
        self.spotify_connect.setEnabled(True)
        self._refresh_spotify_status()
        QMessageBox.information(
            self,
            "Spotify",
            f"Conta conectada como {profile}. Agora você pode analisar suas playlists autorizadas.",
        )

    def _spotify_connection_failed(self, error: str) -> None:
        self.spotify_connect.setEnabled(True)
        self._refresh_spotify_status()
        QMessageBox.warning(self, "Spotify", error)

    def _disconnect_spotify(self) -> None:
        if not self.spotify.has_authorization():
            return
        answer = QMessageBox.question(
            self,
            "Desconectar Spotify",
            "Remover a autorização armazenada neste computador?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.spotify.disconnect()
            self._refresh_spotify_status()

    def _refresh_spotify_status(self) -> None:
        connected = self.spotify.has_authorization()
        status = f"Conectado: {self.spotify.connection_name()}" if connected else "Não conectado"
        self.spotify_status.setText(status)
        self.spotify_status.setAccessibleName(f"Estado do Spotify: {status}")
        self.spotify_disconnect.setEnabled(connected)

    def _browse_download_dir(self) -> None:
        if directory := QFileDialog.getExistingDirectory(self, "Pasta padrão", self.download_dir.text()):
            self.download_dir.setText(directory)

    def _browse_cookies(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Importar cookies.txt", "", "Cookies Netscape (*.txt)")
        if filename:
            self.cookies_file.setText(filename)
            self._select_data(self.cookie_source, "file")

    def _run_task(self, function, success) -> None:
        worker = TaskWorker(function)
        worker.signals.done.connect(success)
        worker.signals.failed.connect(lambda error: QMessageBox.warning(self, "Componentes", error))
        self.pool.start(worker)

    def _check_update(self) -> None:
        self._run_task(
            self.updates.latest_ytdlp_version,
            lambda version: QMessageBox.information(self, "yt-dlp", f"Versão instalada: {self.updates.current_ytdlp_version()}\nVersão mais recente: {version}"),
        )

    def _update_ytdlp(self) -> None:
        self._run_task(
            self.updates.update_ytdlp,
            lambda version: QMessageBox.information(self, "yt-dlp", f"yt-dlp {version} instalado com verificação SHA-256. Reinicie o aplicativo para ativá-lo."),
        )
