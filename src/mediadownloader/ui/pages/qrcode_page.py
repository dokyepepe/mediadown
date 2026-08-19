"""Offline URL-to-QR-code workflow."""

from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QScrollArea, QVBoxLayout, QWidget,
)

from mediadownloader.utils.validators import validate_url

from ..icons import svg_icon
from ..widgets import PageHeader, PrimaryButton, SecondaryButton


class QrCodePage(QWidget):
    """Generate a QR code locally and expose common desktop export actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        self._pixmap = QPixmap()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("Page")
        root = QVBoxLayout(content)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(18)
        root.addWidget(PageHeader(
            "Gerar QR Code",
            "Transforme uma URL em um QR Code sem enviar dados para a internet.",
            "qrcode",
        ))

        card = QFrame()
        card.setObjectName("HeroCard")
        card.setAccessibleName("Gerador de QR Code")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(12)

        title = QLabel("Cole a URL que deseja compartilhar")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel("A imagem é criada neste dispositivo e pode ser copiada ou salva em PNG.")
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        input_row = QHBoxLayout()
        input_row.setSpacing(9)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://exemplo.com")
        self.url_input.setAccessibleName("URL para o QR Code")
        self.url_input.setMinimumHeight(44)
        self.url_input.addAction(svg_icon("globe", 18), QLineEdit.ActionPosition.LeadingPosition)
        self.url_input.returnPressed.connect(self.generate)
        self.url_input.textChanged.connect(self._clear_error)
        self.generate_button = PrimaryButton("GERAR QR CODE", icon_name="qrcode")
        self.generate_button.clicked.connect(self.generate)
        input_row.addWidget(self.url_input, 1)
        input_row.addWidget(self.generate_button)
        card_layout.addLayout(input_row)

        self.notice = QLabel()
        self.notice.setObjectName("Notice")
        self.notice.setProperty("state", "error")
        self.notice.setAccessibleName("Erro na URL")
        self.notice.setWordWrap(True)
        self.notice.hide()
        card_layout.addWidget(self.notice)
        root.addWidget(card)

        result = QFrame()
        result.setObjectName("Card")
        result.setAccessibleName("Resultado do QR Code")
        result_layout = QVBoxLayout(result)
        result_layout.setContentsMargins(24, 22, 24, 22)
        result_layout.setSpacing(12)
        self.preview = QLabel("O QR Code aparecerá aqui depois de gerar.")
        self.preview.setObjectName("QrCodePreview")
        self.preview.setAccessibleName("Prévia do QR Code")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(300, 300)
        self.preview.setWordWrap(True)
        result_layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)

        actions = QHBoxLayout()
        actions.addStretch()
        self.copy_button = SecondaryButton("Copiar imagem", icon_name="copy")
        self.copy_button.clicked.connect(self.copy_image)
        self.save_button = SecondaryButton("Salvar PNG", icon_name="folder")
        self.save_button.clicked.connect(self.save_image)
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.save_button)
        actions.addStretch()
        result_layout.addLayout(actions)
        root.addWidget(result)
        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def generate(self) -> None:
        value = self.url_input.text().strip()
        valid, message = validate_url(value)
        if not valid:
            self._show_error(message)
            self.url_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if len(value.encode("utf-8")) > 1500:
            self._show_error("A URL é longa demais para gerar um QR Code confiável.")
            self.url_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        code = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        code.add_data(value)
        code.make(fit=True)
        image = code.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
            self._show_error("Não foi possível montar a imagem do QR Code.")
            return

        self._pixmap = pixmap
        self.preview.setText("")
        self.preview.setPixmap(pixmap.scaled(
            300, 300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self.preview.setAccessibleDescription(f"QR Code gerado para {value}")
        self.copy_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.notice.hide()

    def copy_image(self) -> None:
        if not self._pixmap.isNull():
            QApplication.clipboard().setPixmap(self._pixmap)

    def save_image(self) -> None:
        if self._pixmap.isNull():
            return
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, "Salvar QR Code", "qrcode.png", "Imagem PNG (*.png)"
        )
        if path and not self._pixmap.save(path, "PNG"):
            QMessageBox.warning(self, "Falha ao salvar", "Não foi possível salvar a imagem PNG.")

    def _clear_error(self) -> None:
        self.notice.hide()

    def _show_error(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.show()
