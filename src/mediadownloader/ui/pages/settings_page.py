"""Persistent preferences and controlled component management."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTime, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea,
    QTimeEdit, QVBoxLayout, QWidget,
)

from mediadownloader.core import DownloadEngine, FFmpegManager, QueueManager
from mediadownloader.core.download_gate import GateConfig, clamp_minute, format_minute
from mediadownloader.core.site_compatibility import rows as site_rows
from mediadownloader.models import CookieCheck
from mediadownloader.services import (
    BackupError, CleanupResult, SettingsService, SpotifyService, backup_service, stats_service,
)
from mediadownloader.services.update_service import UpdateService
from mediadownloader.utils.cookie_profiles import SUPPORTED_IMPERSONATE, normalize_impersonate
from mediadownloader.utils.filenames import validate_template
from mediadownloader.utils.formatting import format_bytes
from mediadownloader.utils.proxy import validate_proxy_url
from mediadownloader.version import APP_VERSION

from ..icons import set_button_icon
from ..widgets import (
    PageHeader, PrimaryButton, SecondaryButton, ThemedIconLabel, WheelSafeComboBox,
    WheelSafeSpinBox,
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


def _check_cookies_worker(ffmpeg, source: str, file: str, browser: str):
    engine = DownloadEngine(ffmpeg)

    def run() -> CookieCheck:
        return engine.check_cookies(source, file, browser)

    return run


def _select_impersonate(combo: QComboBox, value: str) -> None:
    """Point an impersonation combo at ``value``, falling back to \"Não usar\"."""
    index = combo.findData(normalize_impersonate(value))
    combo.setCurrentIndex(index if index >= 0 else 0)


class ProfileDialog(QDialog):
    """Collect a per-site cookies.txt profile (label, hosts, file)."""

    def __init__(self, parent=None, profile: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar perfil de cookies por site" if profile else "Novo perfil de cookies por site")
        self.setAccessibleName("Editar perfil de cookies por site")
        self.resize(520, -1)
        form_widget = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(26)
        form.setVerticalSpacing(12)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Ex.: Conta principal, Conta de trabalho…")
        self.hosts_edit = QLineEdit()
        self.hosts_edit.setPlaceholderText("youtube.com, m.youtube.com")
        self.file_edit = QLineEdit()
        self.impersonate = WheelSafeComboBox()
        self.impersonate.addItem("Não usar", "")
        for name in SUPPORTED_IMPERSONATE:
            self.impersonate.addItem(name, name)
        self.impersonate.setToolTip(
            "Usa a impressão digital do navegador em requisições que falham com bot. "
            "Exige curl-cffi; quando ausente, o download segue sem a imitação."
        )
        file_row = QWidget()
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(self.file_edit, 1)
        choose_button = QPushButton("Escolher")
        set_button_icon(choose_button, "file")
        choose_button.clicked.connect(self._browse)
        file_layout.addWidget(choose_button)
        form.addRow("Nome", self.label_edit)
        form.addRow("Sites", self.hosts_edit)
        form.addRow("cookies.txt", file_row)
        form.addRow("Imitar navegador", self.impersonate)
        form_widget.addLayout(form)
        hint = QLabel(
            "Os sites podem conter domínios e subdomínios (ex.: youtube.com também cobre "
            "www.youtube.com e m.youtube.com). Este perfil tem prioridade sobre a fonte global."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form_widget.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form_widget.addWidget(buttons)
        if profile is not None:
            self.label_edit.setText(str(profile.get("label") or ""))
            self.hosts_edit.setText(", ".join(str(host) for host in profile.get("hosts") or []))
            self.file_edit.setText(str(profile.get("file") or ""))
        _select_impersonate(
            self.impersonate, str((profile or {}).get("impersonate") or "")
        )

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Selecionar cookies.txt", "", "Cookies Netscape (*.txt)"
        )
        if filename:
            self.file_edit.setText(filename)

    def accept(self) -> None:
        if not self.hosts_edit.text().strip() or not self.file_edit.text().strip():
            QMessageBox.warning(
                self,
                "Perfil de cookies por site",
                "Informe ao menos um site e um arquivo cookies.txt.",
            )
            return
        super().accept()

    def profile_data(self) -> dict:
        return {
            "id": uuid4().hex,
            "label": self.label_edit.text().strip() or "Perfil sem nome",
            "hosts": [host.strip() for host in self.hosts_edit.text().split(",") if host.strip()],
            "file": self.file_edit.text().strip(),
            "impersonate": normalize_impersonate(self.impersonate.currentData()),
        }


class SettingsSection(QFrame):
    def __init__(self, title: str, description: str = "", icon_name: str = "settings") -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setAccessibleName(title)
        if description:
            self.setAccessibleDescription(description)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 20)
        self.layout.setSpacing(13)
        heading = QHBoxLayout()
        heading.setSpacing(12)
        heading_icon = ThemedIconLabel(icon_name, 20)
        heading_icon.setObjectName("StepIcon")
        heading_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_icon.setFixedSize(40, 40)
        heading_text = QVBoxLayout()
        heading_text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        heading.addWidget(heading_icon)
        heading_text.addWidget(title_label)
        if description:
            label = QLabel(description)
            label.setObjectName("Muted")
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            heading_text.addWidget(label)
        heading.addLayout(heading_text, 1)
        self.layout.addLayout(heading)
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(26)
        self.form.setVerticalSpacing(12)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.layout.addLayout(self.form)


class SettingsPage(QWidget):
    theme_changed = Signal(str)
    storage_changed = Signal()

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
        content = QWidget()
        content.setObjectName("Page")
        root = QVBoxLayout(content)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(16)
        root.addWidget(PageHeader(
            "Configurações", "Personalize downloads, privacidade e integrações locais.", "settings"
        ))

        overview = QFrame()
        overview.setObjectName("Toolbar")
        overview_layout = QHBoxLayout(overview)
        overview_layout.setContentsMargins(16, 13, 16, 13)
        overview_layout.setSpacing(12)
        overview_icon = ThemedIconLabel("shield", 20)
        overview_icon.setObjectName("StepIcon")
        overview_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overview_icon.setFixedSize(40, 40)
        overview_text = QVBoxLayout()
        overview_text.setSpacing(1)
        overview_title = QLabel("Preferências sob seu controle")
        overview_title.setObjectName("SectionTitle")
        overview_caption = QLabel(
            "As alterações são salvas localmente e nenhuma conta é obrigatória."
        )
        overview_caption.setObjectName("Muted")
        overview_caption.setWordWrap(True)
        local_badge = QLabel("ARMAZENAMENTO LOCAL")
        local_badge.setObjectName("MetaPill")
        overview_text.addWidget(overview_title)
        overview_text.addWidget(overview_caption)
        overview_layout.addWidget(overview_icon)
        overview_layout.addLayout(overview_text, 1)
        overview_layout.addWidget(local_badge)
        root.addWidget(overview)

        general = SettingsSection(
            "Geral",
            "Aparência, destino padrão e comportamento do aplicativo.",
            "settings",
        )
        general.setProperty("accent", "true")
        self.language = WheelSafeComboBox(); self.language.addItem("Português (Brasil)", "pt_BR")
        self.theme = WheelSafeComboBox(); self.theme.addItem("Sistema", "system"); self.theme.addItem("Claro", "light"); self.theme.addItem("Escuro", "dark"); self.theme.addItem("AMOLED (preto puro)", "amoled")
        self.video_download_dir = QLineEdit()
        self.audio_download_dir = QLineEdit()
        self.site_files_download_dir = QLineEdit()
        # Compatibility alias for code that used the previous single field.
        self.download_dir = self.video_download_dir

        def make_directory_row(field: QLineEdit, title: str) -> QWidget:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(field, 1)
            button = QPushButton("Procurar")
            set_button_icon(button, "folder")
            button.clicked.connect(
                lambda _checked=False: self._browse_download_dir(field, title)
            )
            row_layout.addWidget(button)
            return row
        self.open_folder = QCheckBox("Abrir pasta ao concluir")
        self.notifications = QCheckBox("Mostrar notificação")
        self.confirm_close = QCheckBox("Confirmar antes de fechar com downloads ativos")
        general.form.addRow("Idioma", self.language)
        general.form.addRow("Tema", self.theme)
        general.form.addRow(
            "Pasta de vídeos", make_directory_row(self.video_download_dir, "Pasta de vídeos")
        )
        general.form.addRow(
            "Pasta de áudios", make_directory_row(self.audio_download_dir, "Pasta de áudios")
        )
        general.form.addRow(
            "Pasta de PDFs e imagens",
            make_directory_row(self.site_files_download_dir, "Pasta de arquivos do site"),
        )
        general.form.addRow("", self.open_folder)
        general.form.addRow("", self.notifications)
        general.form.addRow("", self.confirm_close)
        root.addWidget(general)

        downloads = SettingsSection(
            "Downloads",
            "Defina os padrões usados ao preparar uma nova mídia.",
            "downloads",
        )
        self.concurrent = WheelSafeSpinBox(); self.concurrent.setRange(1, 5)
        self.video_format = WheelSafeComboBox(); self.video_format.addItems(["auto", "mp4", "mkv", "webm"])
        self.video_quality = WheelSafeComboBox(); self.video_quality.addItems(["auto", "2160", "1440", "1080", "720", "480", "360"])
        self.audio_format = WheelSafeComboBox(); self.audio_format.addItems(["mp3", "m4a", "aac", "opus", "flac", "wav"])
        self.audio_quality = WheelSafeComboBox(); self.audio_quality.addItems(["128", "192", "256", "320"])
        self.embed_thumbnail = QCheckBox("Incorporar thumbnail/capa")
        self.add_metadata = QCheckBox("Adicionar metadados")
        downloads.form.addRow("Downloads simultâneos", self.concurrent)
        downloads.form.addRow("Formato de vídeo", self.video_format)
        downloads.form.addRow("Qualidade de vídeo", self.video_quality)
        downloads.form.addRow("Formato de áudio", self.audio_format)
        downloads.form.addRow("Qualidade MP3", self.audio_quality)
        downloads.form.addRow("", self.embed_thumbnail)
        downloads.form.addRow("", self.add_metadata)
        root.addWidget(downloads)

        queue_rules = SettingsSection(
            "Fila e agendamento",
            "A fila espera fora da sua janela de horário e para quando o disco está sem espaço.",
            "clock",
        )
        self.window_enabled = QCheckBox("Respeitar janela de horário")
        self.window_start = QTimeEdit(); self.window_start.setDisplayFormat("HH:mm")
        self.window_end = QTimeEdit(); self.window_end.setDisplayFormat("HH:mm")
        window_row = QWidget()
        window_row_layout = QHBoxLayout(window_row)
        window_row_layout.setContentsMargins(0, 0, 0, 0)
        window_row_layout.addWidget(self.window_start)
        window_row_layout.addWidget(QLabel("até"))
        window_row_layout.addWidget(self.window_end)
        window_row_layout.addStretch()
        self.window_start.setToolTip("Início da janela, no horário local.")
        self.window_end.setToolTip(
            "Fim da janela. Igual ao início significa \"sempre liberado\"."
        )
        self.minimum_free_mb = WheelSafeSpinBox()
        self.minimum_free_mb.setRange(0, 1_048_576)
        self.minimum_free_mb.setSingleStep(32)
        self.minimum_free_mb.setSuffix(" MB")
        self.minimum_free_mb.setSpecialValueText("Sem limite")
        self.minimum_free_mb.setToolTip(
            "A fila pausa sozinha quando o disco livre ficar abaixo deste valor."
        )
        self.keep_awake = QCheckBox("Impedir suspensão durante os downloads")
        self.completion_sound = QCheckBox("Tocar som ao concluir")
        self.window_enabled.toggled.connect(self._refresh_window_state)
        queue_rules.form.addRow("", self.window_enabled)
        queue_rules.form.addRow("Janela", window_row)
        queue_rules.form.addRow("Espaço livre mínimo", self.minimum_free_mb)
        queue_rules.form.addRow("", self.keep_awake)
        queue_rules.form.addRow("", self.completion_sound)
        self.gate_status_panel = QFrame()
        self.gate_status_panel.setObjectName("ComponentStatus")
        self.gate_status_panel.setProperty("state", "neutral")
        gate_status_layout = QHBoxLayout(self.gate_status_panel)
        gate_status_layout.setContentsMargins(10, 8, 10, 8)
        self.gate_status = QLabel()
        self.gate_status.setObjectName("Muted")
        self.gate_status.setWordWrap(True)
        self.gate_status.setAccessibleName("Estado atual do agendamento da fila")
        gate_status_layout.addWidget(self.gate_status, 1)
        queue_rules.form.addRow("Estado", self.gate_status_panel)
        root.addWidget(queue_rules)

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

        network = SettingsSection(
            "Rede",
            "Deixe o proxy desativado quando sua conexão não exigir configuração manual.",
            "globe",
        )
        self.proxy_type = WheelSafeComboBox(); self.proxy_type.addItem("Nenhum", "none"); self.proxy_type.addItem("HTTP", "http"); self.proxy_type.addItem("HTTPS", "https"); self.proxy_type.addItem("SOCKS", "socks")
        self.proxy_url = QLineEdit(); self.proxy_url.setPlaceholderText("http://host:porta (evite credenciais no campo)")
        self.proxy_url.editingFinished.connect(self._refresh_proxy_status)
        self.proxy_type.currentIndexChanged.connect(self._refresh_proxy_status)
        self.rate_limit = WheelSafeSpinBox(); self.rate_limit.setRange(0, 1_000_000); self.rate_limit.setSuffix(" KiB/s"); self.rate_limit.setSpecialValueText("Sem limite")
        self.rate_limit.setToolTip("Limita a velocidade de cada download. 0 (Sem limite) usa toda a banda disponível.")
        self.proxy_status = QLabel()
        self.proxy_status.setObjectName("Muted")
        self.proxy_status.setWordWrap(True)
        self.proxy_status.setProperty("state", "neutral")
        self.proxy_status.setAccessibleName("Validação do endereço de proxy")
        network.form.addRow("Proxy", self.proxy_type)
        network.form.addRow("Endereço", self.proxy_url)
        network.form.addRow("Validação", self.proxy_status)
        network.form.addRow("Limite de velocidade", self.rate_limit)
        root.addWidget(network)

        cookies = SettingsSection("Cookies", "Use apenas para serviços nos quais você possui acesso legítimo. Nada é importado sem sua ação explícita.", "shield")
        self.cookie_source = WheelSafeComboBox(); self.cookie_source.addItem("Nenhum", "none"); self.cookie_source.addItem("Importar cookies.txt", "file"); self.cookie_source.addItem("Importar do navegador", "browser")
        self.cookie_source.currentIndexChanged.connect(self._refresh_cookies_status)
        self.cookies_file = QLineEdit()
        cookie_file_row = QWidget(); cookie_layout = QHBoxLayout(cookie_file_row); cookie_layout.setContentsMargins(0, 0, 0, 0); cookie_layout.addWidget(self.cookies_file, 1)
        choose_cookie = QPushButton("Escolher"); set_button_icon(choose_cookie, "file"); choose_cookie.clicked.connect(self._browse_cookies); cookie_layout.addWidget(choose_cookie)
        self.browser = WheelSafeComboBox(); self.browser.addItems(["chrome", "edge", "firefox", "brave", "opera", "vivaldi"])
        self.impersonate = WheelSafeComboBox()
        self.impersonate.addItem("Não usar", "")
        for name in SUPPORTED_IMPERSONATE:
            self.impersonate.addItem(name, name)
        self.impersonate.setToolTip(
            "Some quando um site bloqueia o download como robô. Exige curl-cffi; "
            "sem ele, o download segue normalmente sem a imitação."
        )
        cookies.form.addRow("Fonte", self.cookie_source)
        cookies.form.addRow("cookies.txt", cookie_file_row)
        cookies.form.addRow("Navegador", self.browser)
        cookies.form.addRow("Imitar navegador", self.impersonate)
        self.cookies_status_panel = QFrame()
        self.cookies_status_panel.setObjectName("ComponentStatus")
        self.cookies_status_panel.setProperty("state", "neutral")
        cookies_status_layout = QHBoxLayout(self.cookies_status_panel)
        cookies_status_layout.setContentsMargins(10, 8, 10, 8)
        self.cookies_status = QLabel()
        self.cookies_status.setObjectName("Muted")
        self.cookies_status.setWordWrap(True)
        self.cookies_status.setAccessibleName("Estado dos cookies configurados")
        self.cookies_status.setToolTip(
            "Valida se a fonte escolhida pode ser lida. Para o navegador, feche-o "
            "durante o teste. A sessão do YouTube é reconhecida pelos cookies SID/SAPISID."
        )
        cookies_status_layout.addWidget(self.cookies_status, 1)
        self.test_cookies_button = SecondaryButton("TESTAR COOKIES", icon_name="shield")
        self.test_cookies_button.clicked.connect(self._test_cookies)
        cookies_status_layout.addWidget(self.test_cookies_button)
        cookies.form.addRow("Validação", self.cookies_status_panel)
        root.addWidget(cookies)

        profiles = SettingsSection(
            "Cookies por site",
            "Anexe arquivos cookies.txt a sites específicos. Eles são usados automaticamente "
            "ao analisar links desses sites e têm prioridade sobre a fonte global.",
            "subtitles",
        )
        self.profile_list = QListWidget()
        self.profile_list.setAccessibleName("Perfis de cookies por site")
        self.profile_list.setAccessibleDescription(
            "Cada perfil associa um arquivo cookies.txt a uma lista de sites."
        )
        self.profile_list.setMaximumHeight(200)
        self.profile_list.currentRowChanged.connect(lambda _row: self._refresh_profile_buttons())
        profiles.form.addRow(self.profile_list)
        profile_actions = QWidget()
        profile_actions_row = QHBoxLayout(profile_actions)
        profile_actions_row.setContentsMargins(0, 0, 0, 0)
        profile_actions_row.setSpacing(8)
        self.add_profile_button = SecondaryButton("Adicionar perfil", icon_name="file")
        self.add_profile_button.clicked.connect(self._add_profile)
        self.edit_profile_button = SecondaryButton("Editar perfil", icon_name="settings")
        self.edit_profile_button.clicked.connect(self._edit_profile)
        self.remove_profile_button = SecondaryButton("Remover perfil", icon_name="trash")
        self.remove_profile_button.clicked.connect(self._remove_profile)
        profile_actions_row.addWidget(self.add_profile_button)
        profile_actions_row.addWidget(self.edit_profile_button)
        profile_actions_row.addWidget(self.remove_profile_button)
        profile_actions_row.addStretch()
        profiles.form.addRow("", profile_actions)
        root.addWidget(profiles)

        storage = SettingsSection(
            "Armazenamento",
            "Totais do histórico e arquivos temporários deixados por downloads interrompidos.",
            "list",
        )
        self.stats_completed = QLabel(); self.stats_completed.setObjectName("SectionTitle")
        self.stats_downloaded = QLabel(); self.stats_downloaded.setObjectName("SectionTitle")
        self.stats_temporary = QLabel(); self.stats_temporary.setObjectName("SectionTitle")
        self.stats_free = QLabel(); self.stats_free.setObjectName("SectionTitle")
        self.stats_refresh = SecondaryButton("ATUALIZAR", icon_name="retry")
        self.stats_refresh.clicked.connect(self._refresh_stats)
        self.stats_cleanup = SecondaryButton("LIMPAR TEMPORÁRIOS", icon_name="trash")
        self.stats_cleanup.clicked.connect(self._cleanup_temporaries)
        self.stats_cleanup.setToolTip(
            "Remove apenas partes e fragmentos de transferências interrompidas. "
            "Mídias concluídas nunca são apagadas."
        )
        storage.form.addRow("Downloads concluídos", self.stats_completed)
        storage.form.addRow("Total transferido", self.stats_downloaded)
        storage.form.addRow("Temporários", self.stats_temporary)
        storage.form.addRow("Espaço livre", self.stats_free)
        storage_actions = QWidget()
        storage_actions_row = QHBoxLayout(storage_actions)
        storage_actions_row.setContentsMargins(0, 0, 0, 0)
        storage_actions_row.setSpacing(8)
        storage_actions_row.addWidget(self.stats_cleanup)
        storage_actions_row.addWidget(self.stats_refresh)
        storage_actions_row.addStretch()
        storage.form.addRow("", storage_actions)
        root.addWidget(storage)

        backup = SettingsSection(
            "Backup e restauração",
            "Leve as configurações e os perfis de cookies para outro computador em um único arquivo.",
            "file",
        )
        self.backup_status = QLabel(
            "O Spotify não é exportado: sua sessão fica protegida pelo Gerenciador de Credenciais do Windows."
        )
        self.backup_status.setObjectName("Muted")
        self.backup_status.setWordWrap(True)
        self.export_button = SecondaryButton("EXPORTAR", icon_name="downloads")
        self.export_button.clicked.connect(self._export_backup)
        self.import_button = SecondaryButton("IMPORTAR", icon_name="folder")
        self.import_button.clicked.connect(self._import_backup)
        backup_actions = QWidget()
        backup_actions_row = QHBoxLayout(backup_actions)
        backup_actions_row.setContentsMargins(0, 0, 0, 0)
        backup_actions_row.setSpacing(8)
        backup_actions_row.addWidget(self.export_button)
        backup_actions_row.addWidget(self.import_button)
        backup_actions_row.addStretch()
        backup.form.addRow(self.backup_status)
        backup.form.addRow("", backup_actions)
        root.addWidget(backup)

        sites = SettingsSection(
            "Sites compatíveis",
            "Verificado contra os extractors do yt-dlp instalado, sem acessar a rede.",
            "globe",
        )
        self.site_list = QLabel()
        self.site_list.setObjectName("Muted")
        self.site_list.setWordWrap(True)
        self.site_list.setTextFormat(Qt.TextFormat.RichText)
        self.site_list.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.site_list.setAccessibleName("Situação de cada site suportado")
        sites.form.addRow(self.site_list)
        self.refresh_sites = SecondaryButton("VERIFICAR NOVAMENTE", icon_name="retry")
        self.refresh_sites.clicked.connect(self._refresh_sites)
        sites.form.addRow("", self.refresh_sites)
        root.addWidget(sites)

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
        account_actions = QHBoxLayout()
        account_actions.setContentsMargins(0, 0, 0, 0)
        self.spotify_connect = QPushButton("Conectar conta")
        set_button_icon(self.spotify_connect, "external")
        self.spotify_connect.clicked.connect(self._connect_spotify)
        self.spotify_disconnect = QPushButton("Desconectar")
        set_button_icon(self.spotify_disconnect, "cancel")
        self.spotify_disconnect.clicked.connect(self._disconnect_spotify)
        self.spotify_dashboard = QPushButton("Abrir Developer Dashboard")
        set_button_icon(self.spotify_dashboard, "external")
        self.spotify_dashboard.setAccessibleName("Abrir painel de desenvolvedor do Spotify")
        self.spotify_dashboard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://developer.spotify.com/dashboard"))
        )
        account_actions.addWidget(self.spotify_connect)
        account_actions.addWidget(self.spotify_disconnect)
        account_actions.addStretch()
        spotify_action_layout.addLayout(account_actions)
        spotify_action_layout.addWidget(self.spotify_dashboard, 0, Qt.AlignmentFlag.AlignLeft)
        spotify.form.addRow("Client ID", self.spotify_client_id)
        spotify.form.addRow("Redirect URI", self.spotify_redirect)
        spotify.form.addRow("Estado", self.spotify_status)
        spotify.form.addRow("", spotify_actions)
        root.addWidget(spotify)

        components = SettingsSection(
            "Compatibilidade com sites",
            "O yt-dlp é preparado separadamente e validado antes da ativação. "
            "A última versão funcional fica disponível para recuperação.",
            "info",
        )
        self.app_version = QLabel(APP_VERSION)
        self.ytdlp_version = QLabel()
        self.ytdlp_previous_version = QLabel()
        self.ffmpeg_version = QLabel(self.ffmpeg.version())
        self.ytdlp_update_status = QLabel()
        self.ytdlp_update_status.setObjectName("Muted")
        self.ytdlp_update_status.setWordWrap(True)
        self.ytdlp_update_status.setMinimumWidth(0)
        self.ytdlp_status_panel = QFrame()
        self.ytdlp_status_panel.setObjectName("ComponentStatus")
        self.ytdlp_status_panel.setProperty("state", "ready")
        status_layout = QHBoxLayout(self.ytdlp_status_panel)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.addWidget(self.ytdlp_update_status, 1)
        component_actions = QWidget()
        action_rows = QVBoxLayout(component_actions)
        action_rows.setContentsMargins(0, 0, 0, 0)
        action_rows.setSpacing(8)
        update_actions = QHBoxLayout()
        self.check_update_button = QPushButton("Verificar atualização")
        set_button_icon(self.check_update_button, "analyze")
        self.check_update_button.clicked.connect(self._check_update)
        self.update_ytdlp_button = PrimaryButton("ATUALIZAR YT-DLP", icon_name="downloads")
        self.update_ytdlp_button.clicked.connect(self._update_ytdlp)
        update_actions.addWidget(self.check_update_button)
        update_actions.addWidget(self.update_ytdlp_button)
        update_actions.addStretch()
        recovery_actions = QHBoxLayout()
        self.rollback_ytdlp_button = SecondaryButton(
            "Restaurar versão de recuperação", icon_name="retry"
        )
        self.rollback_ytdlp_button.clicked.connect(self._rollback_ytdlp)
        self.cancel_ytdlp_change_button = QPushButton("Cancelar alteração pendente")
        set_button_icon(self.cancel_ytdlp_change_button, "cancel")
        self.cancel_ytdlp_change_button.clicked.connect(self._cancel_ytdlp_change)
        recovery_actions.addWidget(self.rollback_ytdlp_button)
        recovery_actions.addWidget(self.cancel_ytdlp_change_button)
        recovery_actions.addStretch()
        action_rows.addLayout(update_actions)
        action_rows.addLayout(recovery_actions)
        components.form.addRow("Aplicativo", self.app_version)
        components.form.addRow("yt-dlp em uso", self.ytdlp_version)
        components.form.addRow("Versão de recuperação", self.ytdlp_previous_version)
        components.form.addRow("FFmpeg", self.ffmpeg_version)
        components.form.addRow("Estado", self.ytdlp_status_panel)
        components.form.addRow("", component_actions)
        root.addWidget(components)

        save_bar = QFrame()
        save_bar.setObjectName("Toolbar")
        save_row = QHBoxLayout(save_bar)
        save_row.setContentsMargins(15, 12, 15, 12)
        save_hint = QLabel("Revise as preferências e aplique quando estiver pronto.")
        save_hint.setObjectName("Muted")
        save_hint.setWordWrap(True)
        self.save_button = PrimaryButton("SALVAR CONFIGURAÇÕES", icon_name="check")
        self.save_button.clicked.connect(self.save)
        save_row.addWidget(save_hint, 1)
        save_row.addWidget(self.save_button)
        root.addWidget(save_bar)
        root.addStretch()
        scroll.setWidget(content); outer.addWidget(scroll)
        self._component_busy = False
        self._available_ytdlp_version: str | None = None
        self._active_component_worker: TaskWorker | None = None
        self._cookies_worker: TaskWorker | None = None
        self._spotify_worker: TaskWorker | None = None
        self._profiles: list[dict] = []
        self._load()
        self._refresh_component_status()
        self._configure_accessibility()

    def _configure_accessibility(self) -> None:
        """Add explicit names for screen readers where visual form labels are indirect."""
        controls = {
            self.language: "Idioma da interface",
            self.theme: "Tema da interface",
            self.video_download_dir: "Pasta padrão de vídeos",
            self.audio_download_dir: "Pasta padrão de áudios",
            self.site_files_download_dir: "Pasta padrão de PDFs e imagens extraídos de sites",
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
            self.rate_limit: "Limite de velocidade de download",
            self.cookie_source: "Fonte de cookies autorizada",
            self.cookies_file: "Caminho do arquivo cookies.txt",
            self.browser: "Navegador para importar cookies",
            self.test_cookies_button: "Validar a fonte de cookies",
            self.spotify_client_id: "Client ID do Spotify",
            self.spotify_redirect: "Endereço local de retorno do Spotify",
        }
        for control, name in controls.items():
            control.setAccessibleName(name)
        self.ytdlp_update_status.setAccessibleName("Estado da atualização do yt-dlp")
        self.check_update_button.setAccessibleName("Verificar atualização do yt-dlp")
        self.update_ytdlp_button.setAccessibleName("Atualizar yt-dlp")
        self.rollback_ytdlp_button.setAccessibleName("Restaurar versão de recuperação do yt-dlp")
        self.cancel_ytdlp_change_button.setAccessibleName("Cancelar alteração pendente do yt-dlp")
        self.add_profile_button.setAccessibleName("Adicionar perfil de cookies por site")
        self.edit_profile_button.setAccessibleName("Editar perfil de cookies selecionado")
        self.remove_profile_button.setAccessibleName("Remover perfil de cookies selecionado")
        self.window_start.setAccessibleName("Início da janela de downloads")
        self.window_end.setAccessibleName("Fim da janela de downloads")
        self.minimum_free_mb.setAccessibleName("Espaço livre mínimo em megabytes")
        self.keep_awake.setAccessibleName("Impedir suspensão durante os downloads")
        self.completion_sound.setAccessibleName("Tocar som ao concluir")
        self.stats_refresh.setAccessibleName("Atualizar os totais de armazenamento")
        self.stats_cleanup.setAccessibleName("Limpar arquivos temporários")
        self.export_button.setAccessibleName("Exportar as configurações para um arquivo")
        self.import_button.setAccessibleName("Importar configurações de um arquivo de backup")
        self.refresh_sites.setAccessibleName("Verificar novamente os sites compatíveis")
        self.theme.setToolTip("A alteração é aplicada ao salvar as configurações.")
        self.concurrent.setToolTip("A roda do mouse não altera este valor; use as setas ou digite.")

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load(self) -> None:
        self._select_data(self.theme, self.settings.get("general.theme", "system"))
        legacy = self.settings.get("general.download_dir")
        self.video_download_dir.setText(self.settings.get("storage.video_dir", legacy))
        self.audio_download_dir.setText(self.settings.get("storage.audio_dir", legacy))
        self.site_files_download_dir.setText(self.settings.get("storage.site_files_dir", legacy))
        self.open_folder.setChecked(self.settings.get("general.open_folder_on_complete", False))
        self.notifications.setChecked(self.settings.get("general.notifications", True))
        self.confirm_close.setChecked(self.settings.get("general.confirm_close_active", True))
        self.concurrent.setValue(self.settings.get("downloads.concurrent", 2))
        for combo, key in ((self.video_format, "video_format"), (self.video_quality, "video_quality"), (self.audio_format, "audio_format"), (self.audio_quality, "audio_quality")):
            combo.setCurrentText(str(self.settings.get(f"downloads.{key}", combo.itemText(0))))
        self.embed_thumbnail.setChecked(self.settings.get("downloads.embed_thumbnail", True))
        self.add_metadata.setChecked(self.settings.get("downloads.add_metadata", True))
        self.window_enabled.setChecked(bool(self.settings.get("downloads.window_enabled", False)))
        self.window_start.setTime(
            QTime().addSecs(
                60 * clamp_minute(self.settings.get("downloads.window_start_minute", 0))
            )
        )
        self.window_end.setTime(
            QTime().addSecs(
                60 * clamp_minute(self.settings.get("downloads.window_end_minute", 360))
            )
        )
        self.minimum_free_mb.setValue(int(self.settings.get("downloads.minimum_free_mb", 32)))
        self.keep_awake.setChecked(bool(self.settings.get("downloads.keep_awake", False)))
        self.completion_sound.setChecked(bool(self.settings.get("downloads.completion_sound", True)))
        self._refresh_window_state()
        self.filename_template.setText(self.settings.get("filenames.template", "%(title)s.%(ext)s"))
        self._select_data(self.duplicate_policy, self.settings.get("downloads.duplicate_policy", "rename"))
        self._select_data(self.proxy_type, self.settings.get("network.proxy_type", "none"))
        self.proxy_url.setText(self.settings.get("network.proxy_url", ""))
        self.rate_limit.setValue(int(self.settings.get("network.rate_limit_kbps", 0)))
        self._select_data(self.cookie_source, self.settings.get("cookies.source", "none"))
        self.cookies_file.setText(self.settings.get("cookies.file", ""))
        self.browser.setCurrentText(self.settings.get("cookies.browser", "chrome"))
        _select_impersonate(
            self.impersonate, str(self.settings.get("cookies.impersonate") or "")
        )
        self._profiles = list(self.settings.get("cookies.profiles", []) or [])
        self._reload_profile_list()
        self.spotify_client_id.setText(self.settings.get("spotify.client_id", ""))
        self._refresh_spotify_status()
        self._refresh_cookies_status()
        self._refresh_proxy_status()
        self._refresh_gate_status()
        self._refresh_sites()

    def showEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        """Measure the download folders only when the page is actually shown.

        Walking the folders is the one expensive thing this page does, so it must
        not run while the window is still being built.
        """
        super().showEvent(event)
        self._refresh_stats()

    def save(self) -> None:
        valid, message = validate_template(self.filename_template.text())
        if not valid:
            QMessageBox.warning(self, "Template inválido", message)
            return
        valid, message = validate_proxy_url(
            str(self.proxy_type.currentData()), self.proxy_url.text()
        )
        if not valid:
            QMessageBox.warning(self, "Proxy inválido", message)
            self._refresh_proxy_status()
            return
        self.settings.update_section("general", {
            "language": "pt_BR", "theme": self.theme.currentData(),
            "download_dir": self.video_download_dir.text(),
            "open_folder_on_complete": self.open_folder.isChecked(), "notifications": self.notifications.isChecked(),
            "confirm_close_active": self.confirm_close.isChecked(),
        })
        self.settings.update_section("storage", {
            "video_dir": self.video_download_dir.text(),
            "audio_dir": self.audio_download_dir.text(),
            "site_files_dir": self.site_files_download_dir.text(),
        })
        self.settings.update_section("downloads", {
            "concurrent": self.concurrent.value(), "video_format": self.video_format.currentText(),
            "video_quality": self.video_quality.currentText(), "audio_format": self.audio_format.currentText(),
            "audio_quality": self.audio_quality.currentText(), "embed_thumbnail": self.embed_thumbnail.isChecked(),
            "add_metadata": self.add_metadata.isChecked(), "duplicate_policy": self.duplicate_policy.currentData(),
            "window_enabled": self.window_enabled.isChecked(),
            "window_start_minute": self.window_start.time().hour() * 60 + self.window_start.time().minute(),
            "window_end_minute": self.window_end.time().hour() * 60 + self.window_end.time().minute(),
            "minimum_free_mb": self.minimum_free_mb.value(),
            "keep_awake": self.keep_awake.isChecked(),
            "completion_sound": self.completion_sound.isChecked(),
        })
        self.settings.update_section("filenames", {"template": self.filename_template.text()})
        self.settings.update_section("network", {"proxy_type": self.proxy_type.currentData(), "proxy_url": self.proxy_url.text().strip(), "rate_limit_kbps": self.rate_limit.value()})
        self.settings.update_section("cookies", {
            "source": self.cookie_source.currentData(), "file": self.cookies_file.text(),
            "browser": self.browser.currentText(),
            "impersonate": normalize_impersonate(self.impersonate.currentData()),
            "profiles": list(self._profiles),
        })
        self.settings.update_section("spotify", {"client_id": self.spotify_client_id.text().strip()})
        self.queue.set_concurrency(self.concurrent.value())
        self._apply_gate()
        self.theme_changed.emit(str(self.theme.currentData()))
        self.storage_changed.emit()
        self._refresh_cookies_status()
        QMessageBox.information(self, "Configurações", "Configurações salvas.")

    def _gate_config(self) -> GateConfig:
        start = self.window_start.time()
        end = self.window_end.time()
        return GateConfig(
            window_enabled=self.window_enabled.isChecked(),
            window_start_minute=start.hour() * 60 + start.minute(),
            window_end_minute=end.hour() * 60 + end.minute(),
            minimum_free_bytes=self.minimum_free_mb.value() * 1024 * 1024,
        )

    def _apply_gate(self) -> None:
        self.queue.set_gate(self._gate_config())
        self.queue.set_keep_awake(self.keep_awake.isChecked())
        self._refresh_gate_status()

    def _refresh_window_state(self) -> None:
        enabled = self.window_enabled.isChecked()
        for control in (self.window_start, self.window_end):
            control.setEnabled(enabled)
        self.minimum_free_mb.setEnabled(enabled or self.minimum_free_mb.value() > 0)
        self._refresh_gate_status()

    def _refresh_gate_status(self) -> None:
        if self.queue.gate_blocked:
            message = self.queue.gate_reason or "A fila está aguardando."
            self.gate_status.setText(message)
            self.gate_status_panel.setProperty("state", "warning")
        elif self.window_enabled.isChecked():
            self.gate_status.setText(
                "Liberado agora. Próxima verificação a cada 30 segundos."
            )
            self.gate_status_panel.setProperty("state", "success")
        else:
            self.gate_status.setText("Sem agendamento: downloads a qualquer hora.")
            self.gate_status_panel.setProperty("state", "neutral")
        self.gate_status_panel.style().unpolish(self.gate_status_panel)
        self.gate_status_panel.style().polish(self.gate_status_panel)

    def _refresh_proxy_status(self, *_args: object) -> None:
        kind = str(self.proxy_type.currentData())
        enabled = kind not in ("", "none")
        self.proxy_url.setEnabled(enabled)
        valid, message = validate_proxy_url(kind, self.proxy_url.text())
        self.proxy_status.setText(
            message if message else ("Endereço válido." if enabled else "")
        )
        self.proxy_status.setProperty("state", "error" if message else "neutral")
        self.proxy_status.style().unpolish(self.proxy_status)
        self.proxy_status.style().polish(self.proxy_status)

    def _stats_directories(self) -> list[Path]:
        directories = [
            self.video_download_dir.text().strip(),
            self.audio_download_dir.text().strip(),
            self.site_files_download_dir.text().strip(),
        ]
        return [Path(item) for item in directories if item]

    def _refresh_stats(self) -> None:
        try:
            snapshot = stats_service.collect(self._stats_directories())
        except OSError as error:
            self.stats_completed.setText("—")
            self.stats_downloaded.setText("—")
            self.stats_temporary.setText("—")
            self.stats_free.setText("—")
            self.stats_cleanup.setEnabled(False)
            self.stats_cleanup.setToolTip(str(error))
            return
        self.stats_cleanup.setEnabled(True)
        self.stats_cleanup.setToolTip(
            "Remove apenas partes e fragmentos de transferências interrompidas. "
            "Mídias concluídas nunca são apagadas."
        )
        self.stats_completed.setText(f"{snapshot.completed_count:,}".replace(",", "."))
        self.stats_downloaded.setText(format_bytes(snapshot.downloaded_bytes))
        self.stats_temporary.setText(
            f"{format_bytes(snapshot.temporary_bytes)} "
            f"({snapshot.temporary_files} arquivos)"
        )
        self.stats_free.setText(
            format_bytes(snapshot.free_bytes)
            if snapshot.free_bytes is not None
            else "Indisponível"
        )

    def _cleanup_temporaries(self) -> None:
        answer = QMessageBox.question(
            self,
            "Limpar temporários",
            "Remover partes e fragmentos de downloads interrompidos? "
            "Nenhuma mídia concluída é apagada.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result: CleanupResult = stats_service.remove_temporaries(self._stats_directories())
        self._refresh_stats()
        QMessageBox.information(
            self,
            "Limpar temporários",
            f"{result.removed_files} arquivos removidos, {format_bytes(result.freed_bytes)} liberados.",
        )

    def _refresh_sites(self) -> None:
        lines = []
        for row in site_rows():
            lines.append(
                f"<b>{row.platform.name}</b> — {row.label}<br/><span style=\"opacity:0.7\">{row.description}</span>"
            )
        self.site_list.setText("<div>" + "<br/><br/>".join(lines) + "</div>")

    def _export_backup(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar configurações",
            str(Path.home() / backup_service.BACKUP_FILENAME),
            "Backup de configurações (*.json)",
        )
        if not filename:
            return
        payload = backup_service.dumps(
            dict(self.settings.as_dict()), list(self._profiles)
        )
        try:
            Path(filename).write_text(payload, encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, "Exportar configurações", str(error))
            return
        QMessageBox.information(
            self, "Exportar configurações", f"Backup gravado em {filename}."
        )

    def _import_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importar configurações", "", "Backup de configurações (*.json)"
        )
        if not filename:
            return
        try:
            raw = Path(filename).read_text(encoding="utf-8")
            payload = backup_service.loads(raw)
            profiles = backup_service.apply(payload)
        except (OSError, BackupError) as error:
            QMessageBox.warning(self, "Importar configurações", str(error))
            return
        answer = QMessageBox.question(
            self,
            "Importar configurações",
            "Substituir as configurações atuais pelas do backup?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.settings.replace(payload.settings)
        self._profiles = profiles
        self._load()
        self._apply_gate()
        self.theme_changed.emit(str(self.theme.currentData()))
        QMessageBox.information(
            self,
            "Importar configurações",
            f"{len(profiles)} perfis de cookies restaurados. Revise e salve para aplicar.",
        )

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
        self._spotify_worker = worker
        self.pool.start(worker)

    def _spotify_connected(self, profile: object) -> None:
        self._spotify_worker = None
        self.spotify_connect.setEnabled(True)
        self._refresh_spotify_status()
        QMessageBox.information(
            self,
            "Spotify",
            f"Conta conectada como {profile}. Agora você pode analisar suas playlists autorizadas.",
        )

    def _spotify_connection_failed(self, error: str) -> None:
        self._spotify_worker = None
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

    def _browse_download_dir(self, field: QLineEdit, title: str) -> None:
        if directory := QFileDialog.getExistingDirectory(self, title, field.text()):
            field.setText(directory)

    def _browse_cookies(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Importar cookies.txt", "", "Cookies Netscape (*.txt)")
        if filename:
            self.cookies_file.setText(filename)
            self._select_data(self.cookie_source, "file")

    def _refresh_cookies_status(self, *_: object) -> None:
        source = self.cookie_source.currentData()
        if source == "browser":
            self._set_cookies_panel_state("neutral")
            message = (
                "Os cookies do navegador serão importados ao analisar um link. "
                "Feche o navegador antes de testar."
            )
        elif source == "file":
            if not self.cookies_file.text().strip():
                self._set_cookies_panel_state("error")
                message = "Escolha um arquivo cookies.txt para usar esta fonte."
            else:
                self._set_cookies_panel_state("neutral")
                message = "Arquivo configurado. Clique em Testar para validar."
        else:
            self._set_cookies_panel_state("neutral")
            message = (
                "Nenhuma fonte ativa. Conteúdo que exige login, como vídeos privados "
                "ou com restrição de idade, pode ficar bloqueado."
            )
        self.cookies_status.setText(message)
        self.cookies_status.setAccessibleDescription(message)
        self._set_cookies_button_enabled()

    def _set_cookies_button_enabled(self) -> None:
        if self._cookies_worker is not None:
            self.test_cookies_button.setEnabled(False)
            return
        source = self.cookie_source.currentData()
        file_ready = bool(self.cookies_file.text().strip())
        self.test_cookies_button.setEnabled(source == "browser" or (source == "file" and file_ready))

    def _set_cookies_panel_state(self, state: str) -> None:
        self.cookies_status_panel.setProperty("state", state)
        self.cookies_status_panel.style().unpolish(self.cookies_status_panel)
        self.cookies_status_panel.style().polish(self.cookies_status_panel)
        self.cookies_status_panel.update()

    def _test_cookies(self) -> None:
        self.test_cookies_button.setEnabled(False)
        self.cookies_status.setText("Validando a fonte de cookies…")
        self._set_cookies_panel_state("pending")
        worker = TaskWorker(_check_cookies_worker(
            self.ffmpeg,
            self.cookie_source.currentData(),
            self.cookies_file.text().strip(),
            self.browser.currentText(),
        ))
        worker.signals.done.connect(self._cookies_check_done)
        worker.signals.failed.connect(self._cookies_check_failed)
        self._cookies_worker = worker
        self.pool.start(worker)

    def _cookies_check_done(self, result: object) -> None:
        self._cookies_worker = None
        check = result if isinstance(result, CookieCheck) else CookieCheck(False, str(result))
        self.cookies_status.setText(check.message)
        self.cookies_status.setAccessibleDescription(check.message)
        self.cookies_status.setToolTip(check.detail or self.cookies_status.toolTip())
        if check.logged_in or check.ok:
            self._set_cookies_panel_state("ready" if check.logged_in else "neutral")
        else:
            self._set_cookies_panel_state("error")
        self._set_cookies_button_enabled()

    def _cookies_check_failed(self, error: str) -> None:
        self._cookies_worker = None
        self.cookies_status.setText(f"Não foi possível validar os cookies. {error}")
        self._set_cookies_panel_state("error")
        self._set_cookies_button_enabled()

    def _reload_profile_list(self) -> None:
        self.profile_list.clear()
        for profile in self._profiles:
            hosts = ", ".join(str(host) for host in profile.get("hosts") or [])
            label = str(profile.get("label") or "Perfil")
            impersonate = normalize_impersonate(profile.get("impersonate"))
            suffix = f" · {impersonate}" if impersonate else ""
            self.profile_list.addItem(f"{label} - {hosts}{suffix}")
        self._refresh_profile_buttons()

    def _refresh_profile_buttons(self) -> None:
        selected = self.profile_list.currentRow() >= 0
        self.edit_profile_button.setEnabled(selected)
        self.remove_profile_button.setEnabled(selected)

    def _add_profile(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._profiles.append(dialog.profile_data())
            self._reload_profile_list()
            self.profile_list.setCurrentRow(len(self._profiles) - 1)

    def _edit_profile(self) -> None:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self._profiles):
            return
        dialog = ProfileDialog(self, self._profiles[row])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.profile_data()
            updated["id"] = str(self._profiles[row].get("id") or updated["id"])
            self._profiles[row] = updated
            self._reload_profile_list()
            self.profile_list.setCurrentRow(row)

    def _remove_profile(self) -> None:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self._profiles):
            return
        profile = self._profiles[row]
        answer = QMessageBox.question(
            self,
            "Remover perfil de cookies",
            f"Remover o perfil \"{profile.get('label', 'Perfil')}\"? O arquivo cookies.txt não será apagado.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            del self._profiles[row]
            self._reload_profile_list()

    def _refresh_component_status(self) -> None:
        status = self.updates.status()
        self.ytdlp_version.setText(status.current_version)
        self.ytdlp_previous_version.setText(status.previous_version or "Nenhuma")
        self.cancel_ytdlp_change_button.setVisible(status.restart_required)

        if status.pending_action == "update" and status.pending_version:
            message = (
                f"Atualização {status.pending_version} pronta. Reinicie o aplicativo "
                "para validar e ativar; a versão atual será preservada."
            )
        elif status.pending_action == "rollback" and status.pending_version:
            message = (
                f"Restauração da versão {status.pending_version} pronta. "
                "Reinicie o aplicativo para aplicar."
            )
        elif status.message:
            message = status.message
        elif status.previous_version:
            message = (
                f"Proteção ativa. A versão {status.previous_version} pode ser restaurada "
                "se uma atualização causar problemas."
            )
        else:
            message = "Componente verificado. Uma versão de recuperação será criada na próxima atualização."
        self.ytdlp_update_status.setText(message)
        self.ytdlp_update_status.setAccessibleDescription(message)
        if status.restart_required:
            visual_state = "pending"
        elif status.last_event == "automatic_rollback":
            visual_state = "error"
        elif status.previous_version or status.last_event in {"updated", "rolled_back"}:
            visual_state = "ready"
        else:
            visual_state = "neutral"
        self._set_component_panel_state(visual_state)

        update_text = "ATUALIZAR YT-DLP"
        update_enabled = not status.restart_required
        if self._available_ytdlp_version:
            if self.updates.versions_equal(
                self._available_ytdlp_version, status.current_version
            ):
                update_text = "YT-DLP ATUALIZADO"
                update_enabled = False
            elif self.updates.version_is_newer(
                status.current_version, self._available_ytdlp_version
            ):
                update_text = "VERSÃO ATUAL MAIS RECENTE"
                update_enabled = False
            elif status.rejected_version and self.updates.versions_equal(
                self._available_ytdlp_version, status.rejected_version
            ):
                update_text = f"VERSÃO {self._available_ytdlp_version} BLOQUEADA"
                update_enabled = False
            else:
                update_text = f"ATUALIZAR PARA {self._available_ytdlp_version}"
        self.update_ytdlp_button.setText(update_text)
        self.rollback_ytdlp_button.setText(
            f"Restaurar {status.previous_version}"
            if status.previous_version
            else "Restaurar versão de recuperação"
        )

        enabled = not self._component_busy
        self.check_update_button.setEnabled(enabled and not status.restart_required)
        self.update_ytdlp_button.setEnabled(enabled and update_enabled)
        self.rollback_ytdlp_button.setEnabled(
            enabled and status.rollback_available and not status.restart_required
        )
        self.cancel_ytdlp_change_button.setEnabled(enabled and status.restart_required)
        self.rollback_ytdlp_button.setToolTip(
            "Use se sites deixaram de funcionar após uma atualização."
            if status.rollback_available
            else "Disponível depois que uma atualização for ativada com sucesso."
        )

    def _set_component_busy(self, busy: bool, message: str = "") -> None:
        self._component_busy = busy
        if message:
            self.ytdlp_update_status.setText(message)
            self.ytdlp_update_status.setAccessibleDescription(message)
            self._set_component_panel_state("pending")
        for button in (
            self.check_update_button,
            self.update_ytdlp_button,
            self.rollback_ytdlp_button,
            self.cancel_ytdlp_change_button,
        ):
            button.setEnabled(not busy)
        if not busy:
            self._refresh_component_status()

    def _set_component_panel_state(self, state: str) -> None:
        self.ytdlp_status_panel.setProperty("state", state)
        self.ytdlp_status_panel.style().unpolish(self.ytdlp_status_panel)
        self.ytdlp_status_panel.style().polish(self.ytdlp_status_panel)
        self.ytdlp_status_panel.update()

    def _run_component_task(self, function, success, busy_message: str) -> None:
        if self._component_busy:
            return
        self._set_component_busy(True, busy_message)
        worker = TaskWorker(function)
        self._active_component_worker = worker
        worker.signals.done.connect(
            lambda result: self._component_task_succeeded(success, result)
        )
        worker.signals.failed.connect(self._component_task_failed)
        self.pool.start(worker)

    def _component_task_succeeded(self, callback, result: object) -> None:
        self._active_component_worker = None
        self._set_component_busy(False)
        callback(result)

    def _component_task_failed(self, error: str) -> None:
        self._active_component_worker = None
        self._set_component_busy(False)
        message = f"Não foi possível concluir a operação. {error}"
        self.ytdlp_update_status.setText(message)
        self.ytdlp_update_status.setAccessibleDescription(message)
        self._set_component_panel_state("error")
        QMessageBox.warning(self, "Atualização do yt-dlp", message)

    def _check_update(self) -> None:
        self._run_component_task(
            self.updates.latest_ytdlp_version,
            self._update_check_finished,
            "Verificando a versão estável mais recente…",
        )

    def _update_check_finished(self, version: object) -> None:
        self._available_ytdlp_version = str(version)
        self._refresh_component_status()
        status = self.updates.status()
        if status.restart_required:
            # _refresh_component_status already explains which change is pending and
            # that a restart is required; never replace that instruction here.
            return
        if self.updates.versions_equal(
            self._available_ytdlp_version, status.current_version
        ):
            message = f"Você já usa a versão mais recente ({status.current_version})."
        elif self.updates.version_is_newer(
            status.current_version, self._available_ytdlp_version
        ):
            message = (
                f"Sua versão {status.current_version} é mais recente que a versão estável "
                f"publicada ({self._available_ytdlp_version}); nenhum downgrade será feito."
            )
        elif status.rejected_version and self.updates.versions_equal(
            self._available_ytdlp_version, status.rejected_version
        ):
            message = (
                f"A versão {self._available_ytdlp_version} falhou anteriormente e foi bloqueada. "
                "Aguarde uma versão mais recente."
            )
        else:
            message = f"Atualização {self._available_ytdlp_version} disponível."
        self.ytdlp_update_status.setText(message)
        self.ytdlp_update_status.setAccessibleDescription(message)

    def _update_ytdlp(self) -> None:
        self._run_component_task(
            self.updates.update_ytdlp,
            self._update_staged,
            "Baixando e verificando a atualização…",
        )

    def _update_staged(self, result: object) -> None:
        self._available_ytdlp_version = None
        self._refresh_component_status()
        version = getattr(result, "version", str(result))
        if getattr(result, "restart_required", False):
            QMessageBox.information(
                self,
                "Atualização pronta",
                f"O yt-dlp {version} foi verificado e está pronto.\n\n"
                "Reinicie o aplicativo para validar e ativar a nova versão. "
                "A versão atual será mantida para recuperação.",
            )
        else:
            QMessageBox.information(
                self,
                "yt-dlp atualizado",
                f"Você já usa a versão {version}.",
            )

    def _rollback_ytdlp(self) -> None:
        status = self.updates.status()
        if not status.previous_version:
            return
        answer = QMessageBox.question(
            self,
            "Restaurar yt-dlp",
            f"Trocar a versão {status.current_version} pela versão de recuperação "
            f"{status.previous_version} no próximo reinício?\n\n"
            "Use esta opção se sites deixaram de funcionar depois de uma atualização. "
            "A versão atual continuará disponível para desfazer a restauração.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_component_task(
            self.updates.request_rollback,
            self._rollback_staged,
            "Preparando a versão de recuperação…",
        )

    def _rollback_staged(self, result: object) -> None:
        self._available_ytdlp_version = None
        self._refresh_component_status()
        version = getattr(result, "version", str(result))
        QMessageBox.information(
            self,
            "Restauração pronta",
            f"A versão {version} será restaurada após reiniciar o aplicativo.",
        )

    def _cancel_ytdlp_change(self) -> None:
        self._run_component_task(
            self.updates.cancel_pending_change,
            self._pending_change_cancelled,
            "Cancelando a alteração pendente…",
        )

    def _pending_change_cancelled(self, _result: object) -> None:
        self._available_ytdlp_version = None
        self._refresh_component_status()
