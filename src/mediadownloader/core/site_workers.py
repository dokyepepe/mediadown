"""Qt workers for the isolated site-file extractor."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .site_files import SiteFile, SiteFileExtractor


class SiteScanSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class SiteScanWorker(QRunnable):
    def __init__(
        self,
        extractor: SiteFileExtractor,
        url: str,
        *,
        include_pdfs: bool,
        include_images: bool,
    ) -> None:
        super().__init__()
        self.extractor = extractor
        self.url = url
        self.include_pdfs = include_pdfs
        self.include_images = include_images
        self.signals = SiteScanSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.extractor.discover(
                self.url,
                include_pdfs=self.include_pdfs,
                include_images=self.include_images,
            )
            self.signals.completed.emit(result)
        except Exception as error:
            self.signals.failed.emit(error)


class SiteFileDownloadSignals(QObject):
    progress = Signal(str, int, object)
    completed = Signal(str, str)
    failed = Signal(str, object)


class SiteFileDownloadWorker(QRunnable):
    def __init__(
        self,
        extractor: SiteFileExtractor,
        asset: SiteFile,
        output_dir: str | Path,
    ) -> None:
        super().__init__()
        self.extractor = extractor
        self.asset = asset
        self.output_dir = output_dir
        self.cancel_event = threading.Event()
        self.signals = SiteFileDownloadSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            path = self.extractor.download(
                self.asset,
                self.output_dir,
                progress=lambda current, total: self.signals.progress.emit(
                    self.asset.url,
                    current,
                    total,
                ),
                cancel_event=self.cancel_event,
            )
            self.signals.completed.emit(self.asset.url, str(path))
        except Exception as error:
            self.signals.failed.emit(self.asset.url, error)
