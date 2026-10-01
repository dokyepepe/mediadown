"""Short audible feedback for finished downloads.

Isolated in its own module so the queue and the main window never need to know
which platform API is available, and so tests can stub a single function.
"""

from __future__ import annotations

import logging
import sys

LOGGER = logging.getLogger(__name__)

#: Windows sound aliases that exist on every supported edition, in preference
#: order. ``None`` means "the default system sound".
_ALIASES = ("Asterisk", "Exclamation", "Question")


def play_completion_sound() -> None:
    """Play the completion chime, doing nothing when the platform has no API.

    Failures are swallowed on purpose: a missing sound must never interrupt the
    user or leave the download queue half-finished.
    """
    try:
        if sys.platform == "win32":
            import winsound  # noqa: PLC0415 - Windows-only import

            for alias in _ALIASES:
                winsound.PlaySound(
                    alias,
                    winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                return
            return
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is not None:
            QApplication.beep()
    except Exception:  # noqa: BLE001 - feedback is optional
        LOGGER.debug("Não foi possível tocar o som de conclusão.", exc_info=True)


def notify(enabled: bool) -> None:
    """Play the chime only when the user asked for it."""
    if enabled:
        play_completion_sound()
