"""Smoke tests for the dedicated audio effects page."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt

from mediadownloader.core.audio_effects import (
    AudioEffects, AudioEffectsController, PITCH_SEMITONES, render_tone_wav,
    semitones_note_name, semitones_to_ratio,
)
from mediadownloader.models import PreviewSource
from mediadownloader.ui.pages.audio_page import AudioPage


class StubFFmpeg:
    def __init__(self, available: bool = False, version: str = "7.0") -> None:
        self.available = available
        self._version = version

    def version(self) -> str:
        return self._version


class RaisesEngine:
    def preview_source(self, url, proxy="", cookies_file="", cookies_browser=""):
        raise RuntimeError("falha resolvendo o stream")


class LocalEngine:
    def __init__(self, wav_url: str) -> None:
        self._wav_url = wav_url

    def preview_source(self, url, proxy="", cookies_file="", cookies_browser=""):
        return PreviewSource(url=self._wav_url, has_audio=True, has_video=False, duration=0.9)


def _make_page(qtbot, ffmpeg_available: bool = False, tmp_path=None, engine=None):
    settings = None
    if tmp_path:
        from mediadownloader.services.settings_service import SettingsService
        settings = SettingsService(tmp_path / "settings.json")
    controller = AudioEffectsController(settings)
    page = AudioPage(controller, StubFFmpeg(ffmpeg_available), engine=engine, settings=settings)
    qtbot.addWidget(page)
    return page, controller


def test_summary_updates_when_pitch_changes(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.pitch_slider.setValue(-2)
    assert "mais grave" in page.summary_label.text().lower()
    page.pitch_slider.setValue(0)
    assert page.summary_label.text() == "Sem efeitos"


def test_speed_slider_syncs_combo_and_controller(qtbot) -> None:
    page, controller = _make_page(qtbot)
    page.speed_slider.setValue(125)
    assert float(page.speed_combo.currentData()) == 1.25
    assert controller.effects.speed == 1.25


def test_volume_combo_syncs_slider(qtbot) -> None:
    page, controller = _make_page(qtbot)
    page.volume_combo.setCurrentIndex(page.volume_combo.count() - 2)
    assert page.volume_slider.value() == 200
    assert controller.effects.volume == 2.0


def test_fine_grained_speed_uses_custom_slot(qtbot) -> None:
    page, controller = _make_page(qtbot)
    page.speed_slider.setValue(130)
    assert controller.effects.speed == 1.3
    assert "personalizado" in page.speed_combo.currentText().lower()
    page.audio_effects.set_effects(AudioEffects(speed=1.3, pitch=1.0, volume=1.0))
    assert float(page.speed_combo.currentData()) == 1.3


def test_custom_slot_empty_selection_keeps_value(qtbot) -> None:
    page, controller = _make_page(qtbot)
    empty_custom = page.volume_combo.count() - 1
    page._volume_combo_changed(empty_custom)
    assert controller.effects.volume == 1.0
    assert page.volume_slider.value() == 100


def test_pitch_readouts_show_direction_and_note(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.pitch_slider.setValue(2)
    assert page.pitch_value.text().startswith("+2")
    assert "B4" in page.pitch_note.text()


def test_chain_label_reflects_identity(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.speed_slider.setValue(100)
    page.volume_slider.setValue(100)
    assert "Nenhum efeito ativo" in page.chain_label.text()


def test_chain_label_reflects_speed_and_volume(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.speed_slider.setValue(150)
    page.volume_slider.setValue(150)
    assert "atempo=1.5" in page.chain_label.text()
    assert "volume=1.5" in page.chain_label.text()


def test_ffmpeg_unavailable_disables_speed_button(qtbot) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=False)
    assert page.speed_tone_button.isEnabled() is False
    assert page.ab_effects_button.isEnabled() is False


def test_ffmpeg_available_enables_speed_button(qtbot) -> None:
    page, _ = _make_page(qtbot, ffmpeg_available=True)
    assert page.speed_tone_button.isEnabled() is True
    assert page.ab_effects_button.isEnabled() is True


def test_reset_restores_identity(qtbot) -> None:
    page, controller = _make_page(qtbot)
    page.speed_slider.setValue(150)
    page.pitch_slider.setValue(3)
    page.volume_slider.setValue(75)
    page.reset_button.click()
    assert controller.effects.is_identity
    assert page.summary_label.text() == "Sem efeitos"
    assert page.speed_slider.value() == 100


def test_sync_external_changes_from_controller(qtbot) -> None:
    page, controller = _make_page(qtbot)
    controller.set_effects(AudioEffects(speed=0.5, pitch=semitones_to_ratio(-2), volume=1.5))
    assert page.speed_slider.value() == 50
    assert page.pitch_slider.value() == -2
    assert page.volume_slider.value() == 150


def test_explanations_label_populated_on_effect(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.speed_slider.setValue(200)
    assert "Velocidade" in page.explanations_label.text()
    assert "atempo" in page.explanations_label.text()


def test_pitch_note_changes_with_semitones(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.pitch_slider.setValue(0)
    base = page.pitch_note.text()
    page.pitch_slider.setValue(-3)
    assert page.pitch_note.text() != base
    assert page.pitch_note.text() == semitones_note_name(-3)


def test_preview_button_disabled_without_engine(qtbot) -> None:
    page, _ = _make_page(qtbot)
    assert page.preview_button.isEnabled() is False


def test_preview_button_enabled_with_engine(qtbot) -> None:
    page, _ = _make_page(qtbot, engine=LocalEngine("about:blank"))
    assert page.preview_button.isEnabled() is True


def test_preview_invalid_url_shows_notice(qtbot) -> None:
    page, _ = _make_page(qtbot)
    page.preview_url_input.setText("isto não é uma URL")
    page._preview_media()
    assert page.preview_notice.isHidden() is False
    assert "URL" in page.preview_notice.text()


def test_preview_engine_failure_shows_notice(qtbot) -> None:
    page, _ = _make_page(qtbot, engine=RaisesEngine())
    page.preview_url_input.setText("https://example.com/video")
    page._preview_media()
    qtbot.waitUntil(
        lambda: "Não foi possível preparar" in page.preview_notice.text(), timeout=4000
    )
    assert page.preview_button.isEnabled() is True
    assert page.preview_button.text() == "PRÉ-VISUALIZAR"


def test_preview_success_opens_and_closes_dialog(qtbot, tmp_path) -> None:
    wav = tmp_path / "tone.wav"
    render_tone_wav(wav, 440.0)
    page, _ = _make_page(qtbot, engine=LocalEngine(QUrl.fromLocalFile(str(wav)).toString()))
    page.preview_url_input.setText("https://example.com/video")
    page._preview_media()
    qtbot.waitUntil(lambda: page._preview_dialog is not None, timeout=4000)
    dialog = page._preview_dialog
    assert "example.com" in dialog.windowTitle()
    dialog.reject()
    qtbot.waitUntil(lambda: page._preview_dialog is None, timeout=4000)
    assert page.preview_button.isEnabled() is True