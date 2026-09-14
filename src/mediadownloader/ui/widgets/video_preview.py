"""Modal media preview player with explicit, audible speed / pitch / volume effects.

The dialog shows exactly what will be applied: a human-readable summary of the
active effects, the exact FFmpeg ``-af`` filter chain, and an A/B toggle to
compare the original stream against the processed clip. Volume is applied live
(instant response) and also baked into the rendered clip by FFmpeg, so levels
above 100% are actually audible. Speed and pitch are rendered through FFmpeg
from the exact segment the user is listening to, keeping the preview as close
to real-time as the platform allows.

Robustness: every user-facing slot is guarded so no media/FFmpeg failure can
crash the dialog; the dialog degrades gracefully (original keeps playing with a
clear message), stale renders are discarded, and temp files are always removed.
"""

from __future__ import annotations

import functools
import uuid
from pathlib import Path
from tempfile import gettempdir

from PySide6.QtCore import QThreadPool, QTimer, QUrl, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QSlider, QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False

from mediadownloader.core.audio_effects import (
    SPEED_PRESETS, VOLUME_PRESETS, AudioEffects, AudioEffectsController,
    add_effect_presets, add_pitch_presets, combo_effect_value,
    select_effect_preset,
)
from mediadownloader.core.ffmpeg_manager import FFmpegManager
from mediadownloader.core.workers import PreviewRenderWorker
from mediadownloader.models import PreviewSource

from ..icons import set_button_icon
from ..widgets import PrimaryButton, SecondaryButton, ThemedIconLabel, WheelSafeComboBox


def _guarded(slot):
    """Never let a media/FFmpeg failure escape a Qt slot and crash the app."""

    @functools.wraps(slot)
    def wrapper(self, *args, **kwargs):
        try:
            return slot(self, *args, **kwargs)
        except Exception:  # noqa: BLE001 - blanket guard is the point
            try:
                self._set_status(
                    "A pré-visualização encontrou um problema inesperado. "
                    "A reprodução da fonte original continua disponível."
                )
            except Exception:  # noqa: BLE001
                pass

    return wrapper


class VideoPreviewDialog(QDialog):
    """Preview player with explicit tempo / pitch / volume control.

    Volume is applied instantly (as a live approximation) and also baked into
    the final clip by FFmpeg, so values above 100% become audible once the clip
    is rendered. While the processed clip is being built the original stream
    keeps playing and the UI states clearly what is happening and which effects
    are active. When an :class:`AudioEffectsController` is attached, every
    change made here is pushed to it, keeping the app (home, Audio tab and the
    final file) in sync.
    """

    def __init__(
        self,
        title: str,
        ffmpeg: FFmpegManager | None = None,
        audio_effects: AudioEffectsController | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        duration: float = 12.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Pré-visualizar — {title}")
        self.setModal(True)
        self.setAccessibleName(f"Pré-visualizar {title}")
        self.setMinimumSize(680, 600)
        self.resize(840, 640)
        self.ffmpeg = ffmpeg
        self.audio_effects = audio_effects
        self.preview_duration = duration
        self._render_pool = QThreadPool(self)
        self._render_pool.setMaxThreadCount(1)
        self._render_workers: dict[int, PreviewRenderWorker] = {}
        self._pending_render = False
        self._render_seq = 0
        self._source_url = ""
        self._source: PreviewSource | None = None
        self._merged = False
        self._has_audio = True
        self._local_path: Path | None = None
        self._listening_original = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(700)
        self._debounce.timeout.connect(self._start_render)
        self._build_ui()
        select_effect_preset(self.speed_combo, speed)
        select_effect_preset(self.pitch_combo, pitch)
        select_effect_preset(self.volume_combo, volume)
        if not _HAS_MULTIMEDIA:
            self._set_status("Módulo multimídia indisponível. Atualize o PySide6.")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        banner = QHBoxLayout()
        icon = ThemedIconLabel("video", 21)
        icon.setObjectName("StepIcon")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        title_label = QLabel("Pré-visualização da mídia")
        title_label.setObjectName("SectionTitle")
        self.subtitle = QLabel("Clique em Iniciar para reproduzir.")
        self.subtitle.setObjectName("Muted")
        self.subtitle.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(self.subtitle)
        banner.addWidget(icon)
        banner.addLayout(text, 1)
        root.addLayout(banner)

        if _HAS_MULTIMEDIA:
            self.video = QVideoWidget()
            self.video.setAccessibleName("Pré-visualização de vídeo")
            self.video.setMinimumHeight(200)
            root.addWidget(self.video, 1)

            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(1.0)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video)

            controls = QHBoxLayout()
            controls.setSpacing(8)
            self.play_button = SecondaryButton("Iniciar", icon_name="play")
            self.play_button.clicked.connect(self._toggle_play)
            controls.addWidget(self.play_button)
            self.compare_button = SecondaryButton("Comparar com original", icon_name="retry")
            self.compare_button.setToolTip(
                "Alterna entre o áudio original e a prévia com efeitos para você ouvir a diferença."
            )
            self.compare_button.setEnabled(False)
            self.compare_button.clicked.connect(self._toggle_compare)
            controls.addWidget(self.compare_button)
            self.position_slider = QSlider(Qt.Orientation.Horizontal)
            self.position_slider.setRange(0, 0)
            self.position_slider.sliderMoved.connect(self.player.setPosition)
            controls.addWidget(self.position_slider, 1)
            self.time_label = QLabel("0:00")
            self.time_label.setObjectName("Muted")
            controls.addWidget(self.time_label)
            root.addLayout(controls)

            self.player.positionChanged.connect(self._position_changed)
            self.player.durationChanged.connect(self._duration_changed)
            self.player.errorOccurred.connect(self._error_occurred)
            self.player.playbackStateChanged.connect(self._state_changed)

            effects = QFrame()
            effects.setObjectName("Card")
            effects_grid = QGridLayout(effects)
            effects_grid.setContentsMargins(12, 10, 12, 10)
            effects_grid.setSpacing(8)

            self.speed_combo = WheelSafeComboBox()
            add_effect_presets(
                self.speed_combo, SPEED_PRESETS, "Velocidade na pré-visualização"
            )
            self.pitch_combo = WheelSafeComboBox()
            add_pitch_presets(self.pitch_combo, "Tom na pré-visualização")
            self.volume_combo = WheelSafeComboBox()
            add_effect_presets(
                self.volume_combo, VOLUME_PRESETS, "Volume na pré-visualização"
            )

            self.effect_status = QLabel("Efeitos seguem as Configurações.")
            self.effect_status.setObjectName("Muted")
            self.effect_status.setWordWrap(True)
            self.effects_summary = QLabel("Nenhum efeito ativo")
            self.effects_summary.setWordWrap(True)
            self.chain_label = QLabel("")
            self.chain_label.setObjectName("MonoBlock")
            self.chain_label.setWordWrap(True)
            self.chain_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.chain_label.hide()

            effects_grid.addWidget(QLabel("Velocidade"), 0, 0)
            effects_grid.addWidget(self.speed_combo, 1, 0)
            effects_grid.addWidget(QLabel("Tom"), 0, 1)
            effects_grid.addWidget(self.pitch_combo, 1, 1)
            effects_grid.addWidget(QLabel("Volume"), 0, 2)
            effects_grid.addWidget(self.volume_combo, 1, 2)
            effects_grid.addWidget(self.effects_summary, 2, 0, 1, 3)
            effects_grid.addWidget(self.chain_label, 3, 0, 1, 3)
            effects_grid.addWidget(self.effect_status, 4, 0, 1, 3)
            root.addWidget(effects)

            self.speed_combo.currentIndexChanged.connect(self._effect_changed)
            self.pitch_combo.currentIndexChanged.connect(self._effect_changed)
            self.volume_combo.currentIndexChanged.connect(self._effect_changed)
        else:
            placeholder = QLabel(
                "A pré-visualização requer o módulo PySide6.QtMultimediaWidgets."
            )
            placeholder.setObjectName("Muted")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(240)
            root.addWidget(placeholder, 1)
            self.player = None
            self.audio_output = None
            self.play_button = None
            self.compare_button = None
            self.speed_combo = WheelSafeComboBox()
            self.pitch_combo = WheelSafeComboBox()
            self.volume_combo = WheelSafeComboBox()
            self.effect_status = QLabel()
            self.effects_summary = QLabel()
            self.chain_label = QLabel()

        footer = QHBoxLayout()
        footer.addStretch()
        close = PrimaryButton("FECHAR", icon_name="cancel")
        close.setAccessibleName("Fechar pré-visualização")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        root.addLayout(footer)

    def load_source(self, source: PreviewSource) -> None:
        """Load a resolved :class:`PreviewSource` (local or streamed)."""
        self._source = source
        self._has_audio = source.has_audio if source.has_audio is not None else True
        self._merged = source.needs_merge
        if source.duration and source.duration > 0:
            self.preview_duration = max(1.0, min(float(source.duration), 12.0))
        self.load(source.url)

    def load(self, preview_url: str) -> None:
        if not _HAS_MULTIMEDIA or self.player is None:
            return
        self._source_url = preview_url
        if not self._merged:
            self._play_stream("Carregando stream…")
        self._effect_changed()

    def apply_values(self, speed: float, pitch: float, volume: float) -> None:
        if not _HAS_MULTIMEDIA:
            return
        for combo, value in (
            (self.speed_combo, speed),
            (self.pitch_combo, pitch),
            (self.volume_combo, volume),
        ):
            combo.blockSignals(True)
            select_effect_preset(combo, value)
            combo.blockSignals(False)
        self._effect_changed()

    def _current_effects(self) -> AudioEffects:
        return AudioEffects(
            speed=combo_effect_value(self.speed_combo),
            pitch=combo_effect_value(self.pitch_combo),
            volume=combo_effect_value(self.volume_combo),
        )

    @_guarded
    def _play_stream(self, status: str) -> None:
        if self.player is None or not self._source_url or not _HAS_MULTIMEDIA:
            return
        self._listening_original = True
        self.player.setSource(QUrl(self._source_url))
        self.player.setPosition(0)
        self.player.play()
        self._set_subtitle(status)
        self._set_status(status)

    @_guarded
    def _effect_changed(self) -> None:
        if not _HAS_MULTIMEDIA or self.player is None or not self._source_url:
            return
        effects = self._current_effects()
        self._listening_original = False
        self._apply_volume_live()
        self._update_effect_panel(effects)
        if self.audio_effects is not None:
            self.audio_effects.set_effects(effects)
        if self._merged:
            if self.ffmpeg is None or not self.ffmpeg.available:
                self._set_status(
                    "Este stream usa áudio e vídeo separados; o componente FFmpeg "
                    "é necessário para montar a pré-visualização."
                )
                return
            self._pending_render = True
            self._set_subtitle("Preparando a prévia (áudio e vídeo separados)…")
            self._set_status("Montando a pré-visualização com o FFmpeg…")
            self._debounce.start()
            return
        if not self._has_audio:
            self._cancel_render()
            self._play_stream(
                "Esta mídia não contém áudio — os efeitos serão aplicados apenas ao "
                "arquivo final baixado."
            )
            return
        if effects.is_identity:
            self._cancel_render()
            self._play_stream("Fonte original — sem alterações.")
            return
        if self.ffmpeg is None or not self.ffmpeg.available:
            self._set_status(
                "Estes efeitos não podem ser pré-visualizados ao vivo sem o componente "
                f"FFmpeg: {effects.summary()}. O volume segue em tempo real."
            )
            return
        self._pending_render = True
        self._set_subtitle(f"Preparando prévia com {effects.summary()}…")
        self._set_status("Renderizando a prévia a partir do ponto atual…")
        self._debounce.start()

    def _update_effect_panel(self, effects: AudioEffects) -> None:
        if self.effects_summary is None or self.chain_label is None:
            return
        active = effects.active_effect_names()
        if active:
            self.effects_summary.setText("  •  ".join(active))
        else:
            self.effects_summary.setText("Nenhum efeito ativo")
        chain = effects.filter_chain()
        if chain and self.ffmpeg is not None and self.ffmpeg.available:
            self.chain_label.setText(f"-af: {chain}")
            self.chain_label.show()
        else:
            self.chain_label.setText("")
            self.chain_label.hide()

    def _apply_volume_live(self) -> None:
        if self.audio_output is None:
            return
        value = combo_effect_value(self.volume_combo)
        self.audio_output.setVolume(max(0.0, min(1.0, value)))

    def _cancel_render(self) -> None:
        self._debounce.stop()
        self._render_seq += 1
        self._pending_render = False
        self._listening_original = False
        self._replace_local(None)
        self._set_compare_enabled(False)

    @_guarded
    def _start_render(self) -> None:
        if not self._pending_render or not self._source_url:
            return
        effects = self._current_effects()
        chain = effects.filter_chain()
        if chain is None and not self._merged:
            self._cancel_render()
            return
        if chain is None:
            chain = ""
        self._render_seq += 1
        seq = self._render_seq
        start_time, window = self._current_window()
        output = Path(gettempdir()) / f"mediadown_preview_{uuid.uuid4().hex}.mkv"
        source = self._source
        worker = PreviewRenderWorker(
            self.ffmpeg, self._source_url, output, chain, window, start_time,
            video_url=source.video_url if source else None,
            audio_url=source.audio_url if source else None,
            headers=source.headers if source else None,
        )
        worker.signals.completed.connect(
            lambda path: self._render_ready(seq, Path(path))
        )
        worker.signals.failed.connect(
            lambda message: self._render_failed(seq, message)
        )
        self._render_workers[seq] = worker
        self._render_pool.start(worker)
        summary = effects.summary()
        self._set_subtitle(f"Renderizando prévia ({summary})…")

    def _current_window(self) -> tuple[float, float]:
        """Return ``(start_time, duration)`` around the position being listened to.

        Renders the window right before the current playback position so the
        effect is heard on the exact segment the user is on (near real-time).
        Falls back to the stream start when the position/duration is unknown.
        """
        if not _HAS_MULTIMEDIA or self.player is None:
            return 0.0, self.preview_duration
        try:
            duration_ms = self.player.duration()
            position_ms = self.player.position()
        except Exception:  # noqa: BLE001 - degrade on any media-service quirk
            return 0.0, self.preview_duration
        if duration_ms <= 0 or position_ms < 800:
            return 0.0, self.preview_duration
        total = duration_ms / 1000.0
        window = max(2.0, min(self.preview_duration, total))
        cursor = max(0.0, min(total - 0.5, position_ms / 1000.0))
        start = max(0.0, cursor - 0.5)
        if start + window > total:
            start = max(0.0, total - window)
        return start, window

    @_guarded
    def _render_ready(self, seq: int, path: Path) -> None:
        self._render_workers.pop(seq, None)
        if seq != self._render_seq:
            self._remove_file(path)
            return
        self._pending_render = False
        self._listening_original = False
        self._replace_local(path)
        if self.player is not None and _HAS_MULTIMEDIA:
            self.audio_output.setVolume(1.0)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.setPosition(0)
            self.player.play()
        self._set_compare_enabled(not self._merged)
        summary = self._current_effects().summary()
        if self._merged:
            self._set_subtitle(f"Prévia pronta ({summary}).")
            self._set_status("Prévia montada pelo FFmpeg (áudio e vídeo separados) tocando.")
        else:
            self._set_subtitle(f"Prévia pronta com {summary}.")
            self._set_status(
                "Prévia com efeitos tocando. Use “Comparar com original” para ouvir a diferença."
            )

    @_guarded
    def _render_failed(self, seq: int, message: str) -> None:
        self._render_workers.pop(seq, None)
        if seq != self._render_seq:
            return
        self._pending_render = False
        self._set_compare_enabled(False)
        if self._merged:
            self._set_status(
                "Não foi possível montar a prévia deste stream (áudio e vídeo "
                "separados). Baixe o arquivo para conferir o resultado."
            )
            return
        self._set_status(
            "Não foi possível gerar a prévia com efeitos neste stream. "
            "O áudio original continua tocando; baixe o arquivo para conferir o resultado."
        )

    @_guarded
    def _toggle_compare(self) -> None:
        if self.player is None or self.compare_button is None or not _HAS_MULTIMEDIA:
            return
        if self._local_path is None or self._current_effects().is_identity:
            return
        if not self._listening_original:
            self._listening_original = True
            self.player.setSource(QUrl(self._source_url))
            self.player.setPosition(0)
            self.player.play()
            self.compare_button.setText("Ouvir com efeitos")
            set_button_icon(self.compare_button, "retry")
            self._set_subtitle("Reproduzindo o ORIGINAL — sem efeitos.")
            self._set_status("Compare com a prévia: ouça o áudio original sem alterações.")
        else:
            self._listening_original = False
            self.player.setSource(QUrl.fromLocalFile(str(self._local_path)))
            self.player.setPosition(0)
            self.player.play()
            self.compare_button.setText("Comparar com original")
            set_button_icon(self.compare_button, "retry")
            self._set_subtitle(f"Reproduzindo a prévia com {self._current_effects().summary()}.")
            self._set_status("Prévia com efeitos aplicada pelo FFmpeg.")

    def _set_compare_enabled(self, enabled: bool) -> None:
        if self.compare_button is None:
            return
        self.compare_button.setEnabled(enabled)
        if enabled:
            self.compare_button.setText("Comparar com original")
            set_button_icon(self.compare_button, "retry")

    def _replace_local(self, path: Path | None) -> None:
        if self._local_path is not None:
            self._remove_file(self._local_path)
        self._local_path = path

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @_guarded
    def _toggle_play(self) -> None:
        if self.player is None or self.play_button is None or not _HAS_MULTIMEDIA:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    @_guarded
    def _state_changed(self, state) -> None:
        if self.play_button is None:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("Pausar")
            set_button_icon(self.play_button, "pause")
        else:
            self.play_button.setText("Iniciar")
            set_button_icon(self.play_button, "play")

    @_guarded
    def _position_changed(self, position: int) -> None:
        if self.position_slider is None or self.position_slider.isSliderDown():
            return
        self.position_slider.setValue(position)
        self.time_label.setText(_format_ms(position))

    @_guarded
    def _duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self.time_label.setText(_format_ms(duration))

    @_guarded
    def _error_occurred(self, error, message: str = "") -> None:
        detail = message or str(error)
        if not detail:
            detail = "falha desconhecida na reprodução"
        self._set_status(f"Erro ao reproduzir ({detail}). Tentando manter a fonte original.")
        if self._source_url and not self._listening_original and _HAS_MULTIMEDIA:
            try:
                self.player.setSource(QUrl(self._source_url))
                self.player.play()
            except Exception:  # noqa: BLE001 - best effort fallback
                pass

    def _set_status(self, message: str) -> None:
        self.effect_status.setText(message)
        self.effect_status.setAccessibleDescription(message)

    def _set_subtitle(self, message: str) -> None:
        self.subtitle.setText(message)

    def closeEvent(self, event) -> None:
        self._render_seq += 1
        self._debounce.stop()
        self._pending_render = False
        self._render_workers.clear()
        if self.player is not None and _HAS_MULTIMEDIA:
            self.player.stop()
            self.player.setSource(QUrl())
        self._replace_local(None)
        super().closeEvent(event)


def _format_ms(ms: int) -> str:
    total_sec = max(0, ms) // 1000
    minutes, seconds = divmod(total_sec, 60)
    return f"{minutes}:{seconds:02d}"