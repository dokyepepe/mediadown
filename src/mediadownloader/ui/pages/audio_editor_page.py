"""Local audio editor: open a file, pick a segment on the real waveform,
apply fade in/out and export the selection with the current effect chain.

The trim/fade graph is always applied *after* the effect chain so the fades
are never re-normalized away by loudnorm.  All FFmpeg work (decode and export)
runs off the UI thread.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from tempfile import gettempdir

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QScrollArea, QVBoxLayout, QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False

from mediadownloader.core.audio_editor import (
    EDITABLE_FORMATS,
    audio_format_from_suffix,
    decode_pcm,
    envelope_from_pcm,
    estimate_duration_from_pcm,
    export_command,
    max_editor_seconds,
    preview_command,
    probe_duration,
)
from mediadownloader.core.audio_effects import AudioEffectsController
from mediadownloader.core.ffmpeg_manager import FFmpegManager

from ..icons import set_button_icon
from ..widgets import PageHeader, PrimaryButton, SecondaryButton
from ..widgets.waveform_view import WaveformView

_OPEN_FILTER = (
    "Arquivos de mídia (*.mp3 *.m4a *.aac *.opus *.flac *.wav *.ogg "
    "*.mp4 *.mkv *.webm *.mov *.avi);;Todos os arquivos (*)"
)
_SAVE_FILTER = (
    "Áudio (" + " ".join("*." + fmt for fmt in EDITABLE_FORMATS) + ");;"
    "Todos os arquivos (*)"
)


class _DecodeSignals(QObject):
    done = Signal(object, object)
    failed = Signal(str)


class _DecodeWorker(QRunnable):
    """Decode the waveform once and probe/count duration off the UI thread."""

    def __init__(self, ffmpeg: Path, ffprobe: Path | None, path: Path) -> None:
        super().__init__()
        self.sample_rate = 4000
        self.points = 1200
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.path = path
        self.signals = _DecodeSignals()

    @Slot()
    def run(self) -> None:
        try:
            pcm = decode_pcm(self.ffmpeg, self.path, sample_rate=self.sample_rate)
            duration = probe_duration(self.ffmpeg, self.ffprobe, self.path)
            if duration is None:
                duration = estimate_duration_from_pcm(len(pcm), self.sample_rate)
            peaks = envelope_from_pcm(pcm, points=self.points)
            self.signals.done.emit(duration, tuple(peaks))
        except Exception as error:
            self.signals.failed.emit(str(error))


class _RenderSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _RenderWorker(QRunnable):
    """Render a preview clip or an exported segment with the built command."""

    def __init__(self, args: list[str]) -> None:
        super().__init__()
        self.args = args
        self.signals = _RenderSignals()

    @Slot()
    def run(self) -> None:
        import subprocess

        from mediadownloader.core.audio_editor import CREATE_NO_WINDOW

        try:
            completed = subprocess.run(
                self.args,
                capture_output=True,
                timeout=600,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError as error:
            self.signals.failed.emit(f"Não foi possível executar o FFmpeg: {error}")
            return
        if completed.returncode != 0:
            tail = (completed.stderr or b"").decode("utf-8", "replace")[-300:]
            self.signals.failed.emit(
                f"Falha ao renderizar (código {completed.returncode}): {tail}"
            )
            return
        self.signals.done.emit(self.args[-1])


class AudioEditorPage(QWidget):
    """Waveform-based trim/fade editor wired to the shared effect controller."""

    def __init__(
        self,
        audio_effects: AudioEffectsController,
        ffmpeg: FFmpegManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.audio_effects = audio_effects
        self.ffmpeg = ffmpeg or FFmpegManager()
        self._path: Path | None = None
        self._duration: float | None = None
        self._media_ready = False
        self._decode_worker: _DecodeWorker | None = None
        self._render_worker: _RenderWorker | None = None
        self._preview_path: Path | None = None
        self.player: QMediaPlayer | None = None
        self.audio_output: QAudioOutput | None = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        if _HAS_MULTIMEDIA:
            self.audio_output = QAudioOutput(self)
            self.player = QMediaPlayer(self)
            self.player.setAudioOutput(self.audio_output)
        self._build_ui()
        self._sync_effects_summary()
        self.audio_effects.effects_changed.connect(self._sync_effects_summary)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("Page")
        root = QVBoxLayout(content)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(18)

        root.addWidget(PageHeader(
            "Editor de áudio",
            "Abra um arquivo local, desenhe o trecho na forma de onda, aplique "
            "fades e exporte. Os efeitos configurados na aba Áudio são aplicados "
            "automaticamente na prévia e no arquivo final.",
            "audio",
        ))

        file_card = QFrame()
        file_card.setObjectName("Card")
        file_layout = QHBoxLayout(file_card)
        file_layout.setContentsMargins(18, 14, 18, 14)
        file_layout.setSpacing(12)
        self.open_button = SecondaryButton("Abrir arquivo…")
        self.open_button.setAccessibleName("Abrir arquivo de áudio")
        set_button_icon(self.open_button, "folder")
        self.open_button.clicked.connect(self._open_media)
        file_layout.addWidget(self.open_button)
        self.file_label = QLabel("Nenhum arquivo selecionado")
        self.file_label.setObjectName("Muted")
        file_layout.addWidget(self.file_label, 1)
        self.duration_label = QLabel("")
        self.duration_label.setObjectName("Muted")
        file_layout.addWidget(self.duration_label)
        root.addWidget(file_card)

        render_card = QFrame()
        render_card.setObjectName("Card")
        render_layout = QVBoxLayout(render_card)
        render_layout.setContentsMargins(18, 14, 18, 14)
        render_layout.setSpacing(12)

        self.waveform = WaveformView(self)
        self.waveform.range_changed.connect(self._on_waveform_range)
        render_layout.addWidget(self.waveform)

        self.time_start = self._make_spin("Início do trecho em segundos")
        self.time_end = self._make_spin("Fim do trecho em segundos")
        self.fade_in = self._make_spin("Duração do fade in em segundos", step=0.1, decimals=1)
        self.fade_out = self._make_spin("Duração do fade out em segundos", step=0.1, decimals=1)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for column, (label, spin) in enumerate((
            ("Início", self.time_start),
            ("Fim", self.time_end),
            ("Fade in", self.fade_in),
            ("Fade out", self.fade_out),
        )):
            grid.addLayout(self._spin_row(label, spin), 0, column)
        render_layout.addLayout(grid)

        self.effects_label = QLabel("")
        self.effects_label.setObjectName("Muted")
        self.effects_label.setWordWrap(True)
        render_layout.addWidget(self.effects_label)

        self.render_notice = QLabel("")
        self.render_notice.setObjectName("Notice")
        self.render_notice.hide()
        render_layout.addWidget(self.render_notice)

        root.addWidget(render_card)

        action_card = QFrame()
        action_card.setObjectName("Card")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(18, 14, 18, 14)
        action_layout.setSpacing(12)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(10)
        self.preview_button = SecondaryButton("Pré-visualizar")
        self.preview_button.setAccessibleName("Pré-visualizar trecho editado")
        set_button_icon(self.preview_button, "audio")
        self.preview_button.clicked.connect(self._render_preview)
        preview_row.addWidget(self.preview_button)
        self.play_button = SecondaryButton("Tocar")
        self.play_button.setAccessibleName("Tocar ou pausar a prévia")
        set_button_icon(self.play_button, "play")
        self.play_button.clicked.connect(self._toggle_playback)
        preview_row.addWidget(self.play_button)
        self.preview_status = QLabel("")
        self.preview_status.setObjectName("Muted")
        preview_row.addWidget(self.preview_status, 1)
        action_layout.addLayout(preview_row)

        export_row = QHBoxLayout()
        export_row.setSpacing(10)
        self.export_button = PrimaryButton("Exportar…")
        self.export_button.setAccessibleName("Exportar trecho editado")
        set_button_icon(self.export_button, "downloads")
        self.export_button.clicked.connect(self._export_media)
        export_row.addWidget(self.export_button)
        self.export_status = QLabel("")
        self.export_status.setObjectName("Muted")
        export_row.addWidget(self.export_status, 1)
        action_layout.addLayout(export_row)

        root.addWidget(action_card)
        root.addStretch(1)
        outer.addWidget(scroll)
        scroll.setWidget(content)

        if not self.ffmpeg.available:
            self.open_button.setEnabled(False)
            self._set_notice(
                "O FFmpeg não está disponível nesta instalação — o editor de "
                "áudio ficará desativado.",
                error=True,
            )
        self._refresh_action_state()

    def _make_spin(self, tooltip: str, step: float = 1.0, decimals: int = 2) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 0.0)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setSuffix(" s")
        spin.setToolTip(tooltip)
        spin.setAccessibleName(tooltip)
        spin.setEnabled(False)
        spin.valueChanged.connect(self._time_inputs_changed)
        return spin

    def _spin_row(self, label: str, spin: QDoubleSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(spin)
        return row

    # ── Media loading ──────────────────────────────────────────────────────────

    def _open_media(self) -> None:
        if self._decode_worker is not None or self._render_worker is not None:
            return
        if not self.ffmpeg.available:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Abrir arquivo de mídia", "", _OPEN_FILTER)
        if not filename:
            return
        self._stop_playback()
        path = Path(filename)
        self._path = path
        self._duration = None
        self._media_ready = False
        self.file_label.setText(path.name)
        self.file_label.setObjectName("")
        self.file_label.style().unpolish(self.file_label)
        self.file_label.style().polish(self.file_label)
        self.duration_label.setText("Analisando áudio…")
        self.export_status.setText("")
        self.waveform.clear_media()
        self.waveform.setEnabled(False)
        for spin in (self.time_start, self.time_end, self.fade_in, self.fade_out):
            spin.setEnabled(False)
        self._set_notice("Decodificando a forma de onda…")
        self._refresh_action_state()

        ffprobe = getattr(self.ffmpeg, "ffprobe", None)
        worker = _DecodeWorker(self.ffmpeg.ffmpeg, ffprobe, path)
        worker.signals.done.connect(self._on_decode_done)
        worker.signals.failed.connect(self._on_decode_failed)
        self._decode_worker = worker
        self.pool.start(worker)

    def _on_decode_done(self, duration: float, peaks: object) -> None:
        self._decode_worker = None
        self._media_ready = True
        self._duration = float(duration) if duration is not None and duration > 0 else None
        personality = tuple(peaks) if isinstance(peaks, tuple) else ()
        max_seconds = max_editor_seconds(self._duration)
        end_default = self._duration if self._duration is not None else min(30.0, max_seconds)

        for spin in (self.time_start, self.time_end, self.fade_in, self.fade_out):
            spin.blockSignals(True)
        self.time_start.setRange(0.0, max(0.0, max_seconds - 0.1))
        self.time_end.setRange(0.0, max_seconds)
        self.fade_in.setRange(0.0, max_seconds)
        self.fade_out.setRange(0.0, max_seconds)
        self.time_start.setValue(0.0)
        self.time_end.setValue(min(end_default, max_seconds))
        self.fade_in.setValue(0.0)
        self.fade_out.setValue(0.0)
        for spin in (self.time_start, self.time_end, self.fade_in, self.fade_out):
            spin.setEnabled(True)
            spin.blockSignals(False)

        self.waveform.set_media(self._duration or 0.0, personality)
        self.waveform.setEnabled(True)

        if self._duration is not None:
            label = f"{self._duration / 60.0:.2f} min ({self._duration:.1f} s)"
        else:
            label = "duração desconhecida"
        self.duration_label.setText(label)
        self._set_notice(
            "Forma de onda pronta. Arraste os marcadores verde (início) e "
            "vermelho (fim) para selecionar o trecho.",
        )
        self._refresh_action_state()

    def _on_decode_failed(self, message: str) -> None:
        self._decode_worker = None
        self._media_ready = False
        self._set_notice(f"Não foi possível ler o arquivo: {message}", error=True)
        self.duration_label.setText("")
        self._refresh_action_state()

    def _on_waveform_range(self, start: float, end: float) -> None:
        self.time_start.blockSignals(True)
        self.time_end.blockSignals(True)
        self.time_start.setValue(start)
        self.time_end.setValue(end)
        self.time_start.blockSignals(False)
        self.time_end.blockSignals(False)

    def _time_inputs_changed(self) -> None:
        if self._duration is None:
            return
        start = max(0.0, min(self.time_start.value(), self._duration - 0.1))
        end = max(start + 0.1, min(self.time_end.value(), self._duration))
        self.waveform.set_range(start, end)

    # ── Rendering: preview and export ──────────────────────────────────────────

    def _render_preview(self) -> None:
        if self._path is None or not self._media_ready:
            return
        if self._decode_worker is not None or self._render_worker is not None:
            return
        preview_path = Path(gettempdir()) / f"mediadown-editor-{uuid.uuid4().hex}.m4a"
        args = preview_command(
            self.ffmpeg.ffmpeg,
            self._path,
            preview_path,
            start=self.time_start.value(),
            end=self.time_end.value(),
            fade_in=self.fade_in.value(),
            fade_out=self.fade_out.value(),
            effects=self.audio_effects.effects,
        )
        self.preview_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.preview_status.setText("Gerando prévia…")
        worker = _RenderWorker(args)
        worker.signals.done.connect(self._on_preview_ready)
        worker.signals.failed.connect(self._on_render_failed)
        self._render_worker = worker
        self.pool.start(worker)

    def _on_preview_ready(self, path: str) -> None:
        self._render_worker = None
        self._preview_path = Path(path)
        self.preview_status.setText("Prévia pronta.")
        if self.player is not None:
            self.player.setSource(QUrl.fromLocalFile(self._preview_path))
            self.player.play()
            self.play_button.setText("Pausar")
            self.play_button.setEnabled(True)
            set_button_icon(self.play_button, "pause")
        self._refresh_action_state()

    def _on_render_failed(self, message: str) -> None:
        self._render_worker = None
        self._set_notice(f"Falha ao renderizar: {message}", error=True)
        if self._preview_path is not None:
            self.preview_status.setText("Erro ao gerar a prévia.")
        else:
            self.export_status.setText("Falha na exportação.")
        self._refresh_action_state()

    def _toggle_playback(self) -> None:
        if self.player is None:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText("Tocar")
            set_button_icon(self.play_button, "play")
        else:
            self.player.play()
            self.play_button.setText("Pausar")
            set_button_icon(self.play_button, "pause")

    def _stop_playback(self) -> None:
        if self.player is not None:
            self.player.stop()
        self.play_button.setText("Tocar")
        self.play_button.setEnabled(False)
        set_button_icon(self.play_button, "play")

    def _export_media(self) -> None:
        if self._path is None or not self._media_ready:
            return
        if self._decode_worker is not None or self._render_worker is not None:
            return
        default_format = audio_format_from_suffix(self._path)
        default_name = self._path.with_suffix("").name + f"_editado.{default_format}"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar trecho editado", str(Path.home() / default_name), _SAVE_FILTER
        )
        if not filename:
            return
        output = Path(filename)
        output_format = audio_format_from_suffix(output)
        args = export_command(
            self.ffmpeg.ffmpeg,
            self._path,
            output,
            start=self.time_start.value(),
            end=self.time_end.value(),
            fade_in=self.fade_in.value(),
            fade_out=self.fade_out.value(),
            effects=self.audio_effects.effects,
            audio_format=output_format,
        )
        self.export_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.export_status.setText("Exportando…")
        worker = _RenderWorker(args)
        worker.signals.done.connect(self._on_export_done)
        worker.signals.failed.connect(self._on_render_failed)
        self._render_worker = worker
        self.pool.start(worker)

    def _on_export_done(self, path: str) -> None:
        self._render_worker = None
        self.export_status.setText(f"Exportado: {path}")
        self._set_notice("Exportação concluída com sucesso.")
        self._refresh_action_state()

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _sync_effects_summary(self, *_args: object) -> None:
        effects = self.audio_effects.effects
        chain = effects.filter_chain() if effects is not None else None
        if chain is None:
            self.effects_label.setText("Efeitos ativos: nenhum extra além do trecho/fades.")
        else:
            shortened = chain if len(chain) <= 96 else chain[:96] + "…"
            self.effects_label.setText(f"Efeitos da aba Áudio aplicados: {shortened}")

    def _refresh_action_state(self) -> None:
        ready = (
            self._path is not None
            and self._media_ready
            and self._decode_worker is None
            and self._render_worker is None
        )
        self.preview_button.setEnabled(ready)
        self.export_button.setEnabled(ready)

    def _set_notice(self, message: str, error: bool = False) -> None:
        self.render_notice.setProperty("state", "error" if error else "info")
        self.render_notice.style().unpolish(self.render_notice)
        self.render_notice.style().polish(self.render_notice)
        self.render_notice.setText(message)
        self.render_notice.setAccessibleDescription(message)
        self.render_notice.show()

    def stop_preview(self) -> None:
        if self.player is not None:
            self.player.stop()