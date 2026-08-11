"""Human-friendly values used throughout the UI."""

from __future__ import annotations


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    amount = float(value)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "—"


def format_eta(seconds: int | float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: int | float | None) -> str:
    return format_eta(seconds)

