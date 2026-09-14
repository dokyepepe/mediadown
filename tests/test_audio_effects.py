"""Tests for the centralized audio effects module."""

from mediadownloader.core.audio_effects import (
    PITCH_SEMITONES,
    REFERENCE_TONE_FREQUENCY_HZ,
    SPEED_PRESETS,
    TONE_SAMPLE_RATE,
    VOLUME_PRESETS,
    AudioEffects,
    AudioEffectsController,
    build_audio_filters,
    effects_explanations,
    ratio_to_semitones,
    render_tone_wav,
    semitones_note_name,
    semitones_to_ratio,
    sine_wave_pcm,
    write_wav_file,
)
from mediadownloader.core.format_manager import FormatManager


def test_build_audio_filters_matches_format_manager():
    assert FormatManager.build_audio_filters(1.5, 2 ** (1 / 12), 1.25) == build_audio_filters(
        1.5, 2 ** (1 / 12), 1.25
    )


def test_build_audio_filters_all_stages():
    chain = build_audio_filters(1.5, 2 ** (1 / 12), 1.25)
    assert chain == (
        "aresample=44100,asetrate=46722.3,aresample=44100,atempo=0.943874,"
        "atempo=1.5,volume=1.25"
    )


def test_build_audio_filters_speed_only():
    assert build_audio_filters(0.5, 1.0, 1.0) == "atempo=0.5"


def test_build_audio_filters_volume_above_100_percent():
    assert build_audio_filters(1.0, 1.0, 1.5) == "volume=1.5"


def test_build_audio_filters_identity_returns_none():
    assert build_audio_filters(1.0, 1.0, 1.0) is None


def test_audio_effects_is_identity():
    assert AudioEffects().is_identity is True
    assert AudioEffects(volume=1.25).is_identity is False


def test_audio_effects_semitones():
    effects = AudioEffects(pitch=2 ** (2 / 12))
    assert effects.semitones == 2.0


def test_ratio_semitones_roundtrip():
    ratio = semitones_to_ratio(3)
    assert abs(ratio_to_semitones(ratio) - 3.0) < 1e-9


def test_audio_effects_filter_chain_includes_volume():
    effects = AudioEffects(speed=1.0, pitch=1.0, volume=2.0)
    assert effects.filter_chain() == "volume=2"


def test_audio_effects_active_names_speed():
    assert AudioEffects(speed=1.5).active_effect_names() == ("1.5x (mais rápido)",)


def test_audio_effects_active_names_pitch_up():
    effects = AudioEffects(pitch=semitones_to_ratio(2))
    assert "semitons" in effects.active_effect_names()[0]
    assert "mais agudo" in effects.active_effect_names()[0]


def test_audio_effects_active_names_volume_down():
    assert AudioEffects(volume=0.5).active_effect_names() == ("50% do volume (mais baixo)",)


def test_audio_effects_summary_combines_all():
    effects = AudioEffects(speed=1.5, pitch=semitones_to_ratio(-1), volume=1.25)
    summary = effects.summary()
    assert "·" in summary
    assert "mais rápido" in summary
    assert "mais grave" in summary
    assert "mais alto" in summary


def test_audio_effects_summary_identity():
    assert AudioEffects().summary() == "Sem efeitos"


def test_audio_effects_identity_no_chain():
    assert AudioEffects().filter_chain() is None


def test_presets_have_directional_labels():
    for value, label in SPEED_PRESETS:
        assert label and float(value) > 0
    for value, label in VOLUME_PRESETS:
        assert label and float(value) > 0


def test_pitch_semitones_symmetric():
    assert PITCH_SEMITONES[0] == -PITCH_SEMITONES[-1]
    assert 0 in PITCH_SEMITONES


def test_volume_presets_cover_across_100():
    values = [float(value) for value, _ in VOLUME_PRESETS]
    assert any(value < 1.0 for value in values)
    assert any(value > 1.0 for value in values)


def test_semitones_note_name_a4():
    assert semitones_note_name(0) == f"A4 · {REFERENCE_TONE_FREQUENCY_HZ:.2f} Hz"


def test_semitones_note_name_up_two_is_b4():
    assert semitones_note_name(2) == f"B4 · {440.0 * 2 ** (2 / 12):.2f} Hz"


def test_sine_wave_pcm_has_expected_frame_count():
    frames = sine_wave_pcm(440.0, 0.5, amplitude=0.5)
    assert len(frames) == 2 * TONE_SAMPLE_RATE // 2


def test_tone_wav_roundtrip(tmp_path):
    import wave

    path = render_tone_wav(tmp_path / "tone.wav", 440.0, duration_seconds=0.2)
    assert path.exists()
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == TONE_SAMPLE_RATE
        assert handle.getnframes() == TONE_SAMPLE_RATE // 5


def test_write_wav_file_smoke(tmp_path):
    path = write_wav_file(tmp_path / "x.wav", b"\x00\x00" * 8)
    assert path.stat().st_size > 44


def test_effects_explanations_speed():
    explanations = effects_explanations(AudioEffects(speed=1.5))
    assert len(explanations) == 1
    assert "atempo" in explanations[0]


def test_effects_explanations_pitch_mentions_reference():
    explanations = effects_explanations(AudioEffects(pitch=semitones_to_ratio(2)))
    assert "440" in explanations[0]


def test_controller_persists_and_loads(tmp_path):
    from mediadownloader.services.settings_service import SettingsService

    settings = SettingsService(tmp_path / "settings.json")
    controller = AudioEffectsController(settings)
    controller.set_effects(AudioEffects(speed=1.5, pitch=semitones_to_ratio(-1), volume=1.25))

    reloaded = AudioEffectsController(SettingsService(tmp_path / "settings.json"))
    assert reloaded.effects.speed == 1.5
    assert abs(reloaded.effects.semitones + 1.0) < 1e-3
    assert reloaded.effects.volume == 1.25


def test_controller_noop_does_not_emit():
    from mediadownloader.core.audio_effects import AudioEffectsController

    controller = AudioEffectsController()
    received = []
    controller.effects_changed.connect(lambda effects: received.append(effects))
    controller.set_effects(AudioEffects(speed=1.0, pitch=1.0, volume=1.0))
    assert received == []


def test_controller_emits_once_on_change(qtbot):
    from mediadownloader.core.audio_effects import AudioEffectsController

    controller = AudioEffectsController()
    received = []
    controller.effects_changed.connect(lambda effects: received.append(effects))
    controller.set_speed(1.5)
    controller.set_speed(1.5)  # identical — no duplicate emission
    assert len(received) == 1
    assert received[0].speed == 1.5


def test_controller_clamps_speed_and_volume():
    controller = AudioEffectsController()
    controller.set_effects(AudioEffects(speed=5.0, pitch=1.0, volume=9.0))
    assert controller.effects.speed == 2.0
    assert controller.effects.volume == 4.0