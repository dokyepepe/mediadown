"""Local audio editing helpers: format probing, waveform decoding and FFmpeg export.

This module stays Qt-free so the logic (duration parsing, envelope bucketing,
filter building and export command assembly) can be unit-tested without a GUI.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from array import array
from pathlib import Path

from mediadownloader.core.audio_effects import AudioEffects

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

EDITABLE_FORMATS = ("mp3", "m4a", "aac", "opus", "flac", "wav")

_DEFAULT_FORMAT = "mp3"

_CODEC_BY_FORMAT: dict[str, tuple[str, str | None]] = {
    "mp3": ("libmp3lame", None),
    "m4a": ("aac", "192k"),
    "aac": ("aac", "192k"),
    "opus": ("libopus", "128k"),
    "flac": ("flac", None),
    "wav": ("pcm_s16le", None),
}

#: Containers whose muxer accepts the ``attached_pic`` video stream, so a cover
#: copied from the source survives the re-encode. Opus and WAV are audio-only
#: containers and would fail if the picture stream were mapped into them.
_FORMATS_WITH_VIDEO_ART = frozenset({"mp3", "m4a", "aac", "flac"})

_WAVEFORM_SAMPLE_RATE = 4000
_WAVEFORM_POINTS = 1200

_DURATION_OUTPUT = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$")
_FFMPEG_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

_MAX_SANE_SECONDS = 12.0 * 3600.0  # hard cap for unknown durations


def parse_duration_output(raw: str) -> float | None:
    """Parse ``ffprobe -show_entries format=duration`` output (one float)."""
    match = _DURATION_OUTPUT.search(raw)
    if not match:
        return None
    return float(match.group(1))


def parse_ffmpeg_duration_text(raw: str) -> float | None:
    """Parse ``hh:mm:ss.xx`` from ``ffmpeg -i`` stderr (used as a fallback)."""
    match = _FFMPEG_DURATION.search(raw)
    if not match:
        return None
    hours, minutes, seconds = (float(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def probe_duration(
    ffmpeg: Path,
    ffprobe: Path | None,
    path: Path,
    timeout: float = 15.0,
) -> float | None:
    """Return media duration in seconds, preferring ffprobe and falling back to
    parsing ``ffmpeg -i`` output. Returns ``None`` when neither works."""
    if ffprobe is not None:
        try:
            completed = subprocess.run(
                [
                    str(ffprobe), "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
            if completed.returncode == 0:
                duration = parse_duration_output(completed.stdout)
                if duration is not None and duration > 0:
                    return duration
        except subprocess.SubprocessError:
            pass
    try:
        completed = subprocess.run(
            [str(ffmpeg), "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
        return parse_ffmpeg_duration_text(completed.stderr + "\n" + completed.stdout)
    except subprocess.SubprocessError:
        return None


def envelope_from_pcm(pcm: bytes, points: int = _WAVEFORM_POINTS) -> tuple[tuple[float, float], ...]:
    """Bucket raw 16-bit mono PCM bytes into ``(min, max)`` peak pairs in -1..1.

    Each returned pair is the loudest and quietest amplitude within one bucket,
    which paints a faithful peak waveform independent of the buffer length.
    """
    if not pcm:
        raise ValueError("Sem dados de áudio para desenhar a forma de onda.")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    points = max(1, int(points))
    bucket = max(1, math.ceil(len(samples) / points))
    peaks: list[tuple[float, float]] = []
    for start in range(0, len(samples), bucket):
        chunk = samples[start:start + bucket]
        lo = min(chunk) / 32768.0
        hi = max(chunk) / 32768.0
        peaks.append((max(-1.0, lo), min(1.0, hi)))
    return tuple(peaks)


def decode_pcm(
    ffmpeg: Path,
    path: Path,
    sample_rate: int = _WAVEFORM_SAMPLE_RATE,
    timeout: float = 120.0,
) -> bytes:
    """Decode an audio file to raw ``s16le`` mono PCM at a low sample rate.

    Raises :class:`RuntimeError` when decoding fails so callers can degrade
    gracefully instead of freezing the UI.
    """
    try:
        completed = subprocess.run(
            [
                str(ffmpeg), "-hide_banner", "-loglevel", "error",
                "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate),
                "-f", "s16le", "-",
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.SubprocessError as error:
        raise RuntimeError(f"Falha ao decodificar o áudio para a forma de onda: {error}") from error
    if completed.returncode != 0 or not completed.stdout:
        stderr_tail = (completed.stderr or b"").decode("utf-8", "replace")[-300:]
        raise RuntimeError(
            f"Falha ao decodificar o áudio para a forma de onda (ffmpeg {completed.returncode}): "
            f"{stderr_tail}"
        )
    return completed.stdout


def estimate_duration_from_pcm(pcm_bytes: int, sample_rate: int) -> float:
    """Estimate playback seconds from raw ``s16le`` mono byte count."""
    return pcm_bytes / 2.0 / max(1, sample_rate)


def decode_envelope(
    ffmpeg: Path,
    path: Path,
    points: int = _WAVEFORM_POINTS,
    sample_rate: int = _WAVEFORM_SAMPLE_RATE,
    timeout: float = 120.0,
) -> tuple[tuple[float, float], ...]:
    """Decode an audio file to a peak envelope (raw ``s16le`` mono at low rate)."""
    return envelope_from_pcm(decode_pcm(ffmpeg, path, sample_rate, timeout), points=points)


def trim_fade_filter(
    start: float,
    end: float,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
) -> str | None:
    """Build the ``afade`` graph for the trimmed segment, or ``None`` for none.

    Fades are clamped to the selection and scaled down together when their sum
    would exceed the clip duration, so the fade-out never starts before zero.
    """
    start = max(0.0, float(start))
    end = max(start, float(end))
    duration = end - start
    if duration <= 0:
        return None
    fade_in = max(0.0, float(fade_in))
    fade_out = max(0.0, float(fade_out))
    total = fade_in + fade_out
    if total > duration and fade_in > 0 and fade_out > 0:
        ratio = duration / total
        fade_in *= ratio
        fade_out *= ratio
    else:
        fade_in = min(fade_in, duration)
        fade_out = min(fade_out, duration)
    parts: list[str] = []
    if fade_in > 0:
        parts.append(f"afade=t=in:d={fade_in:g}")
    if fade_out > 0:
        parts.append(f"afade=t=out:st={duration - fade_out:g}:d={fade_out:g}")
    return ",".join(parts) if parts else None


def edit_filter_chain(
    start: float,
    end: float,
    fade_in: float,
    fade_out: float,
    effects: AudioEffects | None = None,
) -> str | None:
    """Combine the current effect chain with the trim/fade graph.

    The effect chain (speed / pitch / volume / toggles) runs first so the fade
    envelope is applied to the final waveform and is never re-normalized away
    by loudnorm.
    """
    effect_chain = effects.filter_chain() if effects is not None else None
    fade_chain = trim_fade_filter(start, end, fade_in, fade_out)
    if effect_chain and fade_chain:
        return f"{effect_chain},{fade_chain}"
    return effect_chain or fade_chain


def audio_format_from_suffix(path: Path | str) -> str:
    """Map a file suffix to an editable format id, defaulting to MP3."""
    suffix = (Path(path).suffix or "").lstrip(".").lower()
    return suffix if suffix in _CODEC_BY_FORMAT else _DEFAULT_FORMAT


def export_command(
    ffmpeg: Path,
    input_path: Path,
    output_path: Path,
    start: float = 0.0,
    end: float | None = None,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    effects: AudioEffects | None = None,
    audio_format: str | None = None,
) -> list[str]:
    """Assemble the FFmpeg command that exports the edited segment."""
    start = max(0.0, float(start))
    duration = None
    if end is not None and float(end) > start:
        duration = float(end) - start
    fmt = (audio_format or audio_format_from_suffix(output_path)).lower()
    if fmt not in _CODEC_BY_FORMAT:
        fmt = _DEFAULT_FORMAT
    chain = edit_filter_chain(start, end or start + (duration or 0.0), fade_in, fade_out, effects)
    args = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(input_path),
    ]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    # Keep only the audio stream plus any embedded cover (the ``attached_pic``
    # video stream that MP3/M4A/FLAC use to carry album art). A flat ``-vn`` or
    # ``-map 0:a`` would silently drop the cover when the segment is re-encoded.
    args += ["-map", "0:a:0", "-map", "0:v:m:attached_pic?"]
    if fmt in _FORMATS_WITH_VIDEO_ART:
        args += ["-c:v", "copy"]
    if chain:
        args += ["-af", chain]
    codec, bitrate = _CODEC_BY_FORMAT[fmt]
    args += ["-c:a", codec]
    if fmt == "mp3":
        args += ["-q:a", "2"]
    elif bitrate:
        args += ["-b:a", bitrate]
    args.append(str(output_path))
    return args


def preview_command(
    ffmpeg: Path,
    input_path: Path,
    output_path: Path,
    start: float,
    end: float,
    fade_in: float,
    fade_out: float,
    effects: AudioEffects | None = None,
) -> list[str]:
    """Short-cut of :func:`export_command` forcing a compact M4A preview."""
    return export_command(
        ffmpeg,
        input_path,
        output_path,
        start=start,
        end=end,
        fade_in=fade_in,
        fade_out=fade_out,
        effects=effects,
        audio_format="m4a",
    )


def max_editor_seconds(duration: float | None) -> float:
    """Guard against absurd durations in time inputs (still real for podcasts)."""
    if duration is None or duration <= 0:
        return _MAX_SANE_SECONDS
    return min(float(duration), _MAX_SANE_SECONDS)


__all__ = [
    "EDITABLE_FORMATS",
    "_CODEC_BY_FORMAT",
    "audio_format_from_suffix",
    "decode_envelope",
    "decode_pcm",
    "edit_filter_chain",
    "envelope_from_pcm",
    "estimate_duration_from_pcm",
    "export_command",
    "max_editor_seconds",
    "parse_duration_output",
    "parse_ffmpeg_duration_text",
    "preview_command",
    "probe_duration",
    "trim_fade_filter",
]