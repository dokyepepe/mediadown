"""Visual representation and controls for a queued download."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout,
)

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.utils.formatting import format_bytes, format_eta
from mediadownloader.utils.paths import reveal_in_explorer

from ..icons import set_button_icon
from .common import StatusBadge, ThumbnailLabel


class DownloadCard(QFrame):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, item: DownloadItem) -> None:
        super().__init__()
        self.item_id = item.id
        self.setObjectName("Card")
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)
        self.thumbnail = ThumbnailLabel(120, 68)
        self.thumbnail.load(item.thumbnail)
        root.addWidget(self.thumbnail)

        center = QVBoxLayout()
        center.setSpacing(5)
        title_row = QHBoxLayout()
        self.title = QLabel(item.title)
        self.title.setObjectName("SectionTitle")
        self.title.setWordWrap(True)
        self.badge = StatusBadge()
        title_row.addWidget(self.title, 1)
        title_row.addWidget(self.badge)
        self.meta = QLabel()
        self.meta.setObjectName("Muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Progresso do download")
        self.stats = QLabel()
        self.stats.setObjectName("Muted")
        self.error = QLabel()
        self.error.setObjectName("ErrorText")
        self.error.setWordWrap(True)
        self.error.hide()
        center.addLayout(title_row)
        center.addWidget(self.meta)
        center.addWidget(self.progress)
        center.addWidget(self.stats)
        center.addWidget(self.error)
        root.addLayout(center, 1)

        actions = QVBoxLayout()
        self.primary_action = QPushButton()
        self.primary_action.clicked.connect(self._primary_clicked)
        self.folder_button = QPushButton("Abrir pasta")
        set_button_icon(self.folder_button, "folder")
        self.folder_button.clicked.connect(self._open_folder)
        self.remove_button = QPushButton("Remover")
        set_button_icon(self.remove_button, "trash")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        self.copy_details_button = QPushButton("Copiar detalhes")
        set_button_icon(self.copy_details_button, "copy")
        self.copy_details_button.clicked.connect(self._copy_details)
        actions.addWidget(self.primary_action)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.copy_details_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        root.addLayout(actions)
        self._item = item
        self.setAccessibleName(f"Download: {item.title}")
        self.update_item(item)

    def update_item(self, item: DownloadItem) -> None:
        self._item = item
        self.setAccessibleDescription(
            f"{item.status.label}. {item.progress:.0f} por cento. "
            f"{item.format.upper()}, {item.quality}."
        )
        self.badge.set_status(item.status)
        self.meta.setText(f"{item.platform or 'Mídia'}  •  {item.format.upper()}  •  {item.quality}")
        self.progress.setValue(int(item.progress * 10))
        self.progress.setAccessibleDescription(f"{item.progress:.0f} por cento concluído.")
        downloaded = format_bytes(item.downloaded_bytes)
        total = format_bytes(item.total_bytes)
        speed = f"{format_bytes(item.speed)}/s" if item.speed else "—"
        eta = f"{format_eta(item.eta)} restantes" if item.eta is not None else "—"
        if item.status in {DownloadStatus.MERGING, DownloadStatus.CONVERTING, DownloadStatus.FINALIZING}:
            self.stats.setText("Processando mídia… o download só termina após esta etapa.")
        else:
            self.stats.setText(f"{speed}   •   {downloaded} / {total}   •   {eta}")
        self.error.setText(item.error)
        self.error.setVisible(bool(item.error))
        active = not item.status.terminal
        self.primary_action.setText(
            "Tentar novamente" if item.status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}
            else "Abrir arquivo" if item.status == DownloadStatus.COMPLETED
            else "Cancelar"
        )
        action_icon = (
            "retry" if item.status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}
            else "file" if item.status == DownloadStatus.COMPLETED
            else "cancel"
        )
        set_button_icon(self.primary_action, action_icon)
        self.primary_action.setAccessibleName(self.primary_action.text())
        self.folder_button.setVisible(item.status == DownloadStatus.COMPLETED)
        self.copy_details_button.setVisible(item.status == DownloadStatus.ERROR and bool(item.technical_error))
        self.remove_button.setVisible(item.status.terminal)
        self.progress.setVisible(item.status != DownloadStatus.ERROR)
        processing = item.status in {
            DownloadStatus.MERGING, DownloadStatus.CONVERTING, DownloadStatus.FINALIZING,
        }
        if processing:
            self.primary_action.setText("Processando…")
            set_button_icon(self.primary_action, "settings")
            self.primary_action.setToolTip("O FFmpeg precisa concluir a etapa atual com segurança.")
        else:
            self.primary_action.setToolTip("")
        self.primary_action.setEnabled(not processing)

    def _primary_clicked(self) -> None:
        if self._item.status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}:
            self.retry_requested.emit(self.item_id)
        elif self._item.status == DownloadStatus.COMPLETED:
            path = Path(self._item.final_file)
            if path.exists():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                QMessageBox.warning(self, "Arquivo não encontrado", "O arquivo não existe mais nesse local.")
        else:
            self.cancel_requested.emit(self.item_id)

    def _open_folder(self) -> None:
        reveal_in_explorer(self._item.final_file or self._item.output_path, select_file=True)

    def _copy_details(self) -> None:
        QApplication.clipboard().setText(self._item.technical_error or self._item.error)
