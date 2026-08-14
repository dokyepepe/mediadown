"""Desktop workflow for discovering and downloading PDF/image files from sites."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QThreadPool, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mediadownloader.core.site_files import SiteFile, SiteFileExtractor, SiteScanResult
from mediadownloader.core.site_workers import SiteFileDownloadWorker, SiteScanWorker
from mediadownloader.services import SettingsService
from mediadownloader.utils.validators import validate_url

from ..widgets import PageHeader, PrimaryButton, SecondaryButton


class SiteFilesPage(QWidget):
    """A separate flow so media analysis/download behavior remains unchanged."""

    def __init__(self, settings: SettingsService) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.settings = settings
        self.extractor = SiteFileExtractor()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self._scan_worker: SiteScanWorker | None = None
        self._download_workers: dict[str, SiteFileDownloadWorker] = {}
        self._items_by_url: dict[str, QListWidgetItem] = {}
        self._download_total = 0
        self._download_finished_count = 0
        self._download_failures: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("Page")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 28, 34, 34)
        layout.setSpacing(18)

        layout.addWidget(PageHeader(
            "Arquivos do site",
            "Encontre PDFs e imagens publicados em uma página e salve apenas o que escolher.",
            "file",
        ))

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(12)
        eyebrow = QLabel("EXTRAÇÃO DE DOCUMENTOS")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Transforme uma página em uma lista limpa de arquivos.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel(
            "O analisador reconhece links relativos, PDFs incorporados, imagens responsivas "
            "e endereços diretos, sem passar pelo mecanismo de vídeo e áudio."
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)

        url_row = QHBoxLayout()
        url_row.setSpacing(9)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://site.com/página-com-documentos")
        self.url_input.setAccessibleName("URL do site")
        self.url_input.setMinimumHeight(44)
        self.url_input.returnPressed.connect(self.scan)
        self.paste_button = SecondaryButton("Colar", icon_name="paste")
        self.paste_button.clicked.connect(self._paste_url)
        self.scan_button = PrimaryButton("ANALISAR SITE", icon_name="analyze")
        self.scan_button.clicked.connect(self.scan)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.paste_button)
        url_row.addWidget(self.scan_button)
        hero_layout.addLayout(url_row)

        filters = QHBoxLayout()
        filters.setSpacing(14)
        self.pdf_checkbox = QCheckBox("PDFs")
        self.pdf_checkbox.setChecked(True)
        self.image_checkbox = QCheckBox("Imagens")
        self.image_checkbox.setChecked(True)
        filters.addWidget(self.pdf_checkbox)
        filters.addWidget(self.image_checkbox)
        filters.addStretch()
        privacy = QLabel("Somente URLs públicas HTTP/HTTPS • limite de 512 MB por arquivo")
        privacy.setObjectName("Muted")
        privacy.setWordWrap(True)
        filters.addWidget(privacy)
        hero_layout.addLayout(filters)

        self.notice = QLabel()
        self.notice.setObjectName("Notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        hero_layout.addWidget(self.notice)
        layout.addWidget(hero)

        self.results_card = QFrame()
        self.results_card.setObjectName("SectionCard")
        results_layout = QVBoxLayout(self.results_card)
        results_layout.setContentsMargins(22, 20, 22, 20)
        results_layout.setSpacing(12)
        result_header = QHBoxLayout()
        result_text = QVBoxLayout()
        result_text.setSpacing(2)
        result_title = QLabel("Arquivos encontrados")
        result_title.setObjectName("SectionTitle")
        self.result_summary = QLabel("Analise uma página para começar.")
        self.result_summary.setObjectName("Muted")
        self.result_summary.setWordWrap(True)
        result_text.addWidget(result_title)
        result_text.addWidget(self.result_summary)
        self.select_all_button = SecondaryButton("Selecionar todos")
        self.select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        self.select_none_button = SecondaryButton("Limpar seleção")
        self.select_none_button.clicked.connect(lambda: self._set_all_checked(False))
        result_header.addLayout(result_text, 1)
        result_header.addWidget(self.select_all_button)
        result_header.addWidget(self.select_none_button)
        results_layout.addLayout(result_header)

        self.file_list = QListWidget()
        self.file_list.setObjectName("SiteFileList")
        self.file_list.setMinimumHeight(250)
        self.file_list.itemChanged.connect(self._selection_changed)
        results_layout.addWidget(self.file_list)

        destination_label = QLabel("Pasta de destino")
        destination_label.setObjectName("FieldLabel")
        results_layout.addWidget(destination_label)
        destination_row = QHBoxLayout()
        self.destination_input = QLineEdit(
            str(self.settings.get("general.download_dir", str(Path.home() / "Downloads")))
        )
        self.destination_input.setAccessibleName("Pasta de destino dos arquivos do site")
        self.browse_button = SecondaryButton("Escolher pasta", icon_name="folder")
        self.browse_button.clicked.connect(self._choose_destination)
        destination_row.addWidget(self.destination_input, 1)
        destination_row.addWidget(self.browse_button)
        results_layout.addLayout(destination_row)

        actions = QHBoxLayout()
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 1)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(True)
        self.overall_progress.hide()
        self.open_folder_button = SecondaryButton("Abrir pasta", icon_name="folder")
        self.open_folder_button.clicked.connect(self._open_destination)
        self.open_folder_button.hide()
        self.cancel_button = SecondaryButton("Cancelar", icon_name="cancel")
        self.cancel_button.clicked.connect(self.cancel_downloads)
        self.cancel_button.hide()
        self.download_button = PrimaryButton("BAIXAR SELECIONADOS", icon_name="downloads")
        self.download_button.clicked.connect(self.download_selected)
        actions.addWidget(self.overall_progress, 1)
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.download_button)
        results_layout.addLayout(actions)
        self.results_card.hide()
        layout.addWidget(self.results_card)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def set_detected_url(self, url: str) -> None:
        if not self.url_input.hasFocus():
            self.url_input.setText(url)

    @property
    def has_active_downloads(self) -> bool:
        return bool(self._download_workers)

    def cancel_downloads(self) -> None:
        if not self._download_workers:
            return
        for worker in self._download_workers.values():
            worker.cancel()
        self._show_notice("Cancelando os downloads de arquivos…", "warning")

    def scan(self) -> None:
        valid, error = validate_url(self.url_input.text())
        if not valid:
            self._show_notice(error, "danger")
            return
        if not self.pdf_checkbox.isChecked() and not self.image_checkbox.isChecked():
            self._show_notice("Selecione PDFs, imagens ou ambos.", "warning")
            return
        self._set_scan_busy(True)
        self.file_list.clear()
        self._items_by_url.clear()
        self.results_card.hide()
        self._show_notice("Analisando a página e organizando os arquivos encontrados…", "info")
        worker = SiteScanWorker(
            self.extractor,
            self.url_input.text().strip(),
            include_pdfs=self.pdf_checkbox.isChecked(),
            include_images=self.image_checkbox.isChecked(),
        )
        worker.signals.completed.connect(self._scan_completed)
        worker.signals.failed.connect(self._scan_failed)
        self._scan_worker = worker
        self.pool.start(worker)

    def _paste_url(self) -> None:
        value = QApplication.clipboard().text().strip()
        valid, error = validate_url(value)
        if not valid:
            self._show_notice(
                error or "A área de transferência não contém uma URL válida.",
                "warning",
            )
            return
        self.url_input.setText(value)
        self.url_input.setFocus()

    def _scan_completed(self, result: SiteScanResult) -> None:
        self._scan_worker = None
        self._set_scan_busy(False)
        self.file_list.blockSignals(True)
        for asset in result.files:
            host = (urlparse(asset.url).hostname or "").removeprefix("www.")
            item = QListWidgetItem(f"{asset.kind.label.upper()}  •  {asset.name}\n{host}")
            item.setData(Qt.ItemDataRole.UserRole, asset)
            item.setData(Qt.ItemDataRole.UserRole + 1, f"{asset.kind.label.upper()}  •  {asset.name}\n{host}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(asset.url)
            self.file_list.addItem(item)
            self._items_by_url[asset.url] = item
        self.file_list.blockSignals(False)
        count = len(result.files)
        pdfs = sum(asset.kind.value == "pdf" for asset in result.files)
        images = count - pdfs
        self.result_summary.setText(
            f"{result.page_title}  •  {pdfs} PDF(s)  •  {images} imagem(ns)"
        )
        self.results_card.show()
        if count:
            self._show_notice(
                f"{count} arquivo(s) encontrado(s). Revise a seleção antes de baixar.",
                "success",
            )
        else:
            self._show_notice(
                "Nenhum PDF ou imagem pública foi identificado no HTML desta página. "
                "Conteúdo criado apenas por JavaScript pode não aparecer.",
                "warning",
            )
        self._selection_changed()

    def _scan_failed(self, error: Exception) -> None:
        self._scan_worker = None
        self._set_scan_busy(False)
        self._show_notice(str(error) or "Não foi possível analisar este site.", "danger")

    def download_selected(self) -> None:
        selected = [
            self.file_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.file_list.count())
            if self.file_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            self._show_notice("Selecione pelo menos um arquivo para baixar.", "warning")
            return
        directory = Path(self.destination_input.text()).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.is_dir():
                raise OSError("o destino não é uma pasta")
        except OSError as error:
            self._show_notice(f"A pasta de destino não pôde ser usada: {error}", "danger")
            return

        self._download_total = len(selected)
        self._download_finished_count = 0
        self._download_failures.clear()
        self.overall_progress.setRange(0, self._download_total)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat(f"0 de {self._download_total} concluídos")
        self.overall_progress.show()
        self.open_folder_button.hide()
        self._set_download_busy(True)
        self._show_notice("Baixando os arquivos selecionados…", "info")
        for asset in selected:
            worker = SiteFileDownloadWorker(self.extractor, asset, directory)
            worker.signals.progress.connect(self._download_progress)
            worker.signals.completed.connect(self._download_completed)
            worker.signals.failed.connect(self._download_failed)
            self._download_workers[asset.url] = worker
            self.pool.start(worker)

    def _download_progress(self, url: str, current: int, total: int | None) -> None:
        item = self._items_by_url.get(url)
        if item is None:
            return
        base = item.data(Qt.ItemDataRole.UserRole + 1)
        if total:
            percent = min(100, round(current * 100 / total))
            item.setText(f"{base}\nBaixando… {percent}%")
        else:
            item.setText(f"{base}\nBaixando… {current / (1024 * 1024):.1f} MB")

    def _download_completed(self, url: str, path: str) -> None:
        item = self._items_by_url.get(url)
        if item is not None:
            base = item.data(Qt.ItemDataRole.UserRole + 1)
            item.setText(f"{base}\nSalvo como {Path(path).name}")
            item.setCheckState(Qt.CheckState.Unchecked)
        self._download_workers.pop(url, None)
        self._finish_one_download()

    def _download_failed(self, url: str, error: Exception) -> None:
        item = self._items_by_url.get(url)
        message = str(error) or "Falha no download"
        if item is not None:
            base = item.data(Qt.ItemDataRole.UserRole + 1)
            item.setText(f"{base}\nFalha: {message}")
        self._download_failures.append(message)
        self._download_workers.pop(url, None)
        self._finish_one_download()

    def _finish_one_download(self) -> None:
        self._download_finished_count += 1
        self.overall_progress.setValue(self._download_finished_count)
        self.overall_progress.setFormat(
            f"{self._download_finished_count} de {self._download_total} concluídos"
        )
        if self._download_finished_count < self._download_total:
            return
        self._set_download_busy(False)
        self.open_folder_button.show()
        successful = self._download_total - len(self._download_failures)
        if self._download_failures:
            self._show_notice(
                f"{successful} arquivo(s) salvo(s) e {len(self._download_failures)} com falha. "
                "Os itens com erro permanecem marcados para tentar novamente.",
                "warning",
            )
        else:
            self._show_notice(
                f"{successful} arquivo(s) salvo(s) com sucesso em {self.destination_input.text()}.",
                "success",
            )
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        checked = sum(
            self.file_list.item(index).checkState() == Qt.CheckState.Checked
            for index in range(self.file_list.count())
        )
        self.download_button.setText(
            f"BAIXAR {checked} SELECIONADO{'S' if checked != 1 else ''}"
        )
        self.download_button.setEnabled(checked > 0 and not self._download_workers)

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.file_list.blockSignals(True)
        for index in range(self.file_list.count()):
            self.file_list.item(index).setCheckState(state)
        self.file_list.blockSignals(False)
        self._selection_changed()

    def _set_scan_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.scan_button.setText("ANALISANDO…" if busy else "ANALISAR SITE")
        self.url_input.setEnabled(not busy)
        self.paste_button.setEnabled(not busy)
        self.pdf_checkbox.setEnabled(not busy)
        self.image_checkbox.setEnabled(not busy)

    def _set_download_busy(self, busy: bool) -> None:
        self.download_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.destination_input.setEnabled(not busy)
        self.select_all_button.setEnabled(not busy)
        self.select_none_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        self.download_button.setVisible(not busy)

    def _choose_destination(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Escolher pasta de destino",
            self.destination_input.text(),
        )
        if selected:
            self.destination_input.setText(selected)

    def _open_destination(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.destination_input.text()).resolve())))

    def _show_notice(self, text: str, state: str) -> None:
        self.notice.setProperty("state", state)
        self.notice.setText(text)
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)
        self.notice.show()
