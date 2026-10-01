"""Visual bounded queue and its global controls."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from mediadownloader.core import QueueManager
from mediadownloader.core.download_gate import format_minute
from mediadownloader.core.queue_filters import QueueFilter, filter_counts, filter_items
from mediadownloader.i18n import tr
from mediadownloader.models import DownloadItem, DownloadStatus

from ..icons import set_button_icon
from ..widgets import DownloadCard, EmptyState, PageHeader, SecondaryButton

#: Filter chips, in display order: ``(filter, label, icon)``.
FILTER_CHIPS: tuple[tuple[QueueFilter, str, str], ...] = (
    (QueueFilter.ALL, "Todos", "list"),
    (QueueFilter.ACTIVE, "Em andamento", "play"),
    (QueueFilter.COMPLETED, "Concluídos", "check"),
    (QueueFilter.FAILED, "Com erro", "cancel"),
)


class DownloadsPage(QWidget):
    def __init__(self, queue: QueueManager) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.queue = queue
        self.cards: dict[str, DownloadCard] = {}
        self.query = ""
        self.filter_mode = QueueFilter.ALL
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(16)
        root.addWidget(PageHeader(
            "Downloads", "Acompanhe a fila e o processamento de mídia.", "downloads"
        ))

        self.gate_banner = QFrame()
        self.gate_banner.setObjectName("Notice")
        self.gate_banner.setProperty("state", "info")
        self.gate_banner.setAccessibleName("Aviso de agendamento da fila")
        gate_layout = QHBoxLayout(self.gate_banner)
        gate_layout.setContentsMargins(13, 11, 13, 11)
        gate_layout.setSpacing(10)
        self.gate_label = QLabel()
        self.gate_label.setWordWrap(True)
        gate_layout.addWidget(self.gate_label, 1)
        root.addWidget(self.gate_banner)

        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 12, 15, 12)
        toolbar_layout.setSpacing(12)
        summary = QVBoxLayout()
        summary.setSpacing(1)
        self.queue_summary = QLabel(tr("Fila pronta"))
        self.queue_summary.setObjectName("SectionTitle")
        self.queue_caption = QLabel(tr("Adicione uma mídia para começar"))
        self.queue_caption.setObjectName("Muted")
        summary.addWidget(self.queue_summary)
        summary.addWidget(self.queue_caption)
        controls = QHBoxLayout()
        controls.setSpacing(7)
        self.pause_button = SecondaryButton(tr("Pausar fila"), icon_name="pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        self.cancel_all_button = SecondaryButton(tr("Cancelar todos"), icon_name="cancel")
        self.cancel_all_button.setProperty("role", "danger")
        self.cancel_all_button.clicked.connect(self._confirm_cancel_all)
        self.clear_button = SecondaryButton(tr("Limpar concluídos"), icon_name="trash")
        self.clear_button.clicked.connect(self._clear_completed)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.cancel_all_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()
        toolbar_layout.addLayout(summary)
        toolbar_layout.addLayout(controls)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Buscar por título, autor, plataforma ou link"))
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar downloads")
        self.search.textChanged.connect(self._search_changed)
        toolbar_layout.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(7)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.chips: dict[QueueFilter, QPushButton] = {}
        for mode, label, icon_name in FILTER_CHIPS:
            chip = QPushButton(tr(label))
            chip.setCheckable(True)
            chip.setProperty("segment", "true")
            set_button_icon(chip, icon_name)
            chip.setAccessibleName(tr("Filtrar por {label}").format(label=tr(label).lower()))
            chip.clicked.connect(lambda _checked=False, mode=mode: self._select_filter(mode))
            self.chip_group.addButton(chip)
            self.chips[mode] = chip
            chips.addWidget(chip)
        self.chips[QueueFilter.ALL].setChecked(True)
        chips.addStretch()
        toolbar_layout.addLayout(chips)
        root.addWidget(toolbar)
        self.empty = EmptyState(
            tr("Sua fila está livre"),
            tr("Quando você adicionar uma mídia, ela aparecerá aqui."),
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
        queue.gate_changed.connect(self._gate_changed)
        self._refresh_gate_banner(queue.gate_blocked, queue.gate_reason)
        self._update_controls()

    def add_item(self, item: DownloadItem) -> None:
        card = DownloadCard(item)
        card.cancel_requested.connect(self.queue.cancel)
        card.retry_requested.connect(self.queue.retry)
        card.remove_requested.connect(self._remove)
        card.pause_requested.connect(self._pause_item)
        card.resume_requested.connect(self._resume_item)
        card.move_requested.connect(self._move_item)
        self.cards[item.id] = card
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        self._refresh_cards()
        self._update_controls()

    def update_item(self, item: DownloadItem) -> None:
        if card := self.cards.get(item.id):
            card.update_item(item, *self._move_flags(item.id))
        self._update_counts()
        self._update_controls()

    def _pause_item(self, item_id: str) -> None:
        self.queue.pause_item(item_id)
        self._refresh_cards()

    def _resume_item(self, item_id: str) -> None:
        self.queue.resume_item(item_id)
        self._refresh_cards()

    def _move_item(self, item_id: str, up: bool) -> None:
        """Reorder the queue; :meth:`_refresh_cards` mirrors the new order."""
        if self.queue.move_item(item_id, up):
            self._refresh_cards()

    def _display_order(self, visible_ids: set[str]) -> list[str]:
        """Waiting items first, in queue order, then everything else as inserted.

        Only queued items can be reordered, so showing them in the order the queue
        will actually run them is what makes the move buttons predictable.
        """
        order = [
            item.id
            for item, _options in self.queue.pending
            if item.id in visible_ids
        ]
        ordered = set(order)
        order.extend(
            item_id for item_id in self.cards if item_id in visible_ids and item_id not in ordered
        )
        return order

    def _move_flags(self, item_id: str) -> tuple[bool, bool]:
        return self.queue.can_move(item_id, True), self.queue.can_move(item_id, False)

    def _remove(self, item_id: str) -> None:
        self.queue.remove(item_id)
        if card := self.cards.pop(item_id, None):
            self.list_layout.removeWidget(card)
            card.deleteLater()
        self._refresh_cards()
        self._update_controls()

    def _clear_completed(self) -> None:
        self.queue.clear_completed()
        for item_id, card in list(self.cards.items()):
            item = self.queue.items.get(item_id)
            if item is None or item.status == DownloadStatus.COMPLETED:
                self.cards.pop(item_id)
                self.list_layout.removeWidget(card)
                card.deleteLater()
        self._refresh_cards()
        self._update_controls()

    def _confirm_cancel_all(self) -> None:
        if not self.queue.has_active:
            return
        answer = QMessageBox.question(
            self,
            tr("Cancelar downloads"),
            tr("Cancelar todos os downloads ativos e pendentes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.queue.cancel_all()

    def _toggle_pause(self) -> None:
        if self.queue.paused:
            self.queue.resume()
            self.pause_button.setText(tr("Pausar fila"))
            set_button_icon(self.pause_button, "pause")
        else:
            self.queue.pause()
            self.pause_button.setText(tr("Continuar fila"))
            set_button_icon(self.pause_button, "play")
        self._update_controls()

    def _search_changed(self, text: str) -> None:
        self.query = text
        self._refresh_cards()

    def _select_filter(self, mode: QueueFilter) -> None:
        self.filter_mode = mode
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        """Reorder and show only the cards matching the search and the filter."""
        visible_ids = {
            item.id
            for item in filter_items(
                self.queue.items.values(), self.query, self.filter_mode
            )
        }
        for item_id, card in self.cards.items():
            card.setVisible(item_id in visible_ids)
        for item_id in self._display_order(visible_ids):
            if card := self.cards.get(item_id):
                self.list_layout.removeWidget(card)
                self.list_layout.insertWidget(self.list_layout.count() - 1, card)
                card.refresh_move_flags(*self._move_flags(item_id))
        self._update_empty()
        self._update_counts()

    def _update_counts(self) -> None:
        counts = filter_counts(self.queue.items.values())
        for mode, _label, _icon_name in FILTER_CHIPS:
            chip = self.chips[mode]
            label = tr(_label)
            chip.setText(f"{label} · {counts[mode]}")
            chip.setAccessibleName(tr("{label}: {count} itens").format(label=label, count=counts[mode]))

    def _update_empty(self) -> None:
        empty = not self.cards
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)
        if empty:
            return
        matching = sum(1 for card in self.cards.values() if not card.isHidden())
        if matching == 0:
            self.empty.set_title(tr("Nada corresponde ao filtro"))
            self.empty.set_subtitle(tr("Ajuste a busca ou escolha outro filtro para ver os itens."))
            self.empty.setVisible(True)
        else:
            self.empty.set_title(tr("Sua fila está livre"))
            self.empty.set_subtitle(tr("Quando você adicionar uma mídia, ela aparecerá aqui."))

    def _gate_changed(self, blocked: bool, reason: str) -> None:
        self._refresh_gate_banner(blocked, reason)
        self._update_controls()

    def _refresh_gate_banner(self, blocked: bool, reason: str) -> None:
        if blocked:
            self.gate_label.setText(
                tr("Fila aguardando: {reason}. Os itens continuam salvos e começam sozinhos.").format(
                    reason=reason
                )
            )
            self.gate_banner.setProperty("state", "info")
        else:
            window = self.queue.gate_config
            if window.window_enabled:
                self.gate_label.setText(
                    tr("Fila liberada pela janela {start}–{end}.").format(
                        start=format_minute(window.window_start_minute),
                        end=format_minute(window.window_end_minute),
                    )
                )
            else:
                self.gate_label.setText(
                    tr("Fila liberada. Sem janela de horário ou limite de espaço.")
                )
            self.gate_banner.setProperty("state", "neutral")
        self.gate_banner.style().unpolish(self.gate_banner)
        self.gate_banner.style().polish(self.gate_banner)
        self.gate_banner.setVisible(True)

    def _update_controls(self) -> None:
        active = self.queue.has_active
        completed = any(item.status == DownloadStatus.COMPLETED for item in self.queue.items.values())
        self.pause_button.setEnabled(active)
        self.cancel_all_button.setEnabled(active)
        self.clear_button.setEnabled(completed)
        in_progress = sum(not item.status.terminal for item in self.queue.items.values())
        needs_attention = sum(
            item.status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}
            for item in self.queue.items.values()
        )
        finished = sum(item.status == DownloadStatus.COMPLETED for item in self.queue.items.values())
        if self.queue.gate_blocked and active:
            title = tr("Fila aguardando")
            caption = self.queue.gate_reason or tr("Downloads liberados automaticamente em instantes")
        elif self.queue.paused and active:
            title = tr("Fila pausada")
            caption = tr("{count} item(ns) aguardando continuação").format(count=in_progress)
        elif in_progress:
            title = tr("{count} item(ns) em andamento").format(count=in_progress)
            caption = tr("{done} concluído(s)  •  {failed} com erro").format(
                done=finished, failed=needs_attention
            )
        elif self.cards:
            title = tr("Fila processada")
            caption = tr("{done} concluído(s)  •  {failed} com erro").format(
                done=finished, failed=needs_attention
            )
        else:
            title = tr("Fila pronta")
            caption = tr("Adicione uma mídia para começar")
        self.queue_summary.setText(title)
        self.queue_caption.setText(caption)
        self.queue_summary.setAccessibleName(
            tr("Estado da fila: {title}. {caption}").format(title=title, caption=caption)
        )
