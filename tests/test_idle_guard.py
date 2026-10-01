from __future__ import annotations

from mediadownloader.core import idle_guard


class Recorder:
    """Stands in for the platform inhibitor and counts OS round-trips."""

    def __init__(self) -> None:
        self.requests = 0
        self.releases = 0

    def request(self) -> None:
        self.requests += 1

    def release(self) -> None:
        self.releases += 1


def _patch(monkeypatch: object, recorder: Recorder) -> None:
    monkeypatch.setattr(idle_guard, "_windows_request", recorder.request)  # type: ignore[attr-defined]
    monkeypatch.setattr(idle_guard, "_windows_release", recorder.release)  # type: ignore[attr-defined]


def test_a_single_cycle_calls_the_os_once_per_side(monkeypatch):
    recorder = Recorder()
    _patch(monkeypatch, recorder)
    idle_guard.reset()

    idle_guard.acquire()
    idle_guard.acquire()
    assert idle_guard.holder_count() == 2
    assert recorder.requests == 1

    idle_guard.release()
    assert recorder.releases == 0

    idle_guard.release()
    assert idle_guard.holder_count() == 0
    assert recorder.releases == 1


def test_a_second_download_cycle_rearms_the_inhibitor(monkeypatch):
    recorder = Recorder()
    _patch(monkeypatch, recorder)
    idle_guard.reset()

    idle_guard.acquire()
    idle_guard.release()
    idle_guard.acquire()
    idle_guard.release()

    assert (recorder.requests, recorder.releases) == (2, 2)
    assert idle_guard.holder_count() == 0


def test_release_without_holders_is_harmless(monkeypatch):
    recorder = Recorder()
    _patch(monkeypatch, recorder)
    idle_guard.reset()

    idle_guard.release()

    assert recorder.releases == 0
    assert idle_guard.holder_count() == 0


def test_a_failing_platform_call_never_breaks_the_queue(monkeypatch):
    def boom() -> None:
        raise OSError("sistema ocupado")

    monkeypatch.setattr(idle_guard, "_windows_request", boom)  # type: ignore[attr-defined]
    idle_guard.reset()

    idle_guard.acquire()

    assert idle_guard.holder_count() == 1
    idle_guard.release()
    assert idle_guard.holder_count() == 0


def test_reset_clears_holders_without_touching_the_os(monkeypatch):
    recorder = Recorder()
    _patch(monkeypatch, recorder)
    idle_guard.reset()

    idle_guard.acquire()
    idle_guard.reset()

    assert idle_guard.holder_count() == 0
    assert recorder.releases == 0
