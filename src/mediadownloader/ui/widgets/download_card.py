"""Visual representation and controls for a queued download."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout,
)

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.utils.formatting import format_bytes, format_eta
from mediadownloader.utils.paths import open_local_file, reveal_in_explorer

from ..icons import set_button_icon
from .common import StatusBadge, ThumbnailLabel


class DownloadCard(QFrame):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    remove_requested = Signal(str)
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    move_requested = Signal(str, bool)
    #: ``(item_id, url)`` — emitted after the URL reaches the clipboard.
    link_copied = Signal(str, str)

    def __init__(self, item: DownloadItem) -> None:
        super().__init__()
        self.item_id = item.id
        self.setObjectName("DownloadCard")
        root = QHBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)
        self.thumbnail = ThumbnailLabel(124, 70)
        self.thumbnail.load(item.thumbnail)
        root.addWidget(self.thumbnail)

        center = QVBoxLayout()
        center.setSpacing(7)
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
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        progress_row.addWidget(self.stats, 1)
        self.progress_percent = QLabel("0%")
        self.progress_percent.setObjectName("SectionEyebrow")
        self.progress_percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        progress_row.addWidget(self.progress_percent)
        self.error = QLabel()
        self.error.setObjectName("ErrorText")
        self.error.setWordWrap(True)
        self.error.hide()
        center.addLayout(title_row)
        center.addWidget(self.meta)
        center.addWidget(self.progress)
        center.addLayout(progress_row)
        center.addWidget(self.error)

        actions = QHBoxLayout()
        actions.setSpacing(7)
        actions.addStretch()
        self.move_up_button = QPushButton()
        set_button_icon(self.move_up_button, "up")
        self.move_up_button.setToolTip("Mover para cima na fila")
        self.move_up_button.clicked.connect(lambda: self.move_requested.emit(self.item_id, True))
        self.move_down_button = QPushButton()
        set_button_icon(self.move_down_button, "down")
        self.move_down_button.setToolTip("Mover para baixo na fila")
        self.move_down_button.clicked.connect(lambda: self.move_requested.emit(self.item_id, False))
        self.move_up_button.setAccessibleName("Mover download para cima na fila")
        self.move_down_button.setAccessibleName("Mover download para baixo na fila")
        self.primary_action = QPushButton()
        self.primary_action.clicked.connect(self._primary_clicked)
        self.cancel_button = QPushButton()
        set_button_icon(self.cancel_button, "cancel")
        self.cancel_button.setProperty("role", "danger")
        self.cancel_button.setToolTip("Cancelar este download e mantê-lo na lista")
        self.cancel_button.setAccessibleName("Cancelar download")
        self.cancel_button.clicked.connect(lambda: self.cancel_requested.emit(self.item_id))
        self.folder_button = QPushButton("Abrir pasta")
        set_button_icon(self.folder_button, "folder")
        self.folder_button.clicked.connect(self._open_folder)
        self.remove_button = QPushButton("Remover")
        set_button_icon(self.remove_button, "trash")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        self.copy_details_button = QPushButton("Copiar detalhes")
        set_button_icon(self.copy_details_button, "copy")
        self.copy_details_button.clicked.connect(self._copy_details)
        self.copy_link_button = QPushButton("Copiar link")
        set_button_icon(self.copy_link_button, "copy")
        self.copy_link_button.setToolTip("Copiar o endereço original para a área de transferência")
        self.copy_link_button.clicked.connect(self._copy_link)
        actions.addWidget(self.move_up_button)
        actions.addWidget(self.move_down_button)
        actions.addWidget(self.primary_action)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.copy_link_button)
        actions.addWidget(self.copy_details_button)
        actions.addWidget(self.remove_button)
        center.addLayout(actions)
        root.addLayout(center, 1)
        self._item = item
        self.setAccessibleName(f"Download: {item.title}")
        self.update_item(item)

    def update_item(self, item: DownloadItem, can_move_up: bool = False, can_move_down: bool = False) -> None:
        """Refresh the card, including which reorder buttons make sense right now."""
        self._item = item
        self.setAccessibleDescription(
            f"{item.status.label}. {item.progress:.0f} por cento. "
            f"{item.format.upper()}, {item.quality}."
        )
        self.badge.set_status(item.status)
        self.meta.setText(f"{item.platform or 'Mídia'}  •  {item.format.upper()}  •  {item.quality}")
        self.progress.setValue(int(item.progress * 10))
        self.progress.setAccessibleDescription(f"{item.progress:.0f} por cento concluído.")
        self.progress_percent.setText(f"{item.progress:.0f}%")
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
        self.move_up_button.setEnabled(can_move_up)
        self.move_down_button.setEnabled(can_move_down)
        self.move_up_button.setVisible(can_move_up or can_move_down)
        self.move_down_button.setVisible(can_move_up or can_move_down)
        active = not item.status.terminal
        retryable = item.status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}
        paused = item.status == DownloadStatus.PAUSED
        if retryable:
            self.primary_action.setText("Tentar novamente")
        elif item.status == DownloadStatus.COMPLETED:
            self.primary_action.setText("Abrir arquivo")
        elif paused:
            self.primary_action.setText("Continuar")
        else:
            self.primary_action.setText("Pausar")
        action_icon = (
            "retry" if retryable
            else "file" if item.status == DownloadStatus.COMPLETED
            else "play" if paused
            else "pause"
        )
        role = "primary" if retryable or item.status == DownloadStatus.COMPLETED or paused else "danger"
        self.primary_action.setProperty("role", role)
        self.primary_action.style().unpolish(self.primary_action)
        self.primary_action.style().polish(self.primary_action)
        set_button_icon(
            self.primary_action,
            action_icon,
            "#FFFFFF" if role == "primary" else None,
        )
        self.primary_action.setAccessibleName(self.primary_action.text())
        self.folder_button.setVisible(item.status == DownloadStatus.COMPLETED)
        self.cancel_button.setVisible(active)
        self.copy_link_button.setVisible(active)
        self.copy_details_button.setVisible(item.status == DownloadStatus.ERROR and bool(item.technical_error))
        self.remove_button.setVisible(item.status.terminal)
        self.progress.setVisible(item.status != DownloadStatus.ERROR)
        self.progress_percent.setVisible(item.status != DownloadStatus.ERROR)
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

    def refresh_move_flags(self, can_move_up: bool, can_move_down: bool) -> None:
        """Update only the reorder buttons, e.g. after the queue was reordered."""
        self.move_up_button.setEnabled(can_move_up)
        self.move_down_button.setEnabled(can_move_down)
        self.move_up_button.setVisible(can_move_up or can_move_down)
        self.move_down_button.setVisible(can_move_up or can_move_down)

    def _primary_clicked(self) -> None:
        status = self._item.status
        if status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}:
            self.retry_requested.emit(self.item_id)
        elif status == DownloadStatus.COMPLETED:
            path = Path(self._item.final_file)
            if path.exists():
                open_local_file(path)
            else:
                QMessageBox.warning(self, "Arquivo não encontrado", "O arquivo não existe mais nesse local.")
        elif status == DownloadStatus.PAUSED:
            self.resume_requested.emit(self.item_id)
        elif not status.terminal:
            self.pause_requested.emit(self.item_id)

    def _open_folder(self) -> None:
        reveal_in_explorer(self._item.final_file or self._item.output_path, select_file=True)

    def _copy_details(self) -> None:
        QApplication.clipboard().setText(self._item.technical_error or self._item.error)

    def _copy_link(self) -> None:
        QApplication.clipboard().setText(self._item.url)
        self.link_copied.emit(self.item_id, self._item.url)
