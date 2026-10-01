"""Application identity, supported platforms and third-party acknowledgements."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from io import BytesIO
from pathlib import Path
import platform
import sys

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from mediadownloader.core import site_compatibility
from mediadownloader.core.ffmpeg_manager import FFmpegManager
from mediadownloader.core.platform_catalog import PlatformInfo, extractor_count, supported_platforms
from mediadownloader.core.site_compatibility import SiteState, state_label
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.services.update_service import UpdateService
from mediadownloader.support import SUPPORT_PIX_KEY, SUPPORT_PIX_PAYLOAD
from mediadownloader.utils.paths import database_path, logs_dir, reveal_in_explorer, settings_path
from mediadownloader.version import APP_VERSION

from ..icons import svg_pixmap
from ..widgets import PageHeader, PrimaryButton, SecondaryButton, ThemedIconLabel

#: Python distributions the About page reports, with the label shown to the user.
DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("yt-dlp", "yt-dlp"),
    ("PySide6", "PySide6 / Qt"),
    ("qrcode", "QR Code"),
    ("packaging", "packaging"),
)

STATE_COLORS: dict[SiteState, str] = {
    SiteState.SUPPORTED: "#2E7D5B",
    SiteState.NEEDS_COOKIES: "#B07A18",
    SiteState.METADATA_ONLY: "#3A6EA5",
    SiteState.UNAVAILABLE: "#B23B3B",
}


def _support_qr_pixmap() -> QPixmap:
    code = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=4,
        border=4,
    )
    code.add_data(SUPPORT_PIX_PAYLOAD)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


class _ComponentSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _ComponentWorker(QRunnable):
    """Reads component versions off the UI thread: ffmpeg -version is a subprocess."""

    def __init__(self, ffmpeg: FFmpegManager) -> None:
        super().__init__()
        self.signals = _ComponentSignals()
        self.ffmpeg = ffmpeg

    @Slot()
    def run(self) -> None:
        try:
            status = UpdateService.status()
            self.signals.done.emit({
                "yt-dlp": status.current_version or "desconhecida",
                "FFmpeg": self.ffmpeg.version(),
                "ffprobe": self.ffmpeg.ffprobe_version(),
                "pendente": status.pending_version or "—",
                "recuperacao": status.previous_version or "—",
            })
        except Exception as error:
            self.signals.failed.emit(str(error) or "Não foi possível ler os componentes.")


def dependency_versions() -> list[tuple[str, str]]:
    """Installed versions for the third-party packages, in display order."""
    rows: list[tuple[str, str]] = []
    for distribution, label in DEPENDENCIES:
        try:
            rows.append((label, package_version(distribution)))
        except PackageNotFoundError:
            rows.append((label, "não instalado"))
    return rows


def effective_settings_lines(settings: SettingsService) -> list[str]:
    """The settings that change how a download behaves, never the secrets behind them."""
    from mediadownloader.core.download_gate import format_minute

    cookies = str(settings.get("cookies.file", "") or "")
    browser = str(settings.get("cookies.browser", "") or "")
    window = (
        "inativo"
        if not settings.get("downloads.window_enabled")
        else f"{format_minute(int(settings.get('downloads.window_start_minute', 0)))}"
        f"–{format_minute(int(settings.get('downloads.window_end_minute', 360)))}"
    )
    proxy = settings.get("network.proxy_url", "") or settings.get("network.proxy_type", "none")
    rate_limit = int(settings.get("network.rate_limit_kbps", 0) or 0)
    return [
        f"Tema: {settings.get('general.theme', 'system')}",
        f"Downloads simultâneos: {settings.get('downloads.concurrent', 2)}",
        f"Limite de velocidade: {f'{rate_limit} kbps' if rate_limit else 'sem limite'}",
        f"Proxy: {'configurado' if proxy and proxy != 'none' else 'não configurado'}",
        f"Janela de download: {window}",
        f"Espaço livre mínimo: {settings.get('downloads.minimum_free_mb', 32)} MB",
        f"Manter o computador acordado: {'sim' if settings.get('downloads.keep_awake') else 'não'}",
        f"Impersonate: {settings.get('cookies.impersonate', '') or 'Não usar'}",
        f"Cookies: {Path(cookies).name if cookies else (browser or 'nenhum')}",
        f"Modelo de nome: {settings.get('filenames.template', '%(title)s.%(ext)s')}",
    ]


def build_diagnostics_summary(
    settings_location: str,
    history_location: str,
    logs_location: str,
    extractors: int,
    components: dict[str, str] | None = None,
    settings_lines: list[str] | None = None,
    site_rows: list[str] | None = None,
) -> str:
    """Compile a privacy-conscious support summary without creating any folder.

    Logs may contain URLs, so the summary only points at the folders instead of
    dumping their contents. Cookie files are reported by name only, never by path.
    """
    try:
        import PySide6

        qt_version = str(getattr(PySide6, "__version__", "") or "desconhecida")
    except Exception:
        qt_version = "desconhecida"
    lines = [
        f"Media Downloader {APP_VERSION}",
        "",
        "Sistema",
        f"  Sistema operacional: {platform.system()} {platform.release()} ({platform.machine()})",
        f"  Python: {platform.python_version()}",
        f"  Qt / PySide6: {qt_version}",
        f"  Extractors disponíveis: {extractors}",
    ]
    if components:
        lines += ["", "Componentes"]
        lines += [f"  {name}: {value}" for name, value in components.items()]
    if settings_lines:
        lines += ["", "Configurações efetivas"]
        lines += [f"  {line}" for line in settings_lines]
    if site_rows:
        lines += ["", "Compatibilidade"]
        lines += [f"  {row}" for row in site_rows]
    lines += [
        "",
        "Localizações",
        f"  Configurações: {settings_location}",
        f"  Histórico: {history_location}",
        f"  Logs: {logs_location}",
        "",
        "Nenhum dado saiu deste computador.",
    ]
    return "\n".join(lines)


class SupportCard(QFrame):
    """Quiet, optional support callout with an offline-generated Pix QR code."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setAccessibleName("Apoie voluntariamente o Media Downloader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(20)

        details = QVBoxLayout()
        details.setSpacing(8)
        title = QLabel("❤️ Apoie o projeto")
        title.setObjectName("SectionTitle")
        description = QLabel(
            "O Media Downloader é gratuito e de código aberto. Se ele foi útil para você, "
            "considere apoiar voluntariamente seu desenvolvimento por Pix."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        key_caption = QLabel("CHAVE PIX")
        key_caption.setObjectName("Eyebrow")
        self.key_label = QLabel(SUPPORT_PIX_KEY)
        self.key_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.key_label.setWordWrap(True)
        self.key_label.setAccessibleName("Chave Pix do projeto")
        self.copy_payload_button = PrimaryButton("Copiar Pix Copia e Cola", icon_name="copy")
        self.copy_payload_button.setAccessibleDescription(
            "Copia o código completo do QR Pix para a área de transferência. O apoio é opcional."
        )
        self.copy_payload_button.clicked.connect(self.copy_pix_payload)
        self.copy_button = SecondaryButton("Copiar chave Pix", icon_name="copy")
        self.copy_button.setAccessibleDescription(
            "Copia a chave Pix para a área de transferência. O apoio é opcional."
        )
        self.copy_button.clicked.connect(self.copy_pix_key)
        safety = QLabel(
            "Antes de confirmar, confira no aplicativo do banco os dados do recebedor."
        )
        safety.setObjectName("WarningText")
        safety.setWordWrap(True)
        details.addWidget(title)
        details.addWidget(description)
        details.addSpacing(2)
        details.addWidget(key_caption)
        details.addWidget(self.key_label)
        details.addWidget(self.copy_payload_button)
        details.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignLeft)
        details.addWidget(safety)

        qr_column = QVBoxLayout()
        qr_column.setSpacing(5)
        qr_column.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label = QLabel()
        self.qr_label.setObjectName("QrCodePreview")
        self.qr_label.setFixedSize(236, 236)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setAccessibleName("QR Code Pix para apoiar o projeto")
        pixmap = _support_qr_pixmap()
        self.qr_label.setPixmap(pixmap)
        qr_caption = QLabel("Escaneie com o app do seu banco")
        qr_caption.setObjectName("Muted")
        qr_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_column.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignHCenter)
        qr_column.addWidget(qr_caption)

        layout.addLayout(details, 1)
        layout.addLayout(qr_column)

    def copy_pix_key(self) -> None:
        QApplication.clipboard().setText(SUPPORT_PIX_KEY)
        self.copy_button.setText("Chave Pix copiada")

    def copy_pix_payload(self) -> None:
        QApplication.clipboard().setText(SUPPORT_PIX_PAYLOAD)
        self.copy_payload_button.setText("Pix Copia e Cola copiado")


class MetricCard(QFrame):
    def __init__(self, value: str, label: str, icon_name: str) -> None:
        super().__init__()
        self.setObjectName("SoftCard")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        icon = ThemedIconLabel(icon_name, 24)
        icon.setFixedWidth(32)
        text = QVBoxLayout()
        text.setSpacing(0)
        value_label = QLabel(value)
        value_label.setObjectName("Metric")
        caption = QLabel(label)
        caption.setObjectName("Muted")
        caption.setWordWrap(True)
        text.addWidget(value_label)
        text.addWidget(caption)
        layout.addWidget(icon)
        layout.addLayout(text, 1)


class PlatformCard(QFrame):
    def __init__(self, platform: PlatformInfo, state: SiteState | None = None) -> None:
        super().__init__()
        self.setObjectName("SoftCard")
        self.setMinimumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(platform.name)
        detail = f"{platform.description}. Recursos: {platform.capabilities}."
        if state is not None:
            detail = f"{state_label(state)}. {detail}"
        self.setAccessibleDescription(detail)
        self.setStyleSheet(
            f"QFrame#SoftCard {{ border-left: 3px solid {platform.brand_accent}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(12)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(46, 46)
        icon.setPixmap(svg_pixmap(platform.icon, 27, platform.logo_color))
        icon.setAccessibleName(f"Logo {platform.name}")
        icon.setStyleSheet(
            f"background: {platform.brand_background}; "
            f"border: 1px solid {platform.brand_accent}; border-radius: 9px;"
        )
        text = QVBoxLayout()
        text.setSpacing(3)
        name = QLabel(platform.name)
        name.setObjectName("SectionTitle")
        description = QLabel(platform.description)
        description.setObjectName("Muted")
        description.setWordWrap(True)
        description.setMinimumWidth(0)
        capabilities = QLabel(platform.capabilities)
        capabilities.setObjectName("Eyebrow")
        capabilities.setStyleSheet("font-size:7.5pt; letter-spacing:.5px;")
        capabilities.setWordWrap(True)
        capabilities.setMinimumWidth(0)
        text.addWidget(name)
        text.addWidget(description)
        text.addWidget(capabilities)
        if state is not None:
            badge = QLabel(state_label(state))
            badge.setObjectName("SectionEyebrow")
            badge.setStyleSheet(f"color: {STATE_COLORS[state]}; font-size:8pt;")
            badge.setAccessibleName(f"Situação: {state_label(state)}")
            text.addWidget(badge)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)


class VersionRow(QFrame):
    """One ``label: value`` line for component and dependency readouts."""

    def __init__(self, label: str, value: str = "verificando…") -> None:
        super().__init__()
        self.setObjectName("SoftCard")
        self.caption_text = label
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 9, 13, 9)
        layout.setSpacing(10)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("SectionTitle")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        caption = QLabel(label)
        caption.setObjectName("Muted")
        caption.setWordWrap(True)
        caption.setMinimumWidth(0)
        layout.addWidget(caption, 1)
        layout.addWidget(self.value_label, 0)
        self.setAccessibleName(f"{label}: {value}")

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        self.value_label.setAccessibleDescription(value)
        self.setAccessibleName(f"{self.caption_text}: {value}")


class AboutPage(QWidget):
    def __init__(
        self,
        settings: SettingsService | None = None,
        ffmpeg: FFmpegManager | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.settings = settings
        self._components: dict[str, str] = {}
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
            "Sobre", "Tecnologia, privacidade e compatibilidade em uma visão clara.", "info"
        ))

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero.setAccessibleName("Identidade do Media Downloader")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(20)
        logo = ThemedIconLabel("brand", 58)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(82, 82)
        logo.setObjectName("TintedIcon")
        identity = QVBoxLayout()
        identity.setSpacing(5)
        platform_name = "LINUX" if sys.platform.startswith("linux") else "WINDOWS"
        eyebrow = QLabel(f"UTILITÁRIO DESKTOP PARA {platform_name}")
        eyebrow.setObjectName("Eyebrow")
        name = QLabel("Media Downloader")
        name.setObjectName("HeroName")
        description = QLabel(
            "Download e conversão de mídias com uma interface simples, organizada e local. "
            "Sem conta obrigatória, telemetria ou envio do histórico."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        copyright_label = QLabel("© 2026 Pietro Ferreira · Licença MIT")
        copyright_label.setObjectName("Eyebrow")
        identity.addWidget(eyebrow)
        identity.addWidget(name)
        identity.addWidget(description)
        identity.addWidget(copyright_label)
        hero_layout.addWidget(logo)
        hero_layout.addLayout(identity, 1)
        root.addWidget(hero)

        self.support_card = SupportCard()
        root.addWidget(self.support_card)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        count = extractor_count()
        metrics.addWidget(MetricCard(APP_VERSION, "Versão do aplicativo", "info"), 0, 0)
        metrics.addWidget(MetricCard(f"{count:,}".replace(",", ".") if count else "Ampla", "Extractors disponíveis", "globe"), 0, 1)
        metrics.addWidget(MetricCard("100% local", "Histórico e configurações permanecem neste computador", "shield"), 1, 0, 1, 2)
        metrics.setColumnStretch(0, 1)
        metrics.setColumnStretch(1, 1)
        root.addLayout(metrics)

        section = QLabel("Principais plataformas compatíveis")
        section.setObjectName("SectionTitle")
        root.addWidget(section)
        explanation = QLabel(
            "A disponibilidade depende do tipo de URL, região, autenticação e mudanças feitas por cada serviço. "
            "Cada cartão é resolvido com os extractors desta versão do yt-dlp, então a situação muda quando o componente é atualizado."
        )
        explanation.setObjectName("Muted")
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        platform_grid = QGridLayout()
        platform_grid.setHorizontalSpacing(10)
        platform_grid.setVerticalSpacing(10)
        site_rows = site_compatibility.rows()
        for index, row in enumerate(site_rows):
            platform_grid.addWidget(PlatformCard(row.platform, row.state), index // 2, index % 2)
        platform_grid.setColumnStretch(0, 1)
        platform_grid.setColumnStretch(1, 1)
        root.addLayout(platform_grid)

        more = QFrame()
        more.setObjectName("Card")
        more_layout = QHBoxLayout(more)
        more_layout.setContentsMargins(18, 15, 18, 15)
        more_icon = ThemedIconLabel("list", 28)
        more_text = QLabel(
            "<b>E muitos outros sites.</b><br>O mecanismo genérico do yt-dlp e seus extractors adicionais "
            "ampliam a cobertura além das plataformas destacadas acima."
        )
        more_text.setWordWrap(True)
        more_layout.addWidget(more_icon)
        more_layout.addWidget(more_text, 1)
        root.addWidget(more)
        self.site_summary = QLabel(site_compatibility.summary())
        self.site_summary.setObjectName("Muted")
        root.addWidget(self.site_summary)

        diagnostics_card = QFrame()
        diagnostics_card.setObjectName("Card")
        diagnostics_card.setAccessibleName("Diagnóstico e suporte")
        diagnostics_layout = QVBoxLayout(diagnostics_card)
        diagnostics_layout.setContentsMargins(18, 16, 18, 18)
        diagnostics_layout.setSpacing(10)
        diagnostics_title = QLabel("Diagnóstico")
        diagnostics_title.setObjectName("SectionTitle")
        diagnostics_description = QLabel(
            "Copie um resumo local do aplicativo para colar num pedido de suporte. "
            "Os logs podem conter URLs, então eles ficam nesta máquina; abra a pasta somente quando precisar."
        )
        diagnostics_description.setObjectName("Muted")
        diagnostics_description.setWordWrap(True)
        diagnostics_actions = QWidget()
        diagnostics_actions_row = QHBoxLayout(diagnostics_actions)
        diagnostics_actions_row.setContentsMargins(0, 0, 0, 0)
        diagnostics_actions_row.setSpacing(8)
        self.copy_diagnostics_button = SecondaryButton("Copiar diagnóstico", icon_name="copy")
        self.copy_diagnostics_button.setAccessibleDescription(
            "Copia um resumo sobre versões e locais de arquivos para a área de transferência."
        )
        self.copy_diagnostics_button.clicked.connect(self._copy_diagnostics)
        self.open_logs_button = SecondaryButton("Abrir pasta de logs", icon_name="folder")
        self.open_logs_button.setAccessibleDescription(
            "Abre no explorador de arquivos a pasta onde o aplicativo grava seus logs locais."
        )
        self.open_logs_button.clicked.connect(lambda: reveal_in_explorer(logs_dir()))
        diagnostics_actions_row.addWidget(self.copy_diagnostics_button)
        diagnostics_actions_row.addWidget(self.open_logs_button)
        diagnostics_actions_row.addStretch()
        diagnostics_layout.addWidget(diagnostics_title)
        diagnostics_layout.addWidget(diagnostics_description)
        diagnostics_layout.addWidget(diagnostics_actions)
        root.addWidget(diagnostics_card)

        third = QFrame()
        third.setObjectName("Card")
        third_layout = QVBoxLayout(third)
        third_layout.setContentsMargins(18, 16, 18, 16)
        third_title = QLabel("Componentes de terceiros")
        third_title.setObjectName("SectionTitle")
        third_text = QLabel(
            "<b>yt-dlp</b> — extração e download &nbsp; • &nbsp; "
            "<b>FFmpeg</b> — merge e conversão &nbsp; • &nbsp; "
            "<b>Deno / yt-dlp-ejs</b> — suporte JavaScript &nbsp; • &nbsp; "
            "<b>PySide6 / Qt</b> — interface gráfica &nbsp; • &nbsp; "
            "<b>Spotify Web API</b> — metadados autorizados<br><br>"
            "As licenças completas acompanham a distribuição na pasta <code>licenses</code>."
        )
        third_text.setObjectName("Muted")
        third_text.setWordWrap(True)
        legal = QLabel("Baixe somente conteúdo que você possui autorização para acessar e conservar.")
        legal.setObjectName("WarningText")
        legal.setWordWrap(True)
        third_layout.addWidget(third_title)
        third_layout.addWidget(third_text)
        third_layout.addWidget(legal)
        root.addWidget(third)

        versions = QFrame()
        versions.setObjectName("Card")
        versions.setAccessibleName("Versões dos componentes instalados")
        versions_layout = QVBoxLayout(versions)
        versions_layout.setContentsMargins(18, 16, 18, 18)
        versions_layout.setSpacing(8)
        versions_title = QLabel("Versões instaladas")
        versions_title.setObjectName("SectionTitle")
        versions_hint = QLabel(
            "As versões são lidas dos componentes reais, sem rede. "
            "Atualize o yt-dlp em Configurações quando uma versão mais nova estiver disponível."
        )
        versions_hint.setObjectName("Muted")
        versions_hint.setWordWrap(True)
        self.component_rows: dict[str, VersionRow] = {}
        for label in ("yt-dlp em uso", "FFmpeg", "ffprobe", "yt-dlp pendente", "yt-dlp de recuperação"):
            row = VersionRow(label)
            self.component_rows[label] = row
            versions_layout.addWidget(row)
        versions_layout.addWidget(versions_hint)
        root.addWidget(versions)

        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dependencies.setAccessibleName("Dependências e suas versões")
        dependencies_layout = QVBoxLayout(dependencies)
        dependencies_layout.setContentsMargins(18, 16, 18, 18)
        dependencies_layout.setSpacing(8)
        dependencies_title = QLabel("Dependências")
        dependencies_title.setObjectName("SectionTitle")
        dependencies_layout.addWidget(dependencies_title)
        for label, installed in dependency_versions():
            dependencies_layout.addWidget(VersionRow(label, installed))
        root.addWidget(dependencies)
        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._read_components(ffmpeg or FFmpegManager())

    def _read_components(self, ffmpeg: FFmpegManager) -> None:
        """Probe ffmpeg/yt-dlp off the UI thread, then fill the version rows."""
        worker = _ComponentWorker(ffmpeg)
        worker.signals.done.connect(self._components_read)
        worker.signals.failed.connect(self._components_failed)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _components_read(self, components: dict) -> None:
        self._components = {str(name): str(value) for name, value in components.items()}
        for label, row in self.component_rows.items():
            key = {
                "yt-dlp em uso": "yt-dlp",
                "FFmpeg": "FFmpeg",
                "ffprobe": "ffprobe",
                "yt-dlp pendente": "pendente",
                "yt-dlp de recuperação": "recuperacao",
            }[label]
            row.set_value(self._components.get(key, "—"))

    @Slot(str)
    def _components_failed(self, message: str) -> None:
        for row in self.component_rows.values():
            row.set_value("indisponível")
        self._components = {}
        self.copy_diagnostics_button.setAccessibleDescription(
            f"Não foi possível ler os componentes: {message}"
        )

    def _diagnostics_lines(self) -> list[str]:
        lines = []
        if self.settings is not None:
            lines = effective_settings_lines(self.settings)
        return lines

    def _site_lines(self) -> list[str]:
        return [
            f"{row.platform.name}: {row.label}"
            for row in site_compatibility.rows()
        ] + [site_compatibility.summary()]

    def _copy_diagnostics(self) -> None:
        summary = build_diagnostics_summary(
            str(settings_path()),
            str(database_path()),
            str(logs_dir()),
            extractor_count(),
            self._components or None,
            self._diagnostics_lines(),
            self._site_lines(),
        )
        QApplication.clipboard().setText(summary)
        self.copy_diagnostics_button.setText("Diagnóstico copiado")
