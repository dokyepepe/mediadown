"""Keep the machine awake while downloads run.

Backed by the platform's own inhibitor so the request is honoured even when
the app is not the foreground window: ``SetThreadExecutionState`` on Windows and
``xdg-screensaver suspend`` elsewhere. The guard is reference counted, so nested
or repeated calls only release the inhibitor once the last holder is done.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading

LOGGER = logging.getLogger(__name__)

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001

_lock = threading.RLock()
_holders = 0


def _windows_request() -> None:
    import ctypes  # noqa: PLC0415 - Windows-only import

    ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
        _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
    )


def _posix_request() -> None:
    command = shutil.which("xdg-screensaver")
    if not command:
        LOGGER.debug("xdg-screensaver indisponível; o sistema pode suspender o computador.")
        return
    try:
        subprocess.Popen(
            [command, "suspend"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        LOGGER.debug("Não foi possível inhibiting a suspensão de tela: %s", error)


def _windows_release() -> None:
    import ctypes  # noqa: PLC0415 - Windows-only import

    ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)  # type: ignore[attr-defined]


def _posix_release() -> None:
    command = shutil.which("xdg-screensaver")
    if not command:
        return
    try:
        subprocess.Popen(
            [command, "resume"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        LOGGER.debug("Não foi possível reativar a suspensão de tela.")


def acquire() -> None:
    """Ask the system to stay awake. Safe to call repeatedly.

    The OS call only happens on the first holder, so a nested ``acquire`` costs
    nothing; the matching ``release`` from the last holder gives the sleep
    behaviour back. Each download cycle therefore re-arms the inhibitor.
    """
    global _holders
    with _lock:
        if _holders == 0:
            try:
                if sys.platform == "win32":
                    _windows_request()
                else:
                    _posix_request()
            except Exception:  # noqa: BLE001 - never let the guard break a download
                LOGGER.debug("Falha ao solicitar suspensão de tela.", exc_info=True)
        _holders += 1


def release() -> None:
    """Give the system back its normal sleep behaviour once every holder is done."""
    global _holders
    with _lock:
        if _holders == 0:
            return
        _holders -= 1
        if _holders == 0:
            try:
                if sys.platform == "win32":
                    _windows_release()
                else:
                    _posix_release()
            except Exception:  # noqa: BLE001 - the OS recovers on its own
                LOGGER.debug("Falha ao reativar a suspensão de tela.", exc_info=True)


def reset() -> None:
    """Drop every holder without touching the OS.

    Only used by tests to restore the module-level state between cases.
    """
    global _holders
    with _lock:
        _holders = 0


def holder_count() -> int:
    return _holders
