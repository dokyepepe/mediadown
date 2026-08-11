"""Searchable local-only download history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
    QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from mediadownloader.models import DownloadItem
from mediadownloader.services import HistoryService
from mediadownloader.utils.paths import reveal_in_explorer

from ..icons import svg_icon
from ..widgets import EmptyState, PageHeader, SecondaryButton, WheelSafeComboBox


class HistoryPage(QWidget):
    redownload_requested = Signal(object)

    def __init__(self, history: HistoryService) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.history = history
        self._items: dict[str, DownloadItem] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(14)
        root.addWidget(PageHeader(
            "Histórico", "Downloads concluídos ficam salvos somente neste computador.", "history"
        ))
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar histórico...")
        self.search.setAccessibleName("Pesquisar histórico")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(svg_icon("analyze", 17), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.reload)
        self.filter = WheelSafeComboBox()
        self.filter.setAccessibleName("Filtrar histórico por tipo")
        self.filter.addItem("Todos", "all")
        self.filter.addItem("Vídeo", "video")
        self.filter.addItem("Áudio", "audio")
        self.filter.currentIndexChanged.connect(self.reload)
        clear = SecondaryButton("Limpar histórico", icon_name="trash")
        clear.clicked.connect(self._clear)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.filter)
        tools.addWidget(clear)
        root.addLayout(tools)
        self.empty = EmptyState("Seu histórico está vazio", "Downloads concluídos aparecerão aqui.", "history")
        root.addWidget(self.empty, 1)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Título", "Origem", "Formato", "Qualidade", "Data", "Status", "Arquivo"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setAccessibleName("Histórico de downloads concluídos")
        self.table.setAccessibleDescription("Use as setas para navegar pelas linhas e Shift+F10 para abrir as ações.")
        self.table.customContextMenuRequested.connect(self._menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)
        self.reload()

    def reload(self, *_: object) -> None:
        items = self.history.completed(self.search.text(), str(self.filter.currentData()))
        self._items = {item.id: item for item in items}
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.title, item.platform, item.format.upper(), item.quality,
                item.completed_at[:16].replace("T", " ") if item.completed_at else "—",
                item.status.label, item.final_file,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self.table.setItem(row, column, cell)
        empty = not items
        self.empty.setVisible(empty)
        self.table.setVisible(not empty)

    def _selected(self) -> DownloadItem | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return self._items.get(item_id)

    def _menu(self, position) -> None:
        item = self._selected()
        if not item:
            return
        menu = QMenu(self)
        open_file = menu.addAction("Abrir arquivo")
        open_folder = menu.addAction("Abrir pasta")
        copy_url = menu.addAction("Copiar URL")
        redownload = menu.addAction("Baixar novamente")
        menu.addSeparator()
        remove = menu.addAction("Remover do histórico")
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        path = Path(item.final_file)
        if chosen == open_file and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif chosen == open_folder:
            reveal_in_explorer(path, select_file=True)
        elif chosen == copy_url:
            QApplication.clipboard().setText(item.url)
        elif chosen == redownload:
            self.redownload_requested.emit(item)
        elif chosen == remove:
            self.history.delete(item.id)
            self.reload()

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, "Limpar histórico", "Remover todo o histórico concluído? Os arquivos baixados serão preservados."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear_completed()
            self.reload()
