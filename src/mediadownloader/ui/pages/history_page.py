"""Searchable local-only download history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
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
        root.setSpacing(16)
        root.addWidget(PageHeader(
            "Histórico", "Downloads concluídos ficam salvos somente neste computador.", "history"
        ))
        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(14, 12, 14, 12)
        tools.setSpacing(9)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar por título, site ou formato…")
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
        self.count_label = QLabel("0 itens")
        self.count_label.setObjectName("Muted")
        clear = SecondaryButton("Limpar histórico", icon_name="trash")
        clear.clicked.connect(self._clear)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.filter)
        tools.addWidget(self.count_label)
        tools.addWidget(clear)
        root.addWidget(toolbar)
        self.empty = EmptyState(
            "Seu histórico está vazio",
            "Downloads concluídos serão organizados aqui, somente neste computador.",
            "history",
        )
        root.addWidget(self.empty, 1)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Título", "Origem", "Formato", "Qualidade", "Data", "Status", "Arquivo"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setAccessibleName("Histórico de downloads concluídos")
        self.table.setAccessibleDescription("Use as setas para navegar pelas linhas e Shift+F10 para abrir as ações.")
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemDoubleClicked.connect(lambda _cell: self._open_selected_file())
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
                display_value = Path(value).name if column == 6 and value else value
                cell = QTableWidgetItem(display_value)
                if column == 6 and value:
                    cell.setToolTip(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self.table.setItem(row, column, cell)
        count = len(items)
        self.count_label.setText(f"{count} item" if count == 1 else f"{count} itens")
        self.count_label.setAccessibleName(f"{count} itens no histórico")
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
        if chosen == open_file:
            self._open_file(item)
        elif chosen == open_folder:
            self._open_folder(item)
        elif chosen == copy_url:
            QApplication.clipboard().setText(item.url)
        elif chosen == redownload:
            self.redownload_requested.emit(item)
        elif chosen == remove:
            self.history.delete(item.id)
            self.reload()

    def _open_selected_file(self) -> None:
        if item := self._selected():
            self._open_file(item)

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

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "Limpar histórico",
            "Remover todo o histórico concluído? Os arquivos baixados serão preservados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear_completed()
            self.reload()
