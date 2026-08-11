"""Small Qt workers that bridge blocking core operations to signals."""

from __future__ import annotations

import threading
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from mediadownloader.models import DownloadItem, DownloadOptions, MediaInfo
from mediadownloader.utils.errors import FriendlyError, classify_error

from .downloader import DownloadCancelled, DownloadEngine


class AnalysisEngine(Protocol):
    def analyze(
        self,
        url: str,
        proxy: str = "",
        cookies_file: str = "",
        cookies_browser: str = "",
    ) -> MediaInfo:
        ...


class AnalyzeSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class AnalyzeWorker(QRunnable):
    def __init__(
        self,
        engine: AnalysisEngine,
        url: str,
        proxy: str = "",
        cookies_file: str = "",
        cookies_browser: str = "",
    ) -> None:
        super().__init__()
        self.engine = engine
        self.url = url
        self.proxy = proxy
        self.cookies_file = cookies_file
        self.cookies_browser = cookies_browser
        self.signals = AnalyzeSignals()

    @Slot()
    def run(self) -> None:
        try:
            info: MediaInfo = self.engine.analyze(
                self.url, self.proxy, self.cookies_file, self.cookies_browser
            )
            self.signals.completed.emit(info)
        except Exception as error:
            self.signals.failed.emit(error if isinstance(error, FriendlyError) else classify_error(error))


class DownloadSignals(QObject):
    progress = Signal(str, object)
    completed = Signal(str, str)
    failed = Signal(str, object)
    cancelled = Signal(str)


class DownloadWorker(QRunnable):
    def __init__(self, engine: DownloadEngine, item: DownloadItem, options: DownloadOptions) -> None:
        super().__init__()
        self.engine = engine
        self.item = item
        self.options = options
        self.cancel_event = threading.Event()
        self.signals = DownloadSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            final_file = self.engine.download(
                self.item,
                self.options,
                lambda update: self.signals.progress.emit(self.item.id, update),
                self.cancel_event,
            )
            self.signals.completed.emit(self.item.id, final_file)
        except DownloadCancelled:
            self.signals.cancelled.emit(self.item.id)
        except Exception as error:
            self.signals.failed.emit(
                self.item.id,
                error if isinstance(error, FriendlyError) else classify_error(error),
            )
