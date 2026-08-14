"""Analyzed media summary card."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from mediadownloader.models import MediaInfo
from mediadownloader.utils.formatting import format_duration

from .common import ThumbnailLabel


class MediaPreviewCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MediaPreviewCard")
        self.setAccessibleName("Resumo da mídia analisada")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 18)
        layout.setSpacing(18)
        self.thumbnail = ThumbnailLabel(204, 115)
        text = QVBoxLayout()
        text.setSpacing(7)
        eyebrow_row = QHBoxLayout()
        eyebrow = QLabel("MÍDIA ANALISADA")
        eyebrow.setObjectName("SectionEyebrow")
        self.source_badge = QLabel()
        self.source_badge.setObjectName("MetaPill")
        eyebrow_row.addWidget(eyebrow)
        eyebrow_row.addStretch()
        eyebrow_row.addWidget(self.source_badge)
        self.title = QLabel()
        self.title.setObjectName("SectionTitle")
        self.title.setWordWrap(True)
        self.author = QLabel()
        self.author.setObjectName("Muted")
        self.details = QLabel()
        self.details.setObjectName("Muted")
        text.addLayout(eyebrow_row)
        text.addWidget(self.title)
        text.addWidget(self.author)
        text.addWidget(self.details)
        text.addStretch()
        layout.addWidget(self.thumbnail)
        layout.addLayout(text, 1)

    def set_media(self, media: MediaInfo) -> None:
        kind = "playlist" if media.is_playlist else "mídia"
        self.setAccessibleDescription(
            f"{kind}: {media.title}. Autor: {media.author or 'não informado'}. "
            f"Origem: {media.platform or 'desconhecida'}."
        )
        self.title.setText(media.title)
        self.source_badge.setText(media.platform or "Mídia")
        self.author.setText(media.author or "Autor não informado")
        if media.is_playlist:
            self.details.setText(f"Playlist  •  {media.playlist_count} itens disponíveis")
        else:
            self.details.setText(f"Duração  •  {format_duration(media.duration)}")
        self.thumbnail.set_preserve_artwork(media.platform == "Spotify")
        self.thumbnail.load(media.thumbnail)
