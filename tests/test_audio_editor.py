"""Unit tests for the Qt-free audio-editing helpers."""

from __future__ import annotations

import subprocess
from array import array

import pytest

from mediadownloader.core.audio_editor import (
    estimate_duration_from_pcm,
    envelope_from_pcm,
    export_command,
    max_editor_seconds,
    parse_duration_output,
    parse_ffmpeg_duration_text,
    probe_duration,
    trim_fade_filter,
)
from mediadownloader.core.audio_effects import AudioEffects


def test_parse_duration_output_reads_float() -> None:
    assert parse_duration_output("12.5\n") == 12.5
    assert parse_duration_output("\n\n  3  \n") == 3.0


def test_parse_duration_output_rejects_garbage() -> None:
    assert parse_duration_output("N/A") is None
    assert parse_duration_output("") is None
    assert parse_duration_output("abc12.5") is None


def test_parse_ffmpeg_duration_text_reads_hms() -> None:
    assert parse_ffmpeg_duration_text("Duration: 00:01:02.50, start: 0.000000") == 62.5
    assert parse_ffmpeg_duration_text(
        "Duration: 01:00:00.00, bitrate: 128 kb/s\n  Stream #0:0"
    ) == 3600.0
    assert parse_ffmpeg_duration_text("no duration here") is None


def test_probe_duration_prefers_ffprobe(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(args, **kwargs):
        seen.append(list(args))
        if any(a == "-show_entries" for a in args):
            return subprocess.CompletedProcess(args, 0, stdout="42.5\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

    monkeypatch.setattr("mediadownloader.core.audio_editor.subprocess.run", fake_run)
    assert probe_duration("ffmpeg-bin", "ffprobe-bin", "file.mp3") == 42.5
    assert any("ffprobe" in a for a in seen[-1])


def test_probe_duration_falls_back_to_ffmpeg_i(monkeypatch) -> None:
    def fake_run(args, **kwargs):
        if any(a == "-show_entries" for a in args):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        assert args[0] == "ffmpeg-bin" and args[1] == "-i"
        return subprocess.CompletedProcess(
            args, 0, stdout="", stderr="Duration: 00:01:02.50, bitrate: 128 kb/s"
        )

    monkeypatch.setattr("mediadownloader.core.audio_editor.subprocess.run", fake_run)
    assert probe_duration("ffmpeg-bin", "ffprobe-bin", "file.mp3") == 62.5


def test_probe_duration_returns_none_on_timeout(monkeypatch) -> None:
    def fake_run(args, **kwargs):
        if any(a == "-show_entries" for a in args):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 0))

    monkeypatch.setattr("mediadownloader.core.audio_editor.subprocess.run", fake_run)
    assert probe_duration("ffmpeg-bin", "ffprobe-bin", "file.mp3") is None


def _pcm(values: list[int]) -> bytes:
    samples = array("h", values)
    return samples.tobytes()


def test_envelope_from_pcm_rejects_empty() -> None:
    with pytest.raises(ValueError):
        envelope_from_pcm(b"")


def test_envelope_from_pcm_silence_is_zero_peaks() -> None:
    peaks = envelope_from_pcm(_pcm([0] * 64), points=8)
    assert len(peaks) == 8
    assert all(lo == 0.0 and hi == 0.0 for lo, hi in peaks)


def test_envelope_from_pcm_captures_bucket_min_max() -> None:
    peaks = envelope_from_pcm(_pcm([-16000, 12000] * 100), points=4)
    assert len(peaks) == 4
    for lo, hi in peaks:
        assert lo == pytest.approx(-16000 / 32768.0)
        assert hi == pytest.approx(12000 / 32768.0)


def test_envelope_from_pcm_clamps_to_unit_range() -> None:
    peaks = envelope_from_pcm(_pcm([-32768, 32767]), points=1)
    lo, hi = peaks[0]
    assert lo == -1.0
    assert hi == pytest.approx(1.0, abs=1e-4)


def test_estimate_duration_from_pcm_counts_bytes() -> None:
    assert estimate_duration_from_pcm(2 * 4000 * 30, 4000) == pytest.approx(30.0)


def test_trim_fade_filter_identity_is_none() -> None:
    assert trim_fade_filter(0.0, 10.0) is None
    assert trim_fade_filter(5.0, 5.0) is None


def test_trim_fade_filter_fade_out_uses_correct_start() -> None:
    chain = trim_fade_filter(0.0, 10.0, fade_in=1.5, fade_out=2.0)
    assert "afade=t=in:d=1.5" in chain
    assert "afade=t=out:st=8:d=2" in chain


def test_trim_fade_filter_scales_overlapping_fades() -> None:
    chain = trim_fade_filter(0.0, 6.0, fade_in=5.0, fade_out=5.0)
    assert "afade=t=in:d=3" in chain
    assert "out:st=3:d=3" in chain


def test_trim_fade_filter_clamps_and_ignores_negatives() -> None:
    chain = trim_fade_filter(2.0, 12.0, fade_in=-1.0, fade_out=99.0)
    assert "afade=t=in" not in chain
    assert chain == "afade=t=out:st=0:d=10"


def _shapes(effects=None):
    return export_command(
        "ffmpeg", "in.mp3", "out.mp3", start=1.0, end=6.0, fade_in=0.5, effects=effects
    )


def test_export_command_mp3_vbr_codec() -> None:
    args = _shapes()
    assert args[0] == "ffmpeg"
    assert "-ss" in args and "1.000" in args
    assert "-t" in args and "5.000" in args
    assert args[args.index("-c:a") + 1] == "libmp3lame"
    assert args[args.index("-q:a") + 1] == "2"
    assert "out.mp3" == args[-1]


def test_export_command_wav_uses_pcm() -> None:
    args = export_command("ffmpeg", "in.mp3", "out.wav", start=0.0, end=3.0)
    assert args[args.index("-c:a") + 1] == "pcm_s16le"
    assert "-q:a" not in args


def test_export_command_m4a_sets_bitrate() -> None:
    args = export_command("ffmpeg", "in.mp3", "out.m4a", start=0.0, end=3.0)
    assert args[args.index("-c:a") + 1] == "aac"
    assert args[args.index("-b:a") + 1] == "192k"


def test_export_command_unknown_format_defaults_to_mp3() -> None:
    args = export_command("ffmpeg", "in.mp3", "out.xyz", start=0.0, end=3.0)
    assert args[args.index("-c:a") + 1] == "libmp3lame"


def test_export_command_skips_duration_when_end_is_none() -> None:
    args = export_command("ffmpeg", "in.mp3", "out.mp3", start=0.0)
    assert "-t" not in args


def test_export_command_applies_effect_chain_before_fades() -> None:
    effects = AudioEffects(speed=1.5)
    args = _shapes(effects)
    af_index = args.index("-af")
    chain = args[af_index + 1]
    assert chain.startswith("atempo=1.5")
    assert "afade=t=in:d=0.5" in chain


def test_audio_format_from_suffix_defaults() -> None:
    from pathlib import Path

    from mediadownloader.core.audio_editor import audio_format_from_suffix

    assert audio_format_from_suffix(Path("song.m4a")) == "m4a"
    assert audio_format_from_suffix(Path("song.FLAC")) == "flac"
    assert audio_format_from_suffix(Path("song")) == "mp3"
    assert audio_format_from_suffix(Path("song.weird")) == "mp3"


def test_max_editor_seconds_caps_unknown_durations() -> None:
    assert max_editor_seconds(None) == max_editor_seconds(0) == 43200.0
    assert max_editor_seconds(90.0) == 90.0