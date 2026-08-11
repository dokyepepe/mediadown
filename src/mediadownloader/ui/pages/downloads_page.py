"""Visual bounded queue and its global controls."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

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
        root.setSpacing(14)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(PageHeader(
            "Downloads", "Acompanhe a fila e o processamento de mídia.", "downloads"
        ))
        controls = QHBoxLayout()
        self.pause_button = SecondaryButton("Pausar fila", icon_name="pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        cancel_all = SecondaryButton("Cancelar todos", icon_name="cancel")
        cancel_all.setProperty("role", "danger")
        cancel_all.clicked.connect(queue.cancel_all)
        clear = SecondaryButton("Limpar concluídos", icon_name="trash")
        clear.clicked.connect(self._clear_completed)
        controls.addWidget(self.pause_button)
        controls.addWidget(cancel_all)
        controls.addWidget(clear)
        header.addLayout(title_box)
        header.addStretch()
        header.addLayout(controls)
        root.addLayout(header)
        self.empty = EmptyState("Nenhum download em andamento", "Os downloads adicionados aparecerão aqui.", "downloads")
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

    def add_item(self, item: DownloadItem) -> None:
        card = DownloadCard(item)
        card.cancel_requested.connect(self.queue.cancel)
        card.retry_requested.connect(self.queue.retry)
        card.remove_requested.connect(self._remove)
        self.cards[item.id] = card
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        self._update_empty()

    def update_item(self, item: DownloadItem) -> None:
        if card := self.cards.get(item.id):
            card.update_item(item)

    def _remove(self, item_id: str) -> None:
        self.queue.remove(item_id)
        if card := self.cards.pop(item_id, None):
            card.deleteLater()
        self._update_empty()

    def _clear_completed(self) -> None:
        self.queue.clear_completed()
        for item_id, card in list(self.cards.items()):
            item = self.queue.items.get(item_id)
            if item is None or item.status == DownloadStatus.COMPLETED:
                self.cards.pop(item_id)
                card.deleteLater()
        self._update_empty()

    def _toggle_pause(self) -> None:
        if self.queue.paused:
            self.queue.resume()
            self.pause_button.setText("Pausar fila")
            set_button_icon(self.pause_button, "pause")
        else:
            self.queue.pause()
            self.pause_button.setText("Continuar fila")
            set_button_icon(self.pause_button, "play")

    def _update_empty(self) -> None:
        empty = not self.cards
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)
