"""Guarded-preview robustness tests for the media preview dialog."""

from __future__ import annotations

from PySide6.QtCore import QUrl

from mediadownloader.core.audio_effects import (
    AudioEffectsController, render_tone_wav,
)
from mediadownloader.models import PreviewSource
from mediadownloader.ui.widgets.video_preview import VideoPreviewDialog


class FailingFFmpeg:
    available = True

    def version(self) -> str:
        return "7.0"

    def render_preview(self, *args, **kwargs):
        raise RuntimeError("falha simulada do renderizador")


class UnavailableFFmpeg:
    available = False

    def version(self) -> str:
        return "7.0"

    def render_preview(self, *args, **kwargs):
        raise AssertionError("render não deveria ser chamado")


def _make_dialog(qtbot, ffmpeg=None, audio_effects=None) -> VideoPreviewDialog:
    dialog = VideoPreviewDialog("teste", ffmpeg=ffmpeg, audio_effects=audio_effects)
    qtbot.addWidget(dialog)
    return dialog


def _tone_url(tmp_path, name: str = "tone.wav") -> str:
    path = tmp_path / name
    render_tone_wav(path, 440.0)
    return QUrl.fromLocalFile(str(path)).toString()


def test_apply_values_pushes_to_controller(qtbot) -> None:
    controller = AudioEffectsController()
    dialog = _make_dialog(qtbot, audio_effects=controller)
    dialog._source_url = "https://example.com/audio.mp3"
    dialog.apply_values(1.5, 1.0, 1.0)
    assert controller.effects.speed == 1.5
    assert controller.effects.volume == 1.0


def test_identity_resets_controller_chain(qtbot) -> None:
    controller = AudioEffectsController()
    dialog = _make_dialog(qtbot, audio_effects=controller)
    dialog._source_url = "https://example.com/audio.mp3"
    dialog.apply_values(1.0, 1.0, 1.0)
    assert controller.effects.is_identity


def test_no_audio_source_skips_render(qtbot, tmp_path) -> None:
    dialog = _make_dialog(qtbot, ffmpeg=FailingFFmpeg())
    dialog.load_source(
        PreviewSource(url=_tone_url(tmp_path, "mute.wav"), has_audio=False, duration=2.0)
    )
    assert dialog._pending_render is False
    assert "não contém áudio" in dialog.effect_status.text().lower()


def test_render_failure_degrades_gracefully(qtbot, tmp_path) -> None:
    dialog = _make_dialog(qtbot, ffmpeg=FailingFFmpeg())
    dialog._source_url = _tone_url(tmp_path)
    dialog.apply_values(1.5, 1.0, 1.0)
    dialog._start_render()
    qtbot.waitUntil(lambda: "baixe o arquivo" in dialog.effect_status.text().lower(), timeout=4000)
    assert dialog.compare_button.isEnabled() is False


def test_ffmpeg_unavailable_disables_live_render(qtbot, tmp_path) -> None:
    dialog = _make_dialog(qtbot, ffmpeg=UnavailableFFmpeg())
    dialog._source_url = _tone_url(tmp_path)
    dialog.apply_values(1.5, 1.0, 1.0)
    assert dialog._pending_render is False
    assert "FFmpeg" in dialog.effect_status.text()
    assert dialog.compare_button.isEnabled() is False


def test_stale_render_discards_file(qtbot, tmp_path) -> None:
    dialog = _make_dialog(qtbot)
    stale = tmp_path / "stale.mkv"
    stale.write_bytes(b"x")
    dialog._render_seq = 5
    dialog._render_ready(4, stale)
    assert not stale.exists()


def test_close_cleans_up_render_files_and_cancels(qtbot, tmp_path) -> None:
    dialog = _make_dialog(qtbot)
    clip = tmp_path / "clip.mkv"
    clip.write_bytes(b"m")
    dialog._local_path = clip
    dialog._pending_render = True
    dialog.close()
    assert not clip.exists()
    assert dialog._pending_render is False
    assert dialog._local_path is None


def test_current_window_falls_back_when_position_unknown(qtbot) -> None:
    dialog = _make_dialog(qtbot)
    dialog.preview_duration = 12.0
    start, window = dialog._current_window()
    assert start == 0.0
    assert window == 12.0


def test_error_occurred_does_not_crash_and_keeps_original(qtbot) -> None:
    dialog = _make_dialog(qtbot)
    dialog._source_url = "https://example.com/audio.mp3"
    dialog._error_occurred("boom")
    assert "Erro" in dialog.effect_status.text()