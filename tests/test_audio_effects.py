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


def test_build_audio_filters_toggles_alone():
    assert build_audio_filters(1.0, 1.0, 1.0, bass=True) == "bass=g=6:f=100"
    assert build_audio_filters(1.0, 1.0, 1.0, echo=True) == "aecho=0.7:0.7:300:0.3"
    assert build_audio_filters(1.0, 1.0, 1.0, tremolo=True) == "tremolo=f=5:d=0.25"
    assert build_audio_filters(1.0, 1.0, 1.0, normalize=True) == (
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )


def test_build_audio_filters_toggles_with_speed_and_volume():
    chain = build_audio_filters(1.5, 1.0, 1.25, bass=True, echo=True, tremolo=True)
    assert chain == "atempo=1.5,bass=g=6:f=100,aecho=0.7:0.7:300:0.3,tremolo=f=5:d=0.25,volume=1.25"


def test_build_audio_filters_normalize_runs_last_after_volume():
    chain = build_audio_filters(1.0, 1.0, 0.5, normalize=True)
    assert chain == "volume=0.5,loudnorm=I=-16:TP=-1.5:LRA=11"


def test_audio_effects_toggle_is_identity():
    assert AudioEffects(bass=True).is_identity is False
    assert AudioEffects(echo=True).is_identity is False
    assert AudioEffects(tremolo=True).is_identity is False
    assert AudioEffects(normalize=True).is_identity is False


def test_audio_effects_active_names_toggles():
    names = AudioEffects(bass=True, echo=True, tremolo=True, normalize=True).active_effect_names()
    text = " ".join(names)
    assert "Graves" in text
    assert "Eco" in text
    assert "Tremolo" in text
    assert "loudness" in text.lower()


def test_audio_effects_summary_toggles():
    summary = AudioEffects(bass=True, normalize=True).summary()
    assert "·" in summary
    assert "Graves" in summary
    assert "R128" in summary


def test_audio_effects_filter_chain_toggles():
    assert AudioEffects(bass=True).filter_chain() == "bass=g=6:f=100"
    assert AudioEffects().filter_chain() is None


def test_effects_explanations_toggles():
    explanations = effects_explanations(AudioEffects(bass=True, normalize=True))
    text = " ".join(explanations)
    assert len(explanations) == 2
    assert "bass" in text
    assert "loudnorm" in text


def test_controller_persists_toggles(tmp_path):
    from mediadownloader.services.settings_service import SettingsService

    settings = SettingsService(tmp_path / "settings.json")
    controller = AudioEffectsController(settings)
    controller.set_effects(AudioEffects(
        speed=1.25, pitch=semitones_to_ratio(1), volume=1.1,
        bass=True, echo=True, tremolo=True, normalize=True,
    ))

    reloaded = AudioEffectsController(SettingsService(tmp_path / "settings.json"))
    assert reloaded.effects.bass is True
    assert reloaded.effects.echo is True
    assert reloaded.effects.tremolo is True
    assert reloaded.effects.normalize is True
    assert reloaded.effects.speed == 1.25


def test_controller_set_toggle_noop_does_not_emit():
    controller = AudioEffectsController()
    received = []
    controller.effects_changed.connect(lambda effects: received.append(effects))
    controller.set_bass(False)
    controller.set_echo(False)
    assert received == []
    controller.set_bass(True)
    assert len(received) == 1
    assert received[0].bass is True


def test_controller_set_effects_resets_flags_when_omitted():
    controller = AudioEffectsController()
    controller.set_bass(True)
    controller.set_effects(AudioEffects(speed=1.5, pitch=1.0, volume=1.0))
    assert controller.effects.bass is False
    assert controller.effects.speed == 1.5


def test_audio_effects_to_dict_roundtrips_flags():
    effects = AudioEffects(bass=True, echo=True, tremolo=True, normalize=True)
    assert AudioEffects(**effects.to_dict()) == effects


def test_controller_set_speed_preserves_toggles():
    controller = AudioEffectsController()
    controller.set_bass(True)
    controller.set_normalize(True)
    controller.set_speed(1.5)
    assert controller.effects.bass is True
    assert controller.effects.normalize is True
    assert controller.effects.echo is False
    assert controller.effects.speed == 1.5


def test_controller_set_pitch_preserves_toggles():
    controller = AudioEffectsController()
    controller.set_echo(True)
    controller.set_pitch(semitones_to_ratio(2))
    assert controller.effects.echo is True
    assert abs(controller.effects.semitones - 2.0) < 1e-3


def test_controller_set_volume_preserves_toggles():
    controller = AudioEffectsController()
    controller.set_tremolo(True)
    controller.set_volume(0.8)
    assert controller.effects.tremolo is True
    assert controller.effects.volume == 0.8


def test_controller_toggle_preserves_speed_pitch_volume():
    controller = AudioEffectsController()
    controller.set_effects(AudioEffects(speed=1.5, pitch=semitones_to_ratio(-2), volume=1.2))
    controller.set_bass(True)
    assert controller.effects.speed == 1.5
    assert abs(controller.effects.semitones + 2.0) < 1e-3
    assert controller.effects.volume == 1.2