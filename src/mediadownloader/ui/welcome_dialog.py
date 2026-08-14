"""Short first-run welcome dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from .widgets import PrimaryButton, ThemedIconLabel


class WelcomeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bem-vindo")
        self.setModal(True)
        self.setAccessibleName("Boas-vindas ao Media Downloader")
        self.setAccessibleDescription("Apresentação inicial do aplicativo.")
        self.setMinimumSize(500, 360)
        self.resize(520, 380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(44, 38, 44, 38)
        layout.setSpacing(12)
        logo = ThemedIconLabel("brand", 58)
        logo.setObjectName("TintedIcon")
        logo.setFixedSize(84, 84)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow = QLabel("SEU CONVERSOR DE MÍDIA")
        eyebrow.setObjectName("SectionEyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Bem-vindo ao Media Downloader")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("HeroName")
        title.setWordWrap(True)
        body = QLabel(
            "Cole um link, escolha o formato ideal e acompanhe cada etapa em uma interface clara."
        )
        body.setObjectName("Muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        capabilities = QHBoxLayout()
        capabilities.setSpacing(7)
        capabilities.addStretch()
        for text in ("VÍDEO", "ÁUDIO", "PLAYLISTS"):
            badge = QLabel(text)
            badge.setObjectName("MetaPill")
            capabilities.addWidget(badge)
        capabilities.addStretch()
        start = PrimaryButton("COMEÇAR AGORA", icon_name="check")
        start.setDefault(True)
        start.clicked.connect(self.accept)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(capabilities)
        layout.addStretch()
        layout.addWidget(start)
