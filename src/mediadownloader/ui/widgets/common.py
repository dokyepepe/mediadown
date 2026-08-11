"""Small reusable presentation widgets."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from mediadownloader.models import DownloadStatus

from ..icons import set_button_icon, svg_pixmap


class WheelSafeComboBox(QComboBox):
    """Combo box that never changes selection from an accidental mouse wheel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleDescription(
            "Use as setas do teclado ou abra a lista. A roda do mouse não altera esta seleção."
        )

    def wheelEvent(self, event) -> None:
        event.ignore()


class WheelSafeSpinBox(QSpinBox):
    """Spin box protected from unintended wheel value changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleDescription(
            "Digite um valor ou use as setas. A roda do mouse não altera este número."
        )

    def wheelEvent(self, event) -> None:
        event.ignore()


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None, icon_name: str = "") -> None:
        super().__init__(text, parent)
        self.setProperty("role", "primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setAccessibleName(text.replace("&", ""))
        if icon_name:
            set_button_icon(self, icon_name, "#FFFFFF")


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None, icon_name: str = "") -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setAccessibleName(text.replace("&", ""))
        if icon_name:
            set_button_icon(self, icon_name)


class SidebarButton(QPushButton):
    def __init__(self, text: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("SidebarButton")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setAccessibleName(text)
        self.setAccessibleDescription(f"Abrir a seção {text}.")
        self.icon_name = icon_name
        self.toggled.connect(self._refresh_icon)
        self._refresh_icon(False)

    def _refresh_icon(self, checked: bool) -> None:
        role = QPalette.ColorRole.Link if checked else QPalette.ColorRole.ButtonText
        set_button_icon(self, self.icon_name, self.palette().color(role).name(), 19)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange} and hasattr(self, "icon_name"):
            self._refresh_icon(self.isChecked())


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, icon_name: str) -> None:
        super().__init__()
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(14)
        icon = QLabel()
        icon.setObjectName("PageHeaderIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(46, 46)
        icon.setPixmap(svg_pixmap(icon_name, 25, "#2E8B57"))
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        layout.addWidget(icon)
        layout.addLayout(text, 1)


class EmptyState(QWidget):
    def __init__(self, title: str, subtitle: str, icon_name: str = "downloads") -> None:
        super().__init__()
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(svg_pixmap(icon_name, 48, "#7E8983"))
        icon.setFixedHeight(58)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


class StatusBadge(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("StatusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setContentsMargins(8, 3, 8, 3)

    def set_status(self, status: DownloadStatus) -> None:
        style_status = {
            DownloadStatus.COMPLETED: "completed",
            DownloadStatus.ERROR: "error",
            DownloadStatus.CANCELLED: "cancelled",
            DownloadStatus.QUEUED: "queued",
        }.get(status, "active")
        self.setText(status.label)
        self.setAccessibleName(f"Status: {status.label}")
        self.setProperty("status", style_status)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ThumbnailLabel(QLabel):
    def __init__(self, width: int = 160, height: int = 90) -> None:
        super().__init__()
        self._size = (width, height)
        self._preserve_artwork = False
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("MÍDIA")
        self.setObjectName("Thumbnail")
        self.setAccessibleName("Miniatura da mídia")
        self.manager = QNetworkAccessManager(self)
        self.manager.finished.connect(self._loaded)

    def set_preserve_artwork(self, preserve: bool) -> None:
        """Avoid cropping artwork when a provider's attribution rules require it."""
        self._preserve_artwork = preserve

    def load(self, url: str) -> None:
        if url.startswith(("http://", "https://")):
            request = QNetworkRequest(QUrl(url))
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, True)
            self.manager.get(request)

    def _loaded(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap = QPixmap()
                if pixmap.loadFromData(reply.readAll()):
                    mode = (
                        Qt.AspectRatioMode.KeepAspectRatio
                        if self._preserve_artwork
                        else Qt.AspectRatioMode.KeepAspectRatioByExpanding
                    )
                    self.setPixmap(pixmap.scaled(
                        *self._size, mode, Qt.TransformationMode.SmoothTransformation,
                    ))
                    self.setText("")
        finally:
            reply.deleteLater()
