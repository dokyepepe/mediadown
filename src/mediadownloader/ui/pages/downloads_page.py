"""Visual bounded queue and its global controls."""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from mediadownloader.core import QueueManager
from mediadownloader.models import DownloadItem, DownloadStatus

from ..icons import set_button_icon
from ..widgets import DownloadCard, EmptyState, PageHeader, SecondaryButton


class DownloadsPage(QWidget):
    def __init__(self, queue: QueueManager) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.queue = queue
        self.cards: dict[str, DownloadCard] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(16)
        root.addWidget(PageHeader(
            "Downloads", "Acompanhe a fila e o processamento de mídia.", "downloads"
        ))

        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 12, 15, 12)
        toolbar_layout.setSpacing(12)
        summary = QVBoxLayout()
        summary.setSpacing(1)
        self.queue_summary = QLabel("Fila pronta")
        self.queue_summary.setObjectName("SectionTitle")
        self.queue_caption = QLabel("Adicione uma mídia para começar")
        self.queue_caption.setObjectName("Muted")
        summary.addWidget(self.queue_summary)
        summary.addWidget(self.queue_caption)
        controls = QHBoxLayout()
        controls.setSpacing(7)
        self.pause_button = SecondaryButton("Pausar fila", icon_name="pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        self.cancel_all_button = SecondaryButton("Cancelar todos", icon_name="cancel")
        self.cancel_all_button.setProperty("role", "danger")
        self.cancel_all_button.clicked.connect(self._confirm_cancel_all)
        self.clear_button = SecondaryButton("Limpar concluídos", icon_name="trash")
        self.clear_button.clicked.connect(self._clear_completed)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.cancel_all_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()
        toolbar_layout.addLayout(summary)
        toolbar_layout.addLayout(controls)
        root.addWidget(toolbar)
        self.empty = EmptyState(
            "Sua fila está livre",
            "Quando você adicionar uma mídia, progresso, velocidade e ações aparecerão aqui.",
            "downloads",
        )
        root.addWidget(self.empty, 1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        self.scroll.setWidget(container)
        self.scroll.hide()
        root.addWidget(self.scroll, 1)
        queue.item_added.connect(self.add_item)
        queue.item_updated.connect(self.update_item)
        queue.item_finished.connect(lambda _item: self._update_controls())
        queue.active_count_changed.connect(lambda _count: self._update_controls())
        self._update_controls()

    def add_item(self, item: DownloadItem) -> None:
        card = DownloadCard(item)
        card.cancel_requested.connect(self.queue.cancel)
        card.retry_requested.connect(self.queue.retry)
        card.remove_requested.connect(self._remove)
        self.cards[item.id] = card
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        self._update_empty()
        self._update_controls()

    def update_item(self, item: DownloadItem) -> None:
        if card := self.cards.get(item.id):
            card.update_item(item)
        self._update_controls()

    def _remove(self, item_id: str) -> None:
        self.queue.remove(item_id)
        if card := self.cards.pop(item_id, None):
            card.deleteLater()
        self._update_empty()
        self._update_controls()

    def _clear_completed(self) -> None:
        self.queue.clear_completed()
        for item_id, card in list(self.cards.items()):
            item = self.queue.items.get(item_id)
            if item is None or item.status == DownloadStatus.COMPLETED:
                self.cards.pop(item_id)
                card.deleteLater()
        self._update_empty()
        self._update_controls()

    def _confirm_cancel_all(self) -> None:
        if not self.queue.has_active:
            return
        answer = QMessageBox.question(
            self,
            "Cancelar downloads",
            "Cancelar todos os downloads ativos e pendentes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.queue.cancel_all()

    def _toggle_pause(self) -> None:
        if self.queue.paused:
            self.queue.resume()
            self.pause_button.setText("Pausar fila")
            set_button_icon(self.pause_button, "pause")
        else:
            self.queue.pause()
            self.pause_button.setText("Continuar fila")
            set_button_icon(self.pause_button, "play")
        self._update_controls()

    def _update_empty(self) -> None:
        empty = not self.cards
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)

    def _update_controls(self) -> None:
        active = self.queue.has_active
        completed = any(item.status == DownloadStatus.COMPLETED for item in self.queue.items.values())
        self.pause_button.setEnabled(active)
        self.cancel_all_button.setEnabled(active)
        self.clear_button.setEnabled(completed)
        in_progress = sum(not item.status.terminal for item in self.queue.items.values())
        failed = sum(item.status == DownloadStatus.ERROR for item in self.queue.items.values())
        finished = sum(item.status == DownloadStatus.COMPLETED for item in self.queue.items.values())
        if self.queue.paused and active:
            title = "Fila pausada"
            caption = f"{in_progress} item(ns) aguardando continuação"
        elif in_progress:
            title = f"{in_progress} item(ns) em andamento"
            caption = f"{finished} concluído(s)  •  {failed} com erro"
        elif self.cards:
            title = "Fila processada"
            caption = f"{finished} concluído(s)  •  {failed} com erro"
        else:
            title = "Fila pronta"
            caption = "Adicione uma mídia para começar"
        self.queue_summary.setText(title)
        self.queue_caption.setText(caption)
        self.queue_summary.setAccessibleName(f"Estado da fila: {title}. {caption}")
