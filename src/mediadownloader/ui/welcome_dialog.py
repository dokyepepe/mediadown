"""Short first-run welcome dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from .widgets import PrimaryButton, ThemedIconLabel


class WelcomeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bem-vindo")
        self.setModal(True)
        self.resize(340, 360)
        self.setMinimumSize(300, 280)
        self.setMaximumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 32, 26, 26)
        layout.setSpacing(14)
        logo = ThemedIconLabel("brand", 58)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Bem-vindo ao Media Downloader")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("PageTitle")
        title.setWordWrap(True)
        body = QLabel("Baixe e converta mídias em uma interface simples e organizada.")
        body.setObjectName("Muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        start = PrimaryButton("COMEÇAR", icon_name="check")
        start.clicked.connect(self.accept)
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch()
        layout.addWidget(start)
