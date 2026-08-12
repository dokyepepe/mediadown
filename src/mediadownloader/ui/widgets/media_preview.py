"""Analyzed media summary card."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from mediadownloader.models import MediaInfo
from mediadownloader.utils.formatting import format_duration

from .common import ThumbnailLabel


class MediaPreviewCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName("Resumo da mídia analisada")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(11)
        self.thumbnail = ThumbnailLabel(240, 135)
        text = QVBoxLayout()
        text.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("SectionTitle")
        self.title.setWordWrap(True)
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.author = QLabel()
        self.author.setObjectName("Muted")
        self.author.setWordWrap(True)
        self.author.setMinimumWidth(0)
        self.author.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.details = QLabel()
        self.details.setObjectName("Muted")
        self.details.setWordWrap(True)
        self.details.setMinimumWidth(0)
        self.details.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(self.title)
        text.addWidget(self.author)
        text.addWidget(self.details)
        layout.addWidget(self.thumbnail, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(text)

    def set_media(self, media: MediaInfo) -> None:
        kind = "playlist" if media.is_playlist else "mídia"
        self.setAccessibleDescription(
            f"{kind}: {media.title}. Autor: {media.author or 'não informado'}. "
            f"Origem: {media.platform or 'desconhecida'}."
        )
        self.title.setText(media.title)
        self.author.setText(media.author or "Autor não informado")
        if media.is_playlist:
            self.details.setText(f"{media.platform or 'Playlist'}  •  Playlist  •  {media.playlist_count} itens")
        else:
            self.details.setText(f"{media.platform or 'Origem desconhecida'}  •  {format_duration(media.duration)}")
        self.thumbnail.set_preserve_artwork(media.platform == "Spotify")
        self.thumbnail.load(media.thumbnail)
