"""Small reusable presentation widgets."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from mediadownloader.models import DownloadStatus

from ..icons import set_button_icon, svg_pixmap


class WheelSafeComboBox(QComboBox):
    """Combo box that never changes selection from an accidental mouse wheel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.setMinimumHeight(45)
        self.setAccessibleName(text.replace("&", ""))
        if icon_name:
            set_button_icon(self, icon_name, "#FFFFFF")


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None, icon_name: str = "") -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(45)
        self.setAccessibleName(text.replace("&", ""))
        if icon_name:
            set_button_icon(self, icon_name)


class SidebarButton(QPushButton):
    """Desktop navigation item with a palette-aware icon."""

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
        app = QApplication.instance()
        app_color = app.property("sidebarActiveText" if checked else "sidebarText") if app else None
        if app_color:
            color = str(app_color)
        else:
            role = QPalette.ColorRole.Link if checked else QPalette.ColorRole.ButtonText
            color = self.palette().color(role).name()
        set_button_icon(self, self.icon_name, color, 19)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange} and hasattr(self, "icon_name"):
            self._refresh_icon(self.isChecked())


class ThemedIconLabel(QLabel):
    """Palette-aware SVG label that stays legible after a live theme switch."""

    def __init__(
        self,
        icon_name: str,
        icon_size: int,
        parent: QWidget | None = None,
        color_property: str = "",
    ) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_size = icon_size
        self.color_property = color_property
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        app = QApplication.instance()
        themed_color = app.property(self.color_property) if app and self.color_property else None
        color = str(themed_color) if themed_color else self.palette().color(QPalette.ColorRole.Link).name()
        self.setPixmap(svg_pixmap(self.icon_name, self.icon_size, color))

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange} and hasattr(self, "icon_name"):
            self._refresh_icon()


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, icon_name: str) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(14)
        icon = ThemedIconLabel(icon_name, 23)
        icon.setObjectName("PageHeaderIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(48, 48)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        subtitle_label.setMinimumWidth(0)
        subtitle_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        layout.addWidget(icon)
        layout.addLayout(text, 1)


class EmptyState(QWidget):
    def __init__(self, title: str, subtitle: str, icon_name: str = "downloads") -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(260)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 34, 32, 34)
        layout.setSpacing(0)

        self.content = QWidget()
        self.content.setObjectName("EmptyStateContent")
        self.content.setMinimumWidth(480)
        self.content.setMaximumWidth(640)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(10)
        icon = ThemedIconLabel(icon_name, 31)
        icon.setObjectName("StepIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(64, 64)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Muted")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setMinimumWidth(0)
        self.subtitle_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.subtitle_label)
        layout.addStretch()
        layout.addWidget(self.content, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()


class WorkflowStep(QFrame):
    """Compact instructional card used by first-use and empty workflows."""

    def __init__(self, step: int, title: str, subtitle: str, icon_name: str) -> None:
        super().__init__()
        self.setObjectName("WorkflowStep")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(142)
        self.setAccessibleName(f"Passo {step}: {title}")
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(7)
        top = QHBoxLayout()
        icon = ThemedIconLabel(icon_name, 18)
        icon.setObjectName("StepIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(38, 38)
        number = QLabel(f"PASSO {step}")
        number.setObjectName("SectionEyebrow")
        top.addWidget(icon)
        top.addStretch()
        top.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setWordWrap(True)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        subtitle_label.setWordWrap(True)
        subtitle_label.setMinimumWidth(0)
        layout.addLayout(top)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()


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
