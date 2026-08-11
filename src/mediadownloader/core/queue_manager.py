"""Bounded concurrent queue with safe Qt signal delivery and cancellation."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from mediadownloader.models import DownloadItem, DownloadOptions, DownloadStatus
from mediadownloader.services import HistoryService
from mediadownloader.utils.errors import FriendlyError

from .downloader import DownloadEngine
from .workers import DownloadWorker


class QueueManager(QObject):
    item_added = Signal(object)
    item_updated = Signal(object)
    item_finished = Signal(object)
    active_count_changed = Signal(int)

    def __init__(
        self,
        engine: DownloadEngine,
        history: HistoryService,
        concurrency: int = 2,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.history = history
        self.pool = QThreadPool(self)
        self._concurrency = max(1, min(5, concurrency))
        self.pool.setMaxThreadCount(self._concurrency)
        self.pending: deque[tuple[DownloadItem, DownloadOptions]] = deque()
        self.active: dict[str, DownloadWorker] = {}
        self.items: dict[str, DownloadItem] = {}
        self.paused = False

    @property
    def active_count(self) -> int:
        return len(self.active)

    @property
    def has_active(self) -> bool:
        return bool(self.active or self.pending)

    def set_concurrency(self, value: int) -> None:
        self._concurrency = max(1, min(5, int(value)))
        self.pool.setMaxThreadCount(self._concurrency)
        self._start_available()

    def add(self, item: DownloadItem, options: DownloadOptions) -> None:
        item.options = options.to_dict()
        item.status = DownloadStatus.QUEUED
        self.items[item.id] = item
        self.pending.append((item, options))
        self.history.upsert(item)
        self.item_added.emit(item)
        self._start_available()

    def pause(self) -> None:
        """Pause queue scheduling; current downloads continue safely."""
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._start_available()

    def cancel(self, item_id: str) -> None:
        if worker := self.active.get(item_id):
            worker.cancel()
            return
        for item, options in list(self.pending):
            if item.id == item_id:
                self.pending.remove((item, options))
                item.status = DownloadStatus.CANCELLED
                self.history.upsert(item)
                self.item_updated.emit(item)
                self.item_finished.emit(item)
                break

    def cancel_all(self) -> None:
        for item_id in list(self.active):
            self.cancel(item_id)
        for item, _ in list(self.pending):
            self.cancel(item.id)

    def retry(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if not item or item.status not in {DownloadStatus.ERROR, DownloadStatus.CANCELLED}:
            return
        item.status = DownloadStatus.QUEUED
        item.progress = 0
        item.error = ""
        item.technical_error = ""
        options = DownloadOptions.from_dict(item.options)
        self.pending.append((item, options))
        self.history.upsert(item)
        self.item_updated.emit(item)
        self._start_available()

    def remove(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if not item or not item.status.terminal:
            return
        self.items.pop(item_id, None)

    def clear_completed(self) -> None:
        for item_id, item in list(self.items.items()):
            if item.status == DownloadStatus.COMPLETED:
                self.items.pop(item_id, None)

    def _start_available(self) -> None:
        while not self.paused and self.pending and len(self.active) < self._concurrency:
            item, options = self.pending.popleft()
            worker = DownloadWorker(self.engine, item, options)
            worker.signals.progress.connect(self._on_progress)
            worker.signals.completed.connect(self._on_completed)
            worker.signals.failed.connect(self._on_failed)
            worker.signals.cancelled.connect(self._on_cancelled)
            self.active[item.id] = worker
            item.status = DownloadStatus.PREPARING
            self.item_updated.emit(item)
            self.active_count_changed.emit(len(self.active))
            self.pool.start(worker)

    @Slot(str, object)
    def _on_progress(self, item_id: str, update: dict) -> None:
        item = self.items.get(item_id)
        if item is None or item.status.terminal:
            return
        if "status" in update:
            item.status = DownloadStatus(update["status"])
        for field in ("progress", "speed", "eta", "downloaded_bytes", "total_bytes"):
            if field in update:
                setattr(item, field, update[field])
        self.item_updated.emit(item)

    @Slot(str, str)
    def _on_completed(self, item_id: str, final_file: str) -> None:
        item = self.items.get(item_id)
        if item is None:
            return
        item.status = DownloadStatus.COMPLETED
        item.progress = 100.0
        item.speed = None
        item.eta = 0
        item.final_file = final_file
        item.completed_at = datetime.now(UTC).isoformat()
        self._finalize(item)

    @Slot(str, object)
    def _on_failed(self, item_id: str, error: FriendlyError) -> None:
        item = self.items.get(item_id)
        if item is None:
            return
        item.status = DownloadStatus.ERROR
        item.error = error.message
        item.technical_error = error.details
        self._finalize(item)

    @Slot(str)
    def _on_cancelled(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if item is None:
            return
        item.status = DownloadStatus.CANCELLED
        item.speed = None
        item.eta = None
        self._finalize(item)

    def _finalize(self, item: DownloadItem) -> None:
        self.active.pop(item.id, None)
        self.history.upsert(item)
        self.item_updated.emit(item)
        self.item_finished.emit(item)
        self.active_count_changed.emit(len(self.active))
        self._start_available()

