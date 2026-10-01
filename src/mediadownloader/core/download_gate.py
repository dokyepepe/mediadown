"""Pure scheduling and storage rules that decide when the queue may start work.

The gate is deliberately free of Qt and of the filesystem: it takes the current
time and the free space already probed by the caller, and returns a decision.
That keeps the rules (window wrap-around, minimum free space) directly testable
and lets the UI re-evaluate them on a timer.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

#: Downloads are refused below this much free space so a transfer never fills
#: the volume to the point where the OS starts rejecting unrelated writes.
MINIMUM_FREE_BYTES = 32 * 1024 * 1024

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True, slots=True)
class GateConfig:
    """User-selected queue rules, mirroring the mobile edition's download gate."""

    window_enabled: bool = False
    window_start_minute: int = 0
    window_end_minute: int = 360
    minimum_free_bytes: int = MINIMUM_FREE_BYTES

    @classmethod
    def from_settings(cls, settings) -> "GateConfig":  # noqa: ANN001 - duck-typed service
        return cls(
            window_enabled=bool(settings.get("downloads.window_enabled", False)),
            window_start_minute=clamp_minute(settings.get("downloads.window_start_minute", 0)),
            window_end_minute=clamp_minute(settings.get("downloads.window_end_minute", 360)),
            minimum_free_bytes=max(0, int(settings.get("downloads.minimum_free_mb", 32)) * 1024 * 1024),
        )


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Outcome of a gate evaluation."""

    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


def clamp_minute(value: object) -> int:
    """Coerce any stored value into a valid minute-of-day offset."""
    try:
        minute = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(MINUTES_PER_DAY - 1, minute))


def format_minute(minute: int) -> str:
    """Render a minute-of-day offset as ``HH:MM``."""
    hour, rest = divmod(clamp_minute(minute), 60)
    return f"{hour:02d}:{rest:02d}"


def minute_of_day(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def window_allows(start_minute: int, end_minute: int, moment: datetime) -> bool:
    """Whether ``moment`` falls inside the daily download window.

    The window wraps over midnight, so ``22:00``–``06:00`` is handled without
    special casing. Equal start and end means "always allowed", matching the
    mobile edition, which lets a user disable the restriction by setting both
    ends to the same time.
    """
    start = clamp_minute(start_minute)
    end = clamp_minute(end_minute)
    if start == end:
        return True
    current = minute_of_day(moment)
    if start < end:
        return start <= current < end
    return current >= start or current < end


def free_space_bytes(path: str | Path) -> int | None:
    """Free bytes on the volume holding ``path``, or ``None`` when unknown.

    A failed probe returns ``None`` so callers can fail open: an unreadable
    volume should not silently freeze the queue forever.
    """
    try:
        target = Path(path).expanduser()
        probe = target if target.exists() else target.parent
        return int(shutil.disk_usage(probe).free)
    except OSError:
        return None


def evaluate(
    config: GateConfig,
    moment: datetime | None = None,
    free_bytes: int | None = None,
    *,
    download_dirs: Iterable[str | Path] = (),
) -> GateDecision:
    """Decide whether new downloads may start right now.

    Checks run cheapest-first: the scheduled window needs no I/O, while the
    free-space rule only probes a disk when the user set a threshold.
    """
    now = moment or datetime.now()  # noqa: DTZ005 - local wall clock is the rule
    if config.window_enabled and not window_allows(
        config.window_start_minute, config.window_end_minute, now
    ):
        return GateDecision(
            False,
            f"Janela agendada ({format_minute(config.window_start_minute)}–"
            f"{format_minute(config.window_end_minute)})",
        )
    if config.minimum_free_bytes > 0:
        free = free_bytes
        if free is None:
            for directory in download_dirs:
                free = free_space_bytes(directory)
                if free is not None:
                    break
        if free is not None and free < config.minimum_free_bytes:
            return GateDecision(False, "Espaço livre insuficiente no disco de destino")
    return GateDecision(True)
