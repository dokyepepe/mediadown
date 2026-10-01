"""Bounded concurrent queue with safe Qt signal delivery and cancellation."""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal, Slot

from mediadownloader.models import DownloadItem, DownloadOptions, DownloadStatus
from mediadownloader.services import HistoryService
from mediadownloader.utils.errors import FriendlyError

from . import idle_guard
from .download_gate import GateConfig, evaluate
from .downloader import DownloadEngine
from .workers import DownloadWorker

LOGGER = logging.getLogger(__name__)

#: How often the gate is re-checked. Minute-long so a download window that just
#: opened is noticed quickly, without spinning the CPU all night.
GATE_RECHECK_MS = 30_000


def _file_size(path: str) -> int:
    """Size of a finished file, or ``0`` when it is already gone."""
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


class QueueManager(QObject):
    item_added = Signal(object)
    item_updated = Signal(object)
    item_finished = Signal(object)
    active_count_changed = Signal(int)
    #: ``(blocked, reason)`` — emitted whenever the gate starts or stops holding
    #: the queue back, so the downloads page can explain the wait.
    gate_changed = Signal(bool, str)

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
        self.gate_config = GateConfig()
        self.gate_blocked = False
        self.gate_reason = ""
        self.keep_awake = False
        self._pause_requested: set[str] = set()
        self._awake_held = False
        self._gate_timer = QTimer(self)
        self._gate_timer.setInterval(GATE_RECHECK_MS)
        self._gate_timer.timeout.connect(self._recheck_gate)
        self._gate_timer.start()

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

    def set_gate(self, config: GateConfig) -> None:
        """Replace the queue rules and re-evaluate immediately."""
        self.gate_config = config
        self._recheck_gate()

    def set_keep_awake(self, enabled: bool) -> None:
        """Hold or release the system sleep inhibitor based on queue activity."""
        self.keep_awake = bool(enabled)
        self._sync_idle_guard()

    def add(self, item: DownloadItem, options: DownloadOptions) -> None:
        item.options = options.to_dict()
        item.status = DownloadStatus.QUEUED
        self.items[item.id] = item
        self.pending.append((item, options))
        self._safe_upsert(item)
        self.item_added.emit(item)
        self._start_available()

    def pause(self) -> None:
        """Pause queue scheduling; current downloads continue safely."""
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._start_available()

    def pause_item(self, item_id: str) -> None:
        """Pause a single item, leaving the rest of the queue running.

        An in-flight download is stopped at the next progress checkpoint and
        kept as ``PAUSED``; because yt-dlp runs with ``continuedl`` it picks up
        from the partial file when the item is resumed.
        """
        item = self.items.get(item_id)
        if item is None or item.status.terminal or item.status == DownloadStatus.PAUSED:
            return
        self._pause_requested.add(item_id)
        if worker := self.active.get(item_id):
            worker.cancel()
            return
        for pending_item, _ in list(self.pending):
            if pending_item.id == item_id:
                self.pending.remove((pending_item, _))
                break
        item.status = DownloadStatus.PAUSED
        item.speed = None
        item.eta = None
        self._safe_upsert(item)
        self.item_updated.emit(item)

    def resume_item(self, item_id: str) -> None:
        """Return a paused item to the queue, keeping its downloaded progress."""
        item = self.items.get(item_id)
        if item is None or item.status != DownloadStatus.PAUSED:
            return
        self._pause_requested.discard(item_id)
        item.status = DownloadStatus.QUEUED
        item.error = ""
        item.technical_error = ""
        options = DownloadOptions.from_dict(item.options)
        self.pending.append((item, options))
        self._safe_upsert(item)
        self.item_updated.emit(item)
        self._start_available()

    def move_item(self, item_id: str, up: bool) -> bool:
        """Reorder a waiting item within the queue; returns whether it moved.

        Only items that have not started yet can be reordered — changing the
        order of running downloads would report progress for the wrong file.
        """
        index = next(
            (position for position, (item, _options) in enumerate(self.pending) if item.id == item_id),
            None,
        )
        if index is None:
            return False
        target = index - 1 if up else index + 1
        if target < 0 or target >= len(self.pending):
            return False
        self.pending[index], self.pending[target] = self.pending[target], self.pending[index]
        return True

    def can_move(self, item_id: str, up: bool) -> bool:
        """Whether :meth:`move_item` would currently change anything."""
        index = next(
            (position for position, (item, _options) in enumerate(self.pending) if item.id == item_id),
            None,
        )
        if index is None:
            return False
        target = index - 1 if up else index + 1
        return 0 <= target < len(self.pending)

    def cancel(self, item_id: str) -> None:
        self._pause_requested.discard(item_id)
        if worker := self.active.get(item_id):
            worker.cancel()
            return
        for item, options in list(self.pending):
            if item.id == item_id:
                self.pending.remove((item, options))
                item.status = DownloadStatus.CANCELLED
                self._safe_upsert(item)
                self.item_updated.emit(item)
                self.item_finished.emit(item)
                break
        else:
            item = self.items.get(item_id)
            if item is not None and item.status == DownloadStatus.PAUSED:
                item.status = DownloadStatus.CANCELLED
                self._safe_upsert(item)
                self.item_updated.emit(item)
                self.item_finished.emit(item)

    def cancel_all(self) -> None:
        for item_id in list(self.active):
            self.cancel(item_id)
        for item, _ in list(self.pending):
            self.cancel(item.id)
        for item in list(self.items.values()):
            if item.status == DownloadStatus.PAUSED:
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
        self._safe_upsert(item)
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

    def download_dirs(self) -> list[str]:
        """Distinct output directories currently referenced by the queue."""
        directories: list[str] = []
        for item, options in self.pending:
            if options.output_dir and options.output_dir not in directories:
                directories.append(options.output_dir)
        for item_id in self.active:
            item = self.items.get(item_id)
            if item is None:
                continue
            directory = str(DownloadOptions.from_dict(item.options).output_dir)
            if directory and directory not in directories:
                directories.append(directory)
        return directories

    def _start_available(self) -> None:
        if self.paused or self.gate_blocked:
            self._sync_idle_guard()
            return
        while self.pending and len(self.active) < self._concurrency:
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
        self._sync_idle_guard()

    def _recheck_gate(self) -> None:
        """Re-evaluate the schedule and free-space rules, then drain the queue."""
        decision = evaluate(self.gate_config, download_dirs=self.download_dirs())
        blocked = not decision.allowed
        changed = blocked != self.gate_blocked or decision.reason != self.gate_reason
        self.gate_blocked = blocked
        self.gate_reason = decision.reason
        if changed:
            self.gate_changed.emit(blocked, decision.reason)
        if not blocked:
            self._start_available()
        else:
            self._sync_idle_guard()

    def _sync_idle_guard(self) -> None:
        """Hold the sleep inhibitor only while downloads are genuinely running."""
        should_hold = self.keep_awake and bool(self.active) and not self.gate_blocked
        if should_hold == self._awake_held:
            return
        self._awake_held = should_hold
        if should_hold:
            idle_guard.acquire()
        else:
            idle_guard.release()

    @Slot(str, object)
    def _on_progress(self, item_id: str, update: dict) -> None:
        item = self.items.get(item_id)
        if item is None or item.status.terminal:
            return
        if "status" in update:
            try:
                item.status = DownloadStatus(update["status"])
            except (ValueError, KeyError):
                pass
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
        item.file_size = _file_size(final_file)
        if item.provisional_title and final_file:
            # Batch enqueues are labelled "Link 3" until the real title is known;
            # the saved file name is the first trustworthy title we have.
            item.title = Path(final_file).stem
            item.provisional_title = False
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
        item.speed = None
        item.eta = None
        if item_id in self._pause_requested:
            self._pause_requested.discard(item_id)
            item.status = DownloadStatus.PAUSED
            self.active.pop(item_id, None)
            self._safe_upsert(item)
            self.item_updated.emit(item)
            self.active_count_changed.emit(len(self.active))
            self._start_available()
            return
        item.status = DownloadStatus.CANCELLED
        self._finalize(item)

    def _finalize(self, item: DownloadItem) -> None:
        self.active.pop(item.id, None)
        self._safe_upsert(item)
        self.item_updated.emit(item)
        self.item_finished.emit(item)
        self.active_count_changed.emit(len(self.active))
        self._start_available()

    def _safe_upsert(self, item: DownloadItem) -> None:
        """Persist state without letting SQLite failures kill the UI thread."""
        try:
            self.history.upsert(item)
        except Exception as error:  # noqa: BLE001 - storage must never crash a slot
            LOGGER.warning("Não foi possível salvar o item %s no histórico: %s", item.id, error)

    def shutdown(self) -> None:
        """Stop timers and release the sleep inhibitor before the window closes."""
        self._gate_timer.stop()
        if self._awake_held:
            self._awake_held = False
            idle_guard.release()
