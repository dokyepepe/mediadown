"""Searchable local-only download history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMenu, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from mediadownloader.models import DownloadItem
from mediadownloader.services import HistoryService
from mediadownloader.utils.formatting import format_bytes
from mediadownloader.utils.paths import reveal_in_explorer

from ..icons import svg_icon
from ..widgets import EmptyState, PageHeader, SecondaryButton, WheelSafeComboBox

#: Column indexes, named so the row assembly below stays readable.
TITLE, ORIGIN, FORMAT, QUALITY, SIZE, DATE, FILE = range(7)
COLUMNS = ["Título", "Origem", "Formato", "Qualidade", "Tamanho", "Data", "Arquivo"]
THUMBNAIL_SIZE = (56, 32)


class HistoryPage(QWidget):
    redownload_requested = Signal(object)

    def __init__(self, history: HistoryService) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.history = history
        self._items: dict[str, DownloadItem] = {}
        self._row_ids: list[str] = []
        self.selected: set[str] = set()
        self._thumbnails: dict[str, QIcon] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(16)
        root.addWidget(PageHeader(
            "Histórico", "Downloads concluídos ficam salvos somente neste computador.", "history"
        ))
        self.notice = QLabel()
        self.notice.setObjectName("Notice")
        self.notice.setWordWrap(True)
        self.notice.setAccessibleName("Aviso do histórico")
        self.notice.hide()
        root.addWidget(self.notice)
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
        export = SecondaryButton("Exportar CSV", icon_name="file")
        export.clicked.connect(self._export_csv)
        export.setToolTip("Salva os downloads concluídos como uma planilha CSV, somente neste computador.")
        clear = SecondaryButton("Limpar histórico", icon_name="trash")
        clear.clicked.connect(self._clear)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.filter)
        tools.addWidget(self.count_label)
        tools.addWidget(export)
        tools.addWidget(clear)
        root.addWidget(toolbar)
        self.selection_bar = QFrame()
        self.selection_bar.setObjectName("Toolbar")
        selection_layout = QHBoxLayout(self.selection_bar)
        selection_layout.setContentsMargins(14, 9, 14, 9)
        selection_layout.setSpacing(9)
        self.selection_label = QLabel()
        self.selection_label.setObjectName("SectionTitle")
        self.select_all_button = SecondaryButton("Selecionar todos", icon_name="check")
        self.select_all_button.setToolTip("Marca ou desmarca os itens que a busca está mostrando.")
        self.select_all_button.clicked.connect(self._toggle_select_all)
        self.delete_selected_button = SecondaryButton("Remover selecionados", icon_name="trash")
        self.delete_selected_button.setProperty("role", "danger")
        self.delete_selected_button.clicked.connect(self._delete_selected)
        self.close_selection_button = SecondaryButton("Concluir seleção", icon_name="cancel")
        self.close_selection_button.clicked.connect(self.clear_selection)
        selection_layout.addWidget(self.selection_label)
        selection_layout.addStretch()
        selection_layout.addWidget(self.select_all_button)
        selection_layout.addWidget(self.delete_selected_button)
        selection_layout.addWidget(self.close_selection_button)
        self.selection_bar.hide()
        root.addWidget(self.selection_bar)
        self.empty = EmptyState(
            "Seu histórico está vazio",
            "Downloads concluídos serão organizados aqui, somente neste computador.",
            "history",
        )
        root.addWidget(self.empty, 1)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setIconSize(QSize(*THUMBNAIL_SIZE))
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setAccessibleName("Histórico de downloads concluídos")
        self.table.setAccessibleDescription(
            "Marque a caixa da primeira coluna para selecionar vários itens. "
            "Use as setas para navegar pelas linhas, Shift+F10 para abrir as ações e Esc para sair da seleção."
        )
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemChanged.connect(self._row_check_changed)
        self.table.itemDoubleClicked.connect(lambda _cell: self._open_selected_file())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(TITLE, QHeaderView.ResizeMode.Stretch)
        for column in (ORIGIN, FORMAT, QUALITY, SIZE, DATE):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(FILE, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(FILE, 190)
        root.addWidget(self.table, 1)
        self._thumbnails_manager = QNetworkAccessManager(self)
        self._thumbnails_manager.finished.connect(self._thumbnail_loaded)
        self._pending_thumbnails: dict[str, str] = {}
        select_all = QAction("Selecionar todos os itens visíveis", self)
        select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        select_all.triggered.connect(self._toggle_select_all)
        self.addAction(select_all)
        escape = QAction("Sair da seleção", self)
        escape.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        escape.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.triggered.connect(self.clear_selection)
        self.addAction(escape)
        self.reload()

    def reload(self, *_: object) -> None:
        items = self.history.completed(self.search.text(), str(self.filter.currentData()))
        self._items = {item.id: item for item in items}
        self._row_ids = [item.id for item in items]
        self.selected &= set(self._items)
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.title, item.platform, item.format.upper(), item.quality,
                self._size_text(item), item.completed_at[:16].replace("T", " ") if item.completed_at else "—",
                item.final_file,
            ]
            for column, value in enumerate(values):
                display_value = Path(value).name if column == FILE and value else value
                cell = QTableWidgetItem(display_value)
                if column == FILE and value:
                    cell.setToolTip(value)
                if column == TITLE:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    cell.setCheckState(
                        Qt.CheckState.Checked if item.id in self.selected else Qt.CheckState.Unchecked
                    )
                    self._attach_thumbnail(cell, item)
                self.table.setItem(row, column, cell)
        self.table.blockSignals(False)
        count = len(items)
        self.count_label.setText(f"{count} item" if count == 1 else f"{count} itens")
        self.count_label.setAccessibleName(f"{count} itens no histórico")
        empty = not items
        self.empty.setVisible(empty)
        self.table.setVisible(not empty)
        if not items and self.search.text().strip():
            self.empty.set_title("Nada encontrado")
            self.empty.set_subtitle(f'Nenhum registro corresponde a "{self.search.text().strip()}".')
        else:
            self.empty.set_title("Seu histórico está vazio")
            self.empty.set_subtitle(
                "Downloads concluídos serão organizados aqui, somente neste computador."
            )
        self._update_selection_bar()

    def _size_text(self, item: DownloadItem) -> str:
        """Prefer the recorded size, then the file on disk, and never show 0 B."""
        size = item.file_size or item.total_bytes
        if not size and item.final_file:
            try:
                size = Path(item.final_file).stat().st_size
            except OSError:
                size = 0
        return format_bytes(size) if size else "—"

    def _attach_thumbnail(self, cell: QTableWidgetItem, item: DownloadItem) -> None:
        url = item.thumbnail
        if not url:
            return
        if icon := self._thumbnails.get(url):
            cell.setIcon(icon)
            return
        if url not in self._pending_thumbnails:
            self._pending_thumbnails[url] = url
            request = QNetworkRequest(QUrl(url))
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, True)
            self._thumbnails_manager.get(request)

    def _thumbnail_loaded(self, reply: QNetworkReply) -> None:
        try:
            url = reply.url().toString()
            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap = QPixmap()
                if pixmap.loadFromData(reply.readAll()):
                    self._thumbnails[url] = QIcon(pixmap.scaled(
                        *THUMBNAIL_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
                    self._apply_thumbnail(url)
        finally:
            self._pending_thumbnails.pop(reply.url().toString(), None)
            reply.deleteLater()

    def _apply_thumbnail(self, url: str) -> None:
        icon = self._thumbnails.get(url)
        if icon is None:
            return
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, TITLE)
            item = self._items.get(cell.data(Qt.ItemDataRole.UserRole)) if cell else None
            if item is not None and item.thumbnail == url:
                cell.setIcon(icon)


    def _row_check_changed(self, cell: QTableWidgetItem) -> None:
        if cell.column() != TITLE:
            return
        item_id = cell.data(Qt.ItemDataRole.UserRole)
        if not item_id:
            return
        if cell.checkState() == Qt.CheckState.Checked:
            self.selected.add(item_id)
        else:
            self.selected.discard(item_id)
        self._update_selection_bar()

    def _toggle_select_all(self) -> None:
        if not self._row_ids:
            return
        if set(self._row_ids) <= self.selected:
            self.selected -= set(self._row_ids)
        else:
            self.selected |= set(self._row_ids)
        self._sync_checks()

    def _sync_checks(self) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, TITLE)
            if cell is not None:
                checked = cell.data(Qt.ItemDataRole.UserRole) in self.selected
                cell.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        self.table.blockSignals(False)
        self._update_selection_bar()

    def clear_selection(self) -> None:
        self.selected.clear()
        self._sync_checks()

    def _update_selection_bar(self) -> None:
        count = len(self.selected)
        self.selection_bar.setVisible(count > 0)
        if not count:
            return
        self.selection_label.setText(
            "1 item selecionado" if count == 1 else f"{count} itens selecionados"
        )
        self.selection_label.setAccessibleName(
            f"{count} itens selecionados de {len(self._row_ids)}"
        )
        everything = bool(self._row_ids) and set(self._row_ids) <= self.selected
        self.select_all_button.setText("Limpar seleção" if everything else "Selecionar todos")

    def _selected_items(self) -> list[DownloadItem]:
        return [self._items[item_id] for item_id in self._row_ids if item_id in self.selected]

    def _delete_selected(self) -> None:
        items = self._selected_items()
        if not items:
            return
        answer = QMessageBox.question(
            self,
            "Remover do histórico",
            f"Remover {len(items)} item(ns) do histórico? Os arquivos baixados serão preservados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self.history.delete_many(item.id for item in items)
        self.selected.clear()
        self.reload()
        self._show_notice(
            f"{removed} item(ns) removido(s) do histórico. Os arquivos continuam no computador.",
            "success",
        )


    def _selected(self) -> DownloadItem | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item_id = self.table.item(row, TITLE).data(Qt.ItemDataRole.UserRole)
        return self._items.get(item_id)

    def _menu(self, position) -> None:
        item = self._selected()
        if not item:
            return
        menu = QMenu(self)
        open_file = menu.addAction("Abrir arquivo")
        open_folder = menu.addAction("Abrir pasta")
        share = menu.addAction("Compartilhar arquivo")
        copy_url = menu.addAction("Copiar URL")
        rename = menu.addAction("Renomear arquivo")
        redownload = menu.addAction("Baixar novamente")
        menu.addSeparator()
        if len(self.selected) > 1:
            remove_selected = menu.addAction(
                f"Remover {len(self.selected)} item(ns) selecionados"
            )
            menu.addSeparator()
        else:
            remove_selected = None
            remove = menu.addAction("Remover do histórico")
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen == open_file:
            self._open_file(item)
        elif chosen == open_folder:
            self._open_folder(item)
        elif chosen == share:
            self._share(item)
        elif chosen == copy_url:
            QApplication.clipboard().setText(item.url)
            self._show_notice("URL copiada para a área de transferência.", "success")
        elif chosen == rename:
            self._rename(item)
        elif chosen == redownload:
            self.redownload_requested.emit(item)
        elif chosen == remove_selected:
            self._delete_selected()
        elif chosen == remove:
            self.history.delete(item.id)
            self.reload()

    def _share(self, item: DownloadItem) -> None:
        """Desktop stand-in for the mobile share sheet: put the file path on the clipboard."""
        path = item.final_file or item.output_path
        if not path:
            self._show_notice("Este item não tem um arquivo para compartilhar.", "warning")
            return
        QApplication.clipboard().setText(path)
        self._show_notice(
            f"Caminho copiado para a área de transferência: {path}", "success"
        )

    def _rename(self, item: DownloadItem) -> None:
        current = Path(item.final_file).name if item.final_file else item.title
        typed, accepted = QInputDialog.getText(
            self, "Renomear arquivo", "Novo nome do arquivo:", QLineEdit.EchoMode.Normal, current
        )
        if not accepted:
            return
        trimmed = typed.strip()
        if not trimmed:
            self._show_notice("Informe um nome para o arquivo.", "warning")
            return
        extension = Path(current).suffix
        target_name = trimmed if "." in trimmed or not extension else f"{trimmed}{extension}"
        try:
            path = self.history.rename(item.id, target_name)
        except KeyError:
            self._show_notice("Item não encontrado no histórico.", "warning")
            return
        except FileExistsError as error:
            self._show_notice(f"Já existe um arquivo com esse nome: {Path(str(error)).name}", "warning")
            return
        except OSError as error:
            self._show_notice(f"Não foi possível renomear o arquivo: {error}", "danger")
            return
        self.reload()
        if Path(path).is_file():
            self._show_notice(f"Renomeado para {Path(path).name}.", "success")
        else:
            self._show_notice(
                f"Renomeado para {Path(path).name} (só o nome no app; o arquivo real manteve o título).",
                "warning",
            )

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
            self.selected.clear()
            self.reload()

    def _export_csv(self) -> None:
        items = self.history.completed(self.search.text(), str(self.filter.currentData()))
        if not items:
            QMessageBox.information(self, "Exportar histórico", "Não há downloads concluídos para exportar.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar histórico",
            str(Path.home() / "media_downloader_historico.csv"),
            "Planilha CSV (*.csv)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(self.history.to_csv(items), encoding="utf-8-sig")
        except OSError as error:
            QMessageBox.warning(
                self, "Exportar histórico", f"Não foi possível salvar o arquivo: {error}"
            )
            return
        QMessageBox.information(
            self,
            "Exportar histórico",
            f"{len(items)} item(ns) exportado(s) para {filename}",
        )

    def _show_notice(self, text: str, state: str) -> None:
        self.notice.setProperty("state", state)
        self.notice.setText(text)
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)
        self.notice.setVisible(True)
