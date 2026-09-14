"""Small Qt workers that bridge blocking core operations to signals."""

from __future__ import annotations

import threading
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from mediadownloader.models import DownloadItem, DownloadOptions, MediaInfo, PreviewSource
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


class PreviewSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class PreviewWorker(QRunnable):
    """Resolve a directly playable stream URL off the main thread."""

    def __init__(
        self,
        engine: DownloadEngine,
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
        self.signals = PreviewSignals()

    @Slot()
    def run(self) -> None:
        try:
            source = self.engine.preview_source(
                self.url, self.proxy, self.cookies_file, self.cookies_browser,
            )
            self.signals.completed.emit(source)
        except Exception as error:
            self.signals.failed.emit(error if isinstance(error, FriendlyError) else classify_error(error))


class PreviewRenderSignals(QObject):
    completed = Signal(str)
    failed = Signal(str)


class PreviewRenderWorker(QRunnable):
    """Render a short preview clip with the audio filter chain off-thread."""

    def __init__(
        self,
        ffmpeg: "FFmpegManager",
        source_url: str,
        output_path: "Path",
        audio_filter: str,
        duration: float = 12.0,
        start_time: float = 0.0,
        video_url: str | None = None,
        audio_url: str | None = None,
        headers: dict | None = None,
    ) -> None:
        super().__init__()
        self.ffmpeg = ffmpeg
        self.source_url = source_url
        self.output_path = output_path
        self.audio_filter = audio_filter
        self.duration = duration
        self.start_time = start_time
        self.video_url = video_url
        self.audio_url = audio_url
        self.headers = headers
        self.signals = PreviewRenderSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.ffmpeg.render_preview(
                self.source_url, self.output_path, self.audio_filter, self.duration,
                self.start_time,
                video_url=self.video_url,
                audio_url=self.audio_url,
                headers=self.headers,
            )
            self.signals.completed.emit(str(self.output_path))
        except Exception as error:
            self.signals.failed.emit(str(error))


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
