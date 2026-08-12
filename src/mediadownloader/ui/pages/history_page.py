"""Searchable local-only download history, presented as touch-friendly cards."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from mediadownloader.models import DownloadItem
from mediadownloader.services import HistoryService
from mediadownloader.utils.paths import reveal_in_explorer

from ..icons import svg_icon
from ..widgets import (
    EmptyState, PageHeader, SecondaryButton, WheelSafeComboBox, enable_touch_scrolling,
)


class HistoryCard(QFrame):
    """Compact summary that exposes the most common history actions directly."""

    def __init__(self, item: DownloadItem, page: "HistoryPage") -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(f"Download concluído: {item.title}")
        root = QVBoxLayout(self)
        root.setContentsMargins(13, 13, 13, 13)
        root.setSpacing(7)

        title = QLabel(item.title)
        title.setObjectName("SectionTitle")
        title.setWordWrap(True)
        title.setMinimumWidth(0)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        meta = QLabel(
            f"{item.platform or 'Mídia'}  •  {item.format.upper()}  •  {item.quality or 'Automática'}"
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        meta.setMinimumWidth(0)
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        date = item.completed_at[:16].replace("T", " ") if item.completed_at else "Data não informada"
        detail = QLabel(f"{date}  •  {item.status.label}")
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        detail.setMinimumWidth(0)
        detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        root.addWidget(title)
        root.addWidget(meta)
        root.addWidget(detail)

        actions = QHBoxLayout()
        actions.setSpacing(7)
        open_file = SecondaryButton("Arquivo", icon_name="file")
        open_folder = SecondaryButton("Pasta", icon_name="folder")
        more = SecondaryButton("Mais", icon_name="list")
        open_file.clicked.connect(lambda: page._open_file(item))
        open_folder.clicked.connect(lambda: page._open_folder(item))
        more.clicked.connect(lambda: page._menu(item, more))
        actions.addWidget(open_file, 1)
        actions.addWidget(open_folder, 1)
        actions.addWidget(more, 1)
        root.addLayout(actions)


class HistoryPage(QWidget):
    redownload_requested = Signal(object)

    def __init__(self, history: HistoryService) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.history = history
        self._items: dict[str, DownloadItem] = {}
        self.cards: list[HistoryCard] = []
        self._visible_limit = 50
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(250)
        self._reload_timer.timeout.connect(self.reload)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 18, 16, 22)
        root.setSpacing(12)
        root.addWidget(PageHeader(
            "Histórico", "Downloads concluídos salvos neste computador.", "history"
        ))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar histórico...")
        self.search.setAccessibleName("Pesquisar histórico")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(svg_icon("analyze", 17), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._schedule_reload)
        root.addWidget(self.search)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.filter = WheelSafeComboBox()
        self.filter.setAccessibleName("Filtrar histórico por tipo")
        self.filter.addItem("Todos", "all")
        self.filter.addItem("Vídeo", "video")
        self.filter.addItem("Áudio", "audio")
        self.filter.currentIndexChanged.connect(self._reset_and_reload)
        clear = SecondaryButton("Limpar", icon_name="trash")
        clear.setAccessibleName("Limpar histórico")
        clear.clicked.connect(self._clear)
        tools.addWidget(self.filter, 1)
        tools.addWidget(clear)
        root.addLayout(tools)

        self.empty = EmptyState(
            "Seu histórico está vazio", "Downloads concluídos aparecerão aqui.", "history"
        )
        root.addWidget(self.empty, 1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        enable_touch_scrolling(self.scroll)
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(9)
        self.more_button = SecondaryButton("Mostrar mais", icon_name="list")
        self.more_button.clicked.connect(self._load_more)
        self.list_layout.addWidget(self.more_button)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)
        self.reload()

    def _schedule_reload(self, _text: str) -> None:
        self._visible_limit = 50
        self._reload_timer.start()

    def _reset_and_reload(self, *_: object) -> None:
        self._visible_limit = 50
        self.reload()

    def _load_more(self) -> None:
        self._visible_limit += 50
        self.reload()

    def reload(self, *_: object) -> None:
        items = self.history.completed(self.search.text(), str(self.filter.currentData()))
        self._items = {item.id: item for item in items}
        for card in self.cards:
            self.list_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        for item in items[:self._visible_limit]:
            card = HistoryCard(item, self)
            self.cards.append(card)
            self.list_layout.insertWidget(self.list_layout.indexOf(self.more_button), card)
        empty = not items
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)
        self.more_button.setVisible(len(items) > self._visible_limit)

    def _open_file(self, item: DownloadItem) -> None:
        path = Path(item.final_file) if item.final_file else None
        if path is not None and path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, "Arquivo não encontrado", "O arquivo não existe mais nesse local.")

    def _open_folder(self, item: DownloadItem) -> None:
        target = item.final_file or item.output_path
        if target:
            reveal_in_explorer(target, select_file=bool(item.final_file))
        else:
            QMessageBox.warning(self, "Pasta não encontrada", "O local deste download não está disponível.")

    def _menu(self, item: DownloadItem, anchor: QWidget) -> None:
        menu = QMenu(self)
        copy_url = menu.addAction("Copiar URL")
        redownload = menu.addAction("Baixar novamente")
        menu.addSeparator()
        remove = menu.addAction("Remover do histórico")
        chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if chosen == copy_url:
            QApplication.clipboard().setText(item.url)
        elif chosen == redownload:
            self.redownload_requested.emit(item)
        elif chosen == remove:
            self.history.delete(item.id)
            self.reload()

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, "Limpar histórico",
            "Remover todo o histórico concluído? Os arquivos baixados serão preservados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear_completed()
            self.reload()
