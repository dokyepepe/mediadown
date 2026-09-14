"""Centralized audio effect presets, FFmpeg filter building, and human-readable descriptions.

All UI components (home page, preview dialog, settings) consume these
constants and helpers so the user sees consistent, explicit labels
describing exactly what speed, pitch and volume changes will do.
"""

from __future__ import annotations

import array
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from mediadownloader.services.settings_service import SettingsService


# ── Presets ────────────────────────────────────────────────────────────────────
# (value, display label) — labels include the directional effect for clarity.

SPEED_PRESETS: tuple[tuple[str, str], ...] = (
    ("0.5",  "0,5x — mais lento"),
    ("0.75", "0,75x — mais lento"),
    ("1.0",  "1,0x — normal"),
    ("1.25", "1,25x — mais rápido"),
    ("1.5",  "1,5x — mais rápido"),
    ("2.0",  "2,0x — mais rápido"),
)

VOLUME_PRESETS: tuple[tuple[str, str], ...] = (
    ("0.5",  "50% — mais baixo"),
    ("0.75", "75% — mais baixo"),
    ("1.0",  "100% — normal"),
    ("1.25", "125% — mais alto"),
    ("1.5",  "150% — mais alto"),
    ("2.0",  "200% — mais alto"),
)

PITCH_SEMITONES: tuple[int, ...] = (-3, -2, -1, 0, 1, 2, 3)


# ── Tones and sound generation ─────────────────────────────────────────────────

TONE_SAMPLE_RATE = 44100
REFERENCE_TONE_FREQUENCY_HZ = 440.0  # musical A4


def sine_wave_pcm(
    frequency_hz: float,
    duration_seconds: float,
    sample_rate: int = TONE_SAMPLE_RATE,
    amplitude: float = 0.5,
) -> bytes:
    """Render a mono 16-bit PCM sine wave (no WAV header)."""
    step = 2.0 * math.pi * frequency_hz / sample_rate
    count = max(1, int(sample_rate * duration_seconds))
    samples = array.array("h")
    for index in range(count):
        value = amplitude * math.sin(step * index)
        samples.append(max(-32768, min(32767, round(value * 32767))))
    return samples.tobytes()


def write_wav_file(path: Path, pcm: bytes, sample_rate: int = TONE_SAMPLE_RATE) -> Path:
    """Write 16-bit mono PCM bytes to a standard WAV file."""
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return Path(path)


def render_tone_wav(
    path: Path,
    frequency_hz: float,
    duration_seconds: float = 0.8,
    amplitude: float = 0.5,
    sample_rate: int = TONE_SAMPLE_RATE,
) -> Path:
    """Render a simple tone to a playable WAV file."""
    return write_wav_file(
        path,
        sine_wave_pcm(frequency_hz, duration_seconds, sample_rate, amplitude),
        sample_rate=sample_rate,
    )


def scale_pcm_volume(pcm: bytes, volume: float) -> bytes:
    """Multiply a 16-bit mono PCM buffer by a volume factor with clipping."""
    if volume == 1.0:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm)
    for index in range(len(samples)):
        samples[index] = max(-32768, min(32767, round(samples[index] * volume)))
    return samples.tobytes()


# ── Conversion helpers ────────────────────────────────────────────────────────

def semitones_to_ratio(semitones: int | float) -> float:
    """Convert musical semitones to a frequency ratio."""
    return 2 ** (float(semitones) / 12)


def ratio_to_semitones(ratio: float) -> float:
    """Convert frequency ratio back to semitones (inverse of ``semitones_to_ratio``)."""
    if ratio <= 0.0:
        return 0.0
    return 12.0 * math.log2(ratio)


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def semitones_note_name(semitones: float) -> str:
    """Name the note reached by shifting A4 (440 Hz) and its new frequency."""
    st = round(semitones)
    midi = 69 + st
    name = _NOTE_NAMES[midi % 12]
    octave = max(0, midi // 12 - 1)
    frequency = REFERENCE_TONE_FREQUENCY_HZ * 2 ** (st / 12)
    return f"{name}{octave} · {frequency:.2f} Hz"


# ── Human-readable descriptions ───────────────────────────────────────────────

def _speed_description(value: float) -> str:
    if value < 1.0:
        return f"{value:.2g}x (mais lento)"
    if value > 1.0:
        return f"{value:.2g}x (mais rápido)"
    return "1,0x (normal)"


def _semitones_description(semitones: float) -> str:
    st = round(semitones)
    if st == 0:
        return "sem alteração de tom"
    direction = "mais grave" if st < 0 else "mais agudo"
    return f"{st:+d} semitons ({direction})"


def _volume_description(value: float) -> str:
    pct = round(value * 100)
    if value < 1.0:
        return f"{pct}% do volume (mais baixo)"
    if value > 1.0:
        return f"{pct}% do volume (mais alto)"
    return "100% do volume (normal)"


# ── AudioEffects dataclass ───────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AudioEffects:
    """Immutable snapshot of the three audio adjustments.

    Provides both machine-readable values for FFmpeg and human-readable
    descriptions used by the preview and home page.
    """

    speed: float = 1.0
    pitch: float = 1.0   # ratio (1.0 = no shift, >1.0 = sharper, <1.0 = flatter)
    volume: float = 1.0

    @property
    def semitones(self) -> float:
        """Pitch expressed in semitones (rounded to 4 decimals for display)."""
        return round(ratio_to_semitones(self.pitch), 4)

    @property
    def is_identity(self) -> bool:
        return self.speed == 1.0 and self.pitch == 1.0 and self.volume == 1.0

    def speed_description(self) -> str:
        return _speed_description(self.speed)

    def pitch_description(self) -> str:
        return _semitones_description(self.semitones)

    def volume_description(self) -> str:
        return _volume_description(self.volume)

    def filter_chain(self) -> str | None:
        """Return the ``-af`` filter string, or ``None`` when nothing is altered."""
        return build_audio_filters(self.speed, self.pitch, self.volume)

    def active_effect_names(self) -> tuple[str, ...]:
        """One human-readable string per active effect (speed / pitch / volume)."""
        parts: list[str] = []
        if self.speed != 1.0:
            parts.append(self.speed_description())
        if self.pitch != 1.0:
            parts.append(self.pitch_description())
        if self.volume != 1.0:
            parts.append(self.volume_description())
        return tuple(parts)

    def summary(self) -> str:
        """Single-line summary of all active effects separated by ``·``."""
        parts = self.active_effect_names()
        if not parts:
            return "Sem efeitos"
        return " · ".join(parts)

    def to_dict(self) -> dict[str, float]:
        return {"speed": self.speed, "pitch": self.pitch, "volume": self.volume}


def effects_explanations(effects: AudioEffects) -> tuple[str, ...]:
    """Plain-text explanation of what each stage of the chain does."""
    parts: list[str] = []
    if effects.speed != 1.0:
        parts.append(
            f"Velocidade {effects.speed:g}x: o filtro atempo estica ou comprime "
            "o tempo sem mudar o tom."
        )
    if effects.pitch != 1.0:
        parts.append(
            f"Tom {effects.pitch_description()}: asetrate + aresample reamostram a "
            "frequência (referência Lá 440 Hz) preservando a duração."
        )
    if effects.volume != 1.0:
        parts.append(
            f"Volume {effects.volume_description()}: amplifica ou reduz a amplitude final."
        )
    return tuple(parts)


def build_audio_filters(
    speed: float = 1.0,
    pitch: float = 1.0,
    volume: float = 1.0,
) -> str | None:
    """Build the FFmpeg ``-af`` filter graph for speed / pitch / volume.

    Speed is stretched with ``atempo``; pitch shifts use ``asetrate`` +
    ``aresample`` + ``atempo=1/pitch`` (changes the key while preserving
    duration).  ``atempo`` is limited to [0.5, 2.0] per instance, so the
    pitch-recovery and speed stages remain as separate in-range filters.
    Volume is applied last.  Returns ``None`` when nothing is altered.
    """
    speed = float(speed or 1.0)
    pitch = float(pitch or 1.0)
    volume = float(volume or 1.0)
    if speed == 1.0 and pitch == 1.0 and volume == 1.0:
        return None
    filters: list[str] = []
    if pitch != 1.0:
        filters.extend((
            "aresample=44100",
            f"asetrate={44100 * pitch:g}",
            "aresample=44100",
            f"atempo={1 / pitch:g}",
        ))
    if speed != 1.0:
        filters.append(f"atempo={speed:g}")
    if volume != 1.0:
        filters.append(f"volume={volume:g}")
    return ",".join(filters)


# ── Shared controller ──────────────────────────────────────────────────────────

def _effects_equal(first: AudioEffects, second: AudioEffects) -> bool:
    return (
        math.isclose(first.speed, second.speed, rel_tol=1e-4)
        and math.isclose(first.pitch, second.pitch, rel_tol=1e-4)
        and math.isclose(first.volume, second.volume, rel_tol=1e-4)
    )


class AudioEffectsController(QObject):
    """Single, persistent source of truth for the active audio adjustments.

    Both the home page combo boxes and the dedicated Audio page edit this
    controller; every change is persisted (when a SettingsService is given)
    and broadcast through :attr:`effects_changed` so every UI stays in sync.
    Values are clamped to ranges the FFmpeg filters support.
    """

    effects_changed = Signal(object)

    def __init__(
        self,
        settings: SettingsService | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._effects = AudioEffects(
            speed=float(settings.get("downloads.audio_speed", 1.0)) if settings else 1.0,
            pitch=float(settings.get("downloads.audio_pitch", 1.0)) if settings else 1.0,
            volume=float(settings.get("downloads.audio_volume", 1.0)) if settings else 1.0,
        )

    @property
    def effects(self) -> AudioEffects:
        return self._effects

    def set_effects(self, effects: AudioEffects) -> None:
        """Apply the given snapshot, persist it, and notify listeners."""
        normalized = AudioEffects(
            speed=min(2.0, max(0.5, float(effects.speed or 1.0))),
            pitch=float(effects.pitch or 1.0) or 1.0,
            volume=min(4.0, max(0.0, float(effects.volume or 1.0))),
        )
        if _effects_equal(self._effects, normalized):
            return
        self._effects = normalized
        if self._settings is not None:
            self._settings.set("downloads.audio_speed", normalized.speed, save=False)
            self._settings.set("downloads.audio_pitch", normalized.pitch, save=False)
            self._settings.set("downloads.audio_volume", normalized.volume, save=False)
            self._settings.save()
        self.effects_changed.emit(normalized)

    def set_speed(self, value: float) -> None:
        self.set_effects(AudioEffects(value, self._effects.pitch, self._effects.volume))

    def set_pitch(self, ratio: float) -> None:
        self.set_effects(AudioEffects(self._effects.speed, ratio, self._effects.volume))

    def set_pitch_semitones(self, semitones: int | float) -> None:
        self.set_pitch(semitones_to_ratio(semitones))

    def set_volume(self, value: float) -> None:
        self.set_effects(AudioEffects(self._effects.speed, self._effects.pitch, value))

    def reset(self) -> None:
        """Restore the identity audio effects."""
        self.set_effects(AudioEffects())