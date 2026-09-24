"""Smoke tests for the audio editor page and its waveform widget."""

from __future__ import annotations

from pathlib import Path

import pytest

from mediadownloader.core.audio_effects import AudioEffectsController
from mediadownloader.ui.pages.audio_editor_page import AudioEditorPage


class StubFFmpeg:
    def __init__(self, available: bool, ffmpeg=Path("ffmpeg-bin"), ffprobe=None) -> None:
        self.available = available
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe


def _make_page(qtbot, ffmpeg_available: bool = False, tmp_path=None):
    from mediadownloader.services.settings_service import SettingsService

    settings = SettingsService(tmp_path / "settings.json") if tmp_path else None
    controller = AudioEffectsController(settings)
    ffmpeg = StubFFmpeg(
        available=ffmpeg_available,
        ffprobe=Path("ffprobe-bin") if ffmpeg_available else None,
    )
    page = AudioEditorPage(controller, ffmpeg)
    qtbot.addWidget(page)
    return page, controller


def test_page_disables_everything_without_ffmpeg(qtbot) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=False)
    assert page.open_button.isEnabled() is False
    assert page.preview_button.isEnabled() is False
    assert page.export_button.isEnabled() is False
    assert all(not spin.isEnabled() for spin in (page.time_start, page.time_end))
    assert page.render_notice.isHidden() is False


def test_page_enables_open_with_ffmpeg_and_no_notice(qtbot) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=True)
    assert page.open_button.isEnabled() is True
    assert page.render_notice.isHidden() is True


def test_decode_done_unlocks_editor_and_fills_spins(qtbot, tmp_path) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=True, tmp_path=tmp_path)
    page._path = tmp_path / "tone.mp3"
    peaks = tuple(((-0.25, 0.4), (0.0, 0.0)) * 20)
    page._on_decode_done(30.0, peaks)
    assert page.waveform.has_media()
    assert page.time_start.maximum() == pytest.approx(29.9)
    assert page.time_end.value() == pytest.approx(30.0)
    assert page.preview_button.isEnabled() is True
    assert page.export_button.isEnabled() is True
    assert "0.50 min" in page.duration_label.text()


def test_decode_done_unknown_duration_defaults_end_to_thirty(qtbot, tmp_path) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=True, tmp_path=tmp_path)
    page._path = tmp_path / "mystery.mp3"
    page._on_decode_done(None, ((0.0, 0.1),))
    assert page.time_end.value() == pytest.approx(30.0)
    assert page.preview_button.isEnabled() is True
    assert "duração desconhecida" in page.duration_label.text()


def test_decode_failure_keeps_actions_disabled(qtbot, tmp_path) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=True, tmp_path=tmp_path)
    page._path = tmp_path / "broken.mp3"
    page._on_decode_failed("nope")
    assert page.preview_button.isEnabled() is False
    assert page.export_button.isEnabled() is False
    assert page.render_notice.property("state") == "error"


def test_spin_inputs_move_waveform_selection(qtbot, tmp_path) -> None:
    page, _ = _make_page(qtbot)
    page.waveform.set_media(10.0, ((0.0, 0.1),))
    page.time_start.setRange(0.0, 9.9)
    page.time_end.setRange(0.0, 10.0)
    page.time_start.setEnabled(True)
    page.time_end.setEnabled(True)
    page._duration = 10.0
    page.time_start.setValue(2.0)
    page.time_end.setValue(8.0)
    assert page.waveform._start == pytest.approx(2.0)
    assert page.waveform._end == pytest.approx(8.0)


def test_effects_summary_tracks_controller(qtbot) -> None:
    page, controller = _make_page(qtbot)
    assert "nenhum extra" in page.effects_label.text().lower()
    controller.set_bass(True)
    assert "bass" in page.effects_label.text()
    assert "loudnorm" not in page.effects_label.text()
    controller.set_normalize(True)
    assert "loudnorm" in page.effects_label.text()


def test_waveform_set_range_clamps_min_gap() -> None:
    from mediadownloader.ui.widgets.waveform_view import WaveformView

    view = WaveformView()
    view.set_media(10.0, ((0.0, 0.1),))
    view.set_range(5.0, 5.0)
    assert view._start == pytest.approx(5.0)
    assert view._end == pytest.approx(5.1)
    view.set_range(-3.0, 99.0)
    assert view._start == 0.0
    assert view._end == pytest.approx(10.0)


def test_waveform_arrow_keys_nudge_active_boundary_and_emit(qtbot) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from mediadownloader.ui.widgets.waveform_view import WaveformView

    view = WaveformView()
    view.set_media(10.0, ((0.0, 0.1),))
    qtbot.addWidget(view)
    view.show()
    view.setFocus()

    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Left)
    assert view._end == pytest.approx(9.9)

    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert view._end == pytest.approx(10.0)

    view._active = "start"
    view._start = 5.0
    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Left)
    assert view._start == pytest.approx(4.9)


def test_waveform_home_and_end_jump_to_extremes(qtbot) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from mediadownloader.ui.widgets.waveform_view import WaveformView

    view = WaveformView()
    view.set_media(10.0, ((0.0, 0.1),))
    view._active = "start"
    view._start = 3.0
    qtbot.addWidget(view)
    view.show()
    view.setFocus()

    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Home)
    assert view._start == 0.0

    view._active = "end"
    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_End)
    assert view._end == pytest.approx(10.0)


def test_waveform_arrow_never_moves_beyond_media(qtbot) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from mediadownloader.ui.widgets.waveform_view import WaveformView

    view = WaveformView()
    view.set_media(10.0, ((0.0, 0.1),))
    view._active = "end"
    view._end = 10.0
    qtbot.addWidget(view)
    view.show()
    view.setFocus()

    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Right)
    assert view._end == pytest.approx(10.0)


def test_waveform_arrow_preserves_minimum_gap(qtbot) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from mediadownloader.ui.widgets.waveform_view import WaveformView

    view = WaveformView()
    view.set_media(10.0, ((0.0, 0.1),))
    view._active = "start"
    view._start = 5.0
    view._end = 5.05
    qtbot.addWidget(view)
    view.show()
    view.setFocus()

    with qtbot.waitSignal(view.range_changed, timeout=1000):
        QTest.keyClick(view, Qt.Key.Key_Right)
    assert view._start == pytest.approx(4.95)
    assert view._end - view._start >= 0.1 - 1e-9