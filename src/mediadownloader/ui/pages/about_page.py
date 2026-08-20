"""Application identity, supported platforms and third-party acknowledgements."""

from __future__ import annotations

from io import BytesIO
import sys

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from mediadownloader.core.platform_catalog import PlatformInfo, extractor_count, supported_platforms
from mediadownloader.support import SUPPORT_PIX_KEY, SUPPORT_PIX_PAYLOAD
from mediadownloader.version import APP_VERSION

from ..icons import svg_pixmap
from ..widgets import PageHeader, PrimaryButton, SecondaryButton, ThemedIconLabel


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
    def __init__(self, platform: PlatformInfo) -> None:
        super().__init__()
        self.setObjectName("SoftCard")
        self.setMinimumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(platform.name)
        self.setAccessibleDescription(
            f"{platform.description}. Recursos: {platform.capabilities}."
        )
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
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
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
            "A lista cruza os extractors desta versão do yt-dlp com integrações nativas do aplicativo."
        )
        explanation.setObjectName("Muted")
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        platform_grid = QGridLayout()
        platform_grid.setHorizontalSpacing(10)
        platform_grid.setVerticalSpacing(10)
        for index, platform in enumerate(supported_platforms()):
            platform_grid.addWidget(PlatformCard(platform), index // 2, index % 2)
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
        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
