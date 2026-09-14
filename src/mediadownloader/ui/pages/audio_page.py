"""Dedicated audio studio: fine-grained pitch, speed and volume controls.

This page is the deep counterpart of the quick combos on the home page.  It
shares a single :class:`AudioEffectsController` with the rest of the app, so
everything here is applied identically to the download preview and the final
file.  It also plays local test tones: pitch and volume comparisons are
generated in pure Python (exact), while speed and full-chain comparisons are
rendered through the bundled FFmpeg with the exact ``-af`` chain.

A unified media-preview card reuses the same pipeline as the home page: paste
any URL, the effect set above is applied live (volume responds instantly) and
tempo/pitch are rendered by FFmpeg from the exact segment being played.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlparse

from PySide6.QtCore import QThreadPool, QUrl, Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSlider,
    QVBoxLayout, QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False

from mediadownloader.core.audio_effects import (
    PITCH_SEMITONES, REFERENCE_TONE_FREQUENCY_HZ, SPEED_PRESETS,
    TONE_SAMPLE_RATE, VOLUME_PRESETS, AudioEffects, AudioEffectsController,
    effects_explanations, ratio_to_semitones, render_tone_wav, semitones_note_name,
    semitones_to_ratio, sine_wave_pcm, write_wav_file,
)
from mediadownloader.core.downloader import DownloadEngine
from mediadownloader.core.ffmpeg_manager import FFmpegManager
from mediadownloader.core.workers import PreviewRenderWorker, PreviewWorker
from mediadownloader.models import PreviewSource
from mediadownloader.utils.errors import FriendlyError
from mediadownloader.utils.validators import validate_url

from ..icons import set_button_icon
from ..widgets import (
    PageHeader, PrimaryButton, SecondaryButton, VideoPreviewDialog,
    WheelSafeComboBox,
)


def _select_by_float(combo: WheelSafeComboBox, target: float) -> None:
    for index in range(combo.count()):
        if abs(float(combo.itemData(index)) - target) < 1e-4:
            combo.setCurrentIndex(index)
            return


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


class AudioPage(QWidget):
    """Vanilla audio effects studio backed by a shared controller."""

    def __init__(
        self,
        audio_effects: AudioEffectsController,
        ffmpeg: FFmpegManager | None = None,
        engine: DownloadEngine | None = None,
        settings=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.audio_effects = audio_effects
        self.ffmpeg = ffmpeg or FFmpegManager()
        self.engine = engine
        self.settings = settings
        self._melody_path: Path | None = None
        self._effects_path: Path | None = None
        self._rendered_chain: str | None = None
        self._render_pool = QThreadPool(self)
        self._render_pool.setMaxThreadCount(1)
        self._render_seq = 0
        self._render_workers: dict[int, PreviewRenderWorker] = {}
        self._mode: str | None = None
        self._queue_paths: list[Path] = []
        self._queue_statuses: list[str] = []
        self._queue_index = 0
        self.player: QMediaPlayer | None = None
        self.pool = QThreadPool.globalInstance()
        self._preview_worker: PreviewWorker | None = None
        self._preview_dialog: VideoPreviewDialog | None = None
        self._build_ui()
        self._sync_from_controller()
        self.audio_effects.effects_changed.connect(self._sync_from_controller)
        self._set_ab_message("Use os controles acima e então toque um arpejo de referência.")

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
            "Áudio",
            "Ajuste fino de tom, velocidade e volume — aplicado na prévia e no "
            "arquivo final, sempre em sincronia com o resto do aplicativo.",
            "audio",
        ))

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        summary_card.setProperty("accent", "true")
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        summary_layout.setSpacing(14)
        self.summary_label = QLabel("Sem efeitos")
        self.summary_label.setObjectName("AudioSummary")
        self.summary_label.setWordWrap(True)
        self.summary_label.setAccessibleName("Efeitos de áudio ativos")
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("Muted")
        self.ffmpeg_status.setWordWrap(True)
        summary_layout.addWidget(self.summary_label, 1)
        summary_layout.addWidget(self.ffmpeg_status)
        root.addWidget(summary_card)

        self.canvas_card = QFrame()
        self.canvas_card.setObjectName("Card")
        canvas_layout = QVBoxLayout(self.canvas_card)
        canvas_layout.setContentsMargins(18, 14, 18, 14)
        canvas_layout.setSpacing(12)

        pitch_heading = self._card_heading(
            "Tom (pitch)",
            "Muda a tonalidade preservando a duração (referência: Lá 440 Hz).",
        )
        canvas_layout.addLayout(pitch_heading)
        pitch_row = QHBoxLayout()
        pitch_row.setSpacing(10)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-12, 12)
        self.pitch_slider.setPageStep(1)
        self.pitch_slider.setTickInterval(6)
        self.pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pitch_slider.setAccessibleName("Deslocamento de tom em semitons")
        self.pitch_value = QLabel("0 semitons")
        self.pitch_value.setObjectName("Metric")
        self.pitch_value.setMinimumWidth(150)
        self.pitch_note = QLabel(semitones_note_name(0))
        self.pitch_note.setObjectName("Muted")
        self.pitch_note.setMinimumWidth(150)
        self.pitch_combo = self._make_pitch_combo()
        pitch_readout = QVBoxLayout()
        pitch_readout.setSpacing(1)
        pitch_readout.addWidget(self.pitch_value)
        pitch_readout.addWidget(self.pitch_note)
        self.pitch_tone_button = SecondaryButton("Ouvir tom", icon_name="play")
        self.pitch_tone_button.setToolTip(
            "Toca Lá 440 Hz e depois a mesma nota com o deslocamento de tom atual."
        )
        self.pitch_tone_button.clicked.connect(self._play_pitch_pair)
        pitch_row.addWidget(self.pitch_slider, 1)
        pitch_row.addLayout(pitch_readout)
        pitch_row.addWidget(self.pitch_combo)
        pitch_row.addWidget(self.pitch_tone_button)
        canvas_layout.addLayout(pitch_row)

        speed_heading = self._card_heading(
            "Velocidade",
            "Tempo esticado ou comprimido com atempo, sem mudar o tom.",
        )
        canvas_layout.addLayout(speed_heading)
        speed_row = QHBoxLayout()
        speed_row.setSpacing(10)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setPageStep(5)
        self.speed_slider.setTickInterval(25)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setAccessibleName("Velocidade de reprodução")
        self.speed_value = QLabel("1,0x (normal)")
        self.speed_value.setObjectName("Metric")
        self.speed_value.setMinimumWidth(150)
        self.speed_combo = self._make_combo("Velocidade", SPEED_PRESETS)
        self.speed_tone_button = SecondaryButton("Ouvir velocidade", icon_name="play")
        self.speed_tone_button.setToolTip(
            "Exige o FFmpeg: gera um arpejo rápido/morto conforme a velocidade atual."
        )
        self.speed_tone_button.clicked.connect(self._compare)
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_value)
        speed_row.addWidget(self.speed_combo)
        speed_row.addWidget(self.speed_tone_button)
        canvas_layout.addLayout(speed_row)

        volume_heading = self._card_heading(
            "Volume",
            "Amplifica ou reduz o nível da saída final.",
        )
        canvas_layout.addLayout(volume_heading)
        volume_row = QHBoxLayout()
        volume_row.setSpacing(10)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(5, 200)
        self.volume_slider.setPageStep(5)
        self.volume_slider.setTickInterval(25)
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setAccessibleName("Volume da saída")
        self.volume_value = QLabel("100% do volume (normal)")
        self.volume_value.setObjectName("Metric")
        self.volume_value.setMinimumWidth(150)
        self.volume_combo = self._make_combo("Volume", VOLUME_PRESETS)
        self.volume_tone_button = SecondaryButton("Ouvir volume", icon_name="play")
        self.volume_tone_button.setToolTip(
            "Toca Lá 440 Hz em dois níveis: original e com o volume atual aplicado."
        )
        self.volume_tone_button.clicked.connect(self._play_volume_pair)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value)
        volume_row.addWidget(self.volume_combo)
        volume_row.addWidget(self.volume_tone_button)
        canvas_layout.addLayout(volume_row)
        root.addWidget(self.canvas_card)

        chain_card = QFrame()
        chain_card.setObjectName("Card")
        chain_layout = QVBoxLayout(chain_card)
        chain_layout.setContentsMargins(18, 14, 18, 14)
        chain_layout.setSpacing(8)
        chain_title = QLabel("Cadeia aplicada (FFmpeg -af)")
        chain_title.setObjectName("SectionTitle")
        self.chain_label = QLabel("Nenhum efeito ativo — o arquivo final sai como a fonte.")
        self.chain_label.setObjectName("MonoBlock")
        self.chain_label.setWordWrap(True)
        self.chain_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.explanations_label = QLabel()
        self.explanations_label.setObjectName("Muted")
        self.explanations_label.setWordWrap(True)
        chain_hint = QLabel(
            "Estes filtros são aplicados durante a conversão final e podem ser "
            "pré-visualizados na seção de comparação abaixo. Requer o componente FFmpeg."
        )
        chain_hint.setObjectName("Muted")
        chain_hint.setWordWrap(True)
        chain_layout.addWidget(chain_title)
        chain_layout.addWidget(self.chain_label)
        chain_layout.addWidget(self.explanations_label)
        chain_layout.addWidget(chain_hint)
        root.addWidget(chain_card)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 14, 18, 14)
        preview_layout.setSpacing(10)
        preview_title = QLabel("Pré-visualizar mídia com efeitos")
        preview_title.setObjectName("SectionTitle")
        preview_caption = QLabel(
            "Cole a URL de um vídeo ou áudio para ouvir, já com os efeitos acima, "
            "antes de baixar. O volume responde em tempo real; tom e velocidade são "
            "renderizados pelo FFmpeg a partir do trecho que você está ouvindo."
        )
        preview_caption.setObjectName("Muted")
        preview_caption.setWordWrap(True)
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)
        self.preview_url_input = QLineEdit()
        self.preview_url_input.setPlaceholderText("Cole a URL para pré-visualizar…")
        self.preview_url_input.setAccessibleName("URL para pré-visualizar")
        self.preview_url_input.returnPressed.connect(self._preview_media)
        self.paste_url_button = SecondaryButton("Colar", icon_name="paste")
        self.paste_url_button.setToolTip("Copia o endereço da área de transferência.")
        self.paste_url_button.clicked.connect(self._paste_url)
        self.preview_button = PrimaryButton("PRÉ-VISUALIZAR", icon_name="video")
        self.preview_button.setToolTip(
            "Resolve um stream reproduzível desta URL e abre a prévia com os efeitos atuais."
        )
        self.preview_button.clicked.connect(self._preview_media)
        preview_row.addWidget(self.preview_url_input, 1)
        preview_row.addWidget(self.paste_url_button)
        preview_row.addWidget(self.preview_button)
        self.preview_notice = QLabel()
        self.preview_notice.setObjectName("Notice")
        self.preview_notice.setProperty("state", "info")
        self.preview_notice.setWordWrap(True)
        self.preview_notice.hide()
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_caption)
        preview_layout.addLayout(preview_row)
        preview_layout.addWidget(self.preview_notice)
        root.addWidget(preview_card)

        ab_card = QFrame()
        ab_card.setObjectName("Card")
        ab_layout = QVBoxLayout(ab_card)
        ab_layout.setContentsMargins(18, 14, 18, 14)
        ab_layout.setSpacing(10)
        ab_title = QLabel("Comparação A/B")
        ab_title.setObjectName("SectionTitle")
        ab_caption = QLabel(
            "Um arpejo curto é gerado neste dispositivo. Compare a fonte original com "
            "o mesmo arpejo depois de passar pela cadeia de efeitos."
        )
        ab_caption.setObjectName("Muted")
        ab_caption.setWordWrap(True)
        ab_layout.addWidget(ab_title)
        ab_layout.addWidget(ab_caption)
        ab_actions = QHBoxLayout()
        ab_actions.setSpacing(8)
        self.ab_original_button = SecondaryButton("Ouvir original", icon_name="play")
        self.ab_original_button.setToolTip("Toca o arpejo de referência sem efeitos.")
        self.ab_original_button.clicked.connect(self._play_original)
        self.ab_effects_button = SecondaryButton("Ouvir com efeitos", icon_name="play")
        self.ab_effects_button.clicked.connect(lambda: self._request_effects("effects"))
        self.ab_compare_button = PrimaryButton("COMPARAR A/B", icon_name="retry")
        self.ab_compare_button.setToolTip(
            "Toca o arpejo original e depois o mesmo arpejo com os efeitos aplicados."
        )
        self.ab_compare_button.clicked.connect(self._compare)
        self.ab_stop_button = SecondaryButton("Parar", icon_name="cancel")
        self.ab_stop_button.clicked.connect(self._stop_playback)
        ab_actions.addWidget(self.ab_original_button)
        ab_actions.addWidget(self.ab_effects_button)
        ab_actions.addWidget(self.ab_compare_button)
        ab_actions.addWidget(self.ab_stop_button)
        ab_actions.addStretch()
        ab_layout.addLayout(ab_actions)
        self.ab_message = QLabel()
        self.ab_message.setObjectName("Notice")
        self.ab_message.setProperty("state", "info")
        self.ab_message.setWordWrap(True)
        self.ab_message.hide()
        ab_layout.addWidget(self.ab_message)
        root.addWidget(ab_card)

        self.reset_button = SecondaryButton("RESTAURAR PADRÃO (SEM EFEITOS)", icon_name="retry")
        self.reset_button.setToolTip("Zera tom, velocidade e volume para a fonte original.")
        self.reset_button.clicked.connect(self.audio_effects.reset)
        foot = QHBoxLayout()
        foot.addWidget(self.reset_button)
        self.persist_note = QLabel("Suas preferências de áudio ficam salvas neste computador.")
        self.persist_note.setObjectName("Muted")
        foot.addWidget(self.persist_note)
        foot.addStretch()
        root.addLayout(foot)
        root.addStretch()

        if _HAS_MULTIMEDIA:
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(1.0)
            self.player.setAudioOutput(self.audio_output)
            self.player.mediaStatusChanged.connect(self._media_status_changed)
            self.player.errorOccurred.connect(self._player_error)

        self.pitch_slider.valueChanged.connect(self._pitch_slider_changed)
        self.pitch_combo.currentIndexChanged.connect(self._pitch_combo_changed)
        self.speed_slider.valueChanged.connect(self._speed_slider_changed)
        self.speed_combo.currentIndexChanged.connect(self._speed_combo_changed)
        self.volume_slider.valueChanged.connect(self._volume_slider_changed)
        self.volume_combo.currentIndexChanged.connect(self._volume_combo_changed)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._refresh_availability()

    @staticmethod
    def _card_heading(title: str, note: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        note_label = QLabel(note)
        note_label.setObjectName("Muted")
        note_label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(note_label)
        return layout

    @staticmethod
    def _make_combo(accessible_name: str, presets: tuple[tuple[str, str], ...]) -> WheelSafeComboBox:
        combo = WheelSafeComboBox()
        combo.setAccessibleName(accessible_name)
        for value, label in presets:
            combo.addItem(label, value)
        return combo

    def _make_pitch_combo(self) -> WheelSafeComboBox:
        combo = WheelSafeComboBox()
        combo.setAccessibleName("Tom em semitons")
        for semitones in PITCH_SEMITONES:
            ratio = semitones_to_ratio(semitones)
            combo.addItem(f"{semitones:+d} semitons — " + (
                "mais grave" if semitones < 0 else "mais agudo"
            ), f"{ratio:.4f}")
        return combo

    # ── Controller sync ────────────────────────────────────────────────────────

    def _sync_from_controller(self, *_: object) -> None:
        effects = self.audio_effects.effects
        semitones = _clamp(round(effects.semitones), -12, 12)
        self.pitch_slider.blockSignals(True)
        self.pitch_slider.setValue(semitones)
        self.pitch_slider.blockSignals(False)
        self.pitch_combo.blockSignals(True)
        _select_by_float(self.pitch_combo, effects.pitch)
        self.pitch_combo.blockSignals(False)

        speed_pct = _clamp(round(effects.speed * 100), 50, 200)
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(speed_pct)
        self.speed_slider.blockSignals(False)
        self.speed_combo.blockSignals(True)
        _select_by_float(self.speed_combo, effects.speed)
        self.speed_combo.blockSignals(False)

        volume_pct = _clamp(round(effects.volume * 100), 5, 200)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume_pct)
        self.volume_slider.blockSignals(False)
        self.volume_combo.blockSignals(True)
        _select_by_float(self.volume_combo, effects.volume)
        self.volume_combo.blockSignals(False)

        self.pitch_value.setText(f"{semitones:+d} semitons")
        self.pitch_note.setText(semitones_note_name(semitones))
        self.speed_value.setText(effects.speed_description())
        self.volume_value.setText(effects.volume_description())
        self.summary_label.setText(effects.summary())

        chain = effects.filter_chain()
        if chain:
            self.chain_label.setText(f"-af: {chain}")
            self.chain_label.show()
            self.explanations_label.setText("\n".join(effects_explanations(effects)))
            self.explanations_label.show()
        else:
            self.chain_label.setText("Nenhum efeito ativo — o arquivo final sai como a fonte.")
            self.explanations_label.setText("")
            self.explanations_label.hide()
        if self._effects_path is not None and self._rendered_chain != chain:
            _remove_file(self._effects_path)
            self._effects_path = None
            self._rendered_chain = None

    def _refresh_availability(self) -> None:
        multimedia = _HAS_MULTIMEDIA and self.player is not None
        for button in (
            self.pitch_tone_button, self.volume_tone_button,
            self.ab_original_button, self.ab_stop_button,
        ):
            button.setEnabled(multimedia)
        ffmpeg_ready = multimedia and self.ffmpeg.available
        for button in (self.speed_tone_button, self.ab_effects_button, self.ab_compare_button):
            button.setEnabled(ffmpeg_ready)
        preview_ready = multimedia and self.engine is not None
        preview_clickable = multimedia and self.engine is not None
        self.preview_button.setEnabled(preview_ready)
        if preview_clickable:
            self.preview_notice.hide()
        elif not multimedia:
            self._set_preview_notice(
                "Reprodução indisponível nesta instalação (módulo multimídia ausente).",
                error=True,
            )
        else:
            self._set_preview_notice(
                "A pré-visualização está disponível a partir da aba Início nesta instalação.",
                error=True,
            )
        if self.ffmpeg.available:
            self.ffmpeg_status.setText(
                f"FFmpeg disponível ({self.ffmpeg.version()}) · cadeia pronta."
            )
        else:
            self.ffmpeg_status.setText(
                "Componente FFmpeg não encontrado — efeitos dependem dele. Ative em Configurações."
            )
        if not multimedia:
            for button in (self.pitch_tone_button, self.volume_tone_button):
                button.setToolTip("Reprodução indisponível neste ambiente.")
            self._set_ab_message("Módulo multimídia indisponível nesta instalação.", error=True)

    # ── Control handlers ───────────────────────────────────────────────────────

    def _pitch_slider_changed(self, value: int) -> None:
        self.pitch_combo.blockSignals(True)
        _select_by_float(self.pitch_combo, semitones_to_ratio(value))
        self.pitch_combo.blockSignals(False)
        self.audio_effects.set_pitch_semitones(value)

    def _pitch_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        ratio = float(self.pitch_combo.itemData(index))
        self.pitch_slider.blockSignals(True)
        self.pitch_slider.setValue(round(ratio_to_semitones(ratio)))
        self.pitch_slider.blockSignals(False)
        self.audio_effects.set_pitch(ratio)

    def _speed_slider_changed(self, value: int) -> None:
        speed = value / 100
        self.speed_combo.blockSignals(True)
        _select_by_float(self.speed_combo, speed)
        self.speed_combo.blockSignals(False)
        self.audio_effects.set_speed(speed)

    def _speed_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        speed = float(self.speed_combo.itemData(index))
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(round(speed * 100))
        self.speed_slider.blockSignals(False)
        self.audio_effects.set_speed(speed)

    def _volume_slider_changed(self, value: int) -> None:
        volume = value / 100
        self.volume_combo.blockSignals(True)
        _select_by_float(self.volume_combo, volume)
        self.volume_combo.blockSignals(False)
        self.audio_effects.set_volume(volume)

    def _volume_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        volume = float(self.volume_combo.itemData(index))
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(round(volume * 100))
        self.volume_slider.blockSignals(False)
        self.audio_effects.set_volume(volume)

    # ── Unified media preview ─────────────────────────────────────────────────

    def _paste_url(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.preview_url_input.setText(text)

    def _preview_media(self) -> None:
        url = self.preview_url_input.text().strip()
        valid, message = validate_url(url)
        if not valid:
            self._set_preview_notice(message, error=True)
            self.preview_url_input.setFocus()
            return
        if self.engine is None:
            self._set_preview_notice(
                "A pré-visualização de URL está disponível na aba Início nesta instalação.",
                error=True,
            )
            return
        if not _HAS_MULTIMEDIA or self.player is None:
            self._set_preview_notice(
                "Reprodução indisponível nesta instalação.", error=True,
            )
            return
        self.preview_button.setEnabled(False)
        self.preview_button.setText("PREPARANDO…")
        self._set_preview_notice("Resolvendo um stream reproduzível para a prévia…")
        proxy = ""
        cookies_file = ""
        cookies_browser = ""
        if self.settings is not None:
            proxy = (
                self.settings.get("network.proxy_url", "")
                if self.settings.get("network.proxy_type") != "none" else ""
            )
            cookies_file = (
                self.settings.get("cookies.file", "")
                if self.settings.get("cookies.source") == "file" else ""
            )
            cookies_browser = (
                self.settings.get("cookies.browser", "")
                if self.settings.get("cookies.source") == "browser" else ""
            )
        worker = PreviewWorker(self.engine, url, proxy, cookies_file, cookies_browser)
        worker.signals.completed.connect(
            lambda source: self._on_preview_ready(source, url)
        )
        worker.signals.failed.connect(self._on_preview_failed)
        self._preview_worker = worker
        self.pool.start(worker)

    def _on_preview_ready(self, source: PreviewSource, original_url: str) -> None:
        self._preview_worker = None
        self.preview_button.setEnabled(True)
        self.preview_button.setText("PRÉ-VISUALIZAR")
        try:
            host = (urlparse(original_url).netloc or "mídia").split("@")[-1]
        except ValueError:
            host = "mídia"
        effects = self.audio_effects.effects
        dialog = VideoPreviewDialog(
            host,
            ffmpeg=self.ffmpeg,
            audio_effects=self.audio_effects,
            speed=effects.speed,
            pitch=effects.pitch,
            volume=effects.volume,
            parent=self,
        )
        dialog.rejected.connect(lambda: self._clear_preview_dialog())
        dialog.accepted.connect(lambda: self._clear_preview_dialog())
        dialog.destroyed.connect(lambda: self._clear_preview_dialog())
        self._preview_dialog = dialog
        dialog.load_source(source)
        dialog.show()

    def _on_preview_failed(self, error: FriendlyError) -> None:
        self._preview_worker = None
        self.preview_button.setEnabled(True)
        self.preview_button.setText("PRÉ-VISUALIZAR")
        self._set_preview_notice(f"Não foi possível preparar a prévia: {error.message}", error=True)

    def _clear_preview_dialog(self, *_: object) -> None:
        if self._preview_dialog is None:
            return
        try:
            visible = self._preview_dialog.isVisible()
        except RuntimeError:  # C++ object already destroyed (destroyed signal)
            self._preview_dialog = None
            return
        if not visible:
            self._preview_dialog = None

    def _set_preview_notice(self, message: str, error: bool = False) -> None:
        self.preview_notice.setProperty("state", "error" if error else "info")
        self.preview_notice.style().unpolish(self.preview_notice)
        self.preview_notice.style().polish(self.preview_notice)
        self.preview_notice.setText(message)
        self.preview_notice.setAccessibleDescription(message)
        self.preview_notice.show()

    # ── Local tones (pure Python) ──────────────────────────────────────────────

    def _play_pitch_pair(self) -> None:
        if self.player is None:
            return
        effects = self.audio_effects.effects
        semitones = round(effects.semitones)
        original = render_tone_wav(
            self._tone_path("pitch_base"), REFERENCE_TONE_FREQUENCY_HZ
        )
        if semitones == 0:
            self._play_file(original, "Lá 440 Hz — tom original, sem alteração.")
            return
        shifted = render_tone_wav(
            self._tone_path("pitch_shifted"),
            REFERENCE_TONE_FREQUENCY_HZ * semitones_to_ratio(semitones),
        )
        self._play_sequence(
            [original, shifted],
            ["Lá 440 Hz (original)", f"{semitones_note_name(semitones)} — com deslocamento"],
        )

    def _play_volume_pair(self) -> None:
        if self.player is None:
            return
        effects = self.audio_effects.effects
        level = max(0.06, min(1.0, 0.5 * effects.volume))
        original = render_tone_wav(
            self._tone_path("volume_base"), REFERENCE_TONE_FREQUENCY_HZ, amplitude=0.5
        )
        scaled = render_tone_wav(
            self._tone_path("volume_scaled"), REFERENCE_TONE_FREQUENCY_HZ, amplitude=level
        )
        self._play_sequence(
            [original, scaled],
            ["Lá 440 Hz em 50% (original)", f"{effects.volume_description()} na saída"],
        )

    def _play_original(self) -> None:
        if self.player is None:
            return
        self._play_file(self._ensure_melody(), "Arpejo de referência — sem efeitos.")

    # ── FFmpeg-rendered chain comparison ───────────────────────────────────────

    def _request_effects(self, mode: str) -> None:
        if self.player is None:
            return
        if mode not in ("effects", "compare"):
            return
        effects = self.audio_effects.effects
        chain = effects.filter_chain()
        if chain is None:
            self._set_ab_message("Nenhum efeito ativo no momento — ative um controle acima.")
            return
        if not self.ffmpeg.available:
            self._set_ab_message(
                "O componente FFmpeg é necessário para esta comparação. Ative em Configurações.",
                error=True,
            )
            return
        if self._effects_path is not None and self._rendered_chain == chain:
            self._deliver(mode)
            return
        self._render_seq += 1
        seq = self._render_seq
        self._mode = mode
        output = Path(gettempdir()) / f"mediadown_audiofx_{uuid.uuid4().hex}.mkv"
        worker = PreviewRenderWorker(
            self.ffmpeg, str(self._ensure_melody()), output, chain, 8.0,
        )
        worker.signals.completed.connect(
            lambda path, current=seq: self._clip_ready(current, Path(path))
        )
        worker.signals.failed.connect(
            lambda message, current=seq: self._clip_failed(current, message)
        )
        self._render_workers[seq] = worker
        self._render_pool.start(worker)
        self._set_ab_message("Gerando o clipe com os efeitos atuais…")

    def _compare(self) -> None:
        self._request_effects("compare")

    def _clip_ready(self, seq: int, path: Path) -> None:
        self._render_workers.pop(seq, None)
        if seq != self._render_seq:
            _remove_file(path)
            return
        if self._effects_path is not None:
            _remove_file(self._effects_path)
        self._effects_path = path
        self._rendered_chain = self.audio_effects.effects.filter_chain()
        self.ab_effects_button.setEnabled(_HAS_MULTIMEDIA and self.ffmpeg.available)
        self.ab_compare_button.setEnabled(_HAS_MULTIMEDIA and self.ffmpeg.available)
        mode = self._mode
        self._mode = None
        if mode:
            self._deliver(mode)

    def _deliver(self, mode: str) -> None:
        if self.player is None or self._effects_path is None:
            return
        summary = self.audio_effects.effects.summary()
        if mode == "compare":
            self._set_ab_message("Ouvindo original e depois com efeitos.")
            self._play_sequence(
                [self._ensure_melody(), self._effects_path],
                ["Arpejo original (sem efeitos)", f"Arpejo com {summary}"],
            )
        else:
            self._set_ab_message("Ouvindo o arpejo com os efeitos aplicados.")
            self._play_file(self._effects_path, f"Arpejo com {summary}")

    def _clip_failed(self, seq: int, message: str) -> None:
        self._render_workers.pop(seq, None)
        if seq != self._render_seq:
            return
        self._mode = None
        self._set_ab_message(
            f"Não foi possível gerar o clipe: {message}", error=True,
        )

    # ── Playback helpers ───────────────────────────────────────────────────────

    def _tone_path(self, name: str) -> Path:
        return Path(gettempdir()) / f"mediadown_tone_{name}.wav"

    def _ensure_melody(self) -> Path:
        if self._melody_path is not None and self._melody_path.exists():
            return self._melody_path
        frames: list[bytes] = []
        for frequency in (523.25, 659.25, 783.99, 1046.50):
            frames.append(sine_wave_pcm(frequency, 0.32, amplitude=0.38))
            frames.append(b"\x00\x00" * (TONE_SAMPLE_RATE // 14))
        self._melody_path = write_wav_file(
            Path(gettempdir()) / f"mediadown_audiofx_{uuid.uuid4().hex}.wav",
            b"".join(frames),
        )
        return self._melody_path

    def _play_file(self, path: Path, status: str) -> None:
        self._play_sequence([path], [status])

    def _play_sequence(self, paths: list[Path], statuses: list[str]) -> None:
        if self.player is None or not paths:
            return
        self._queue_paths = list(paths)
        self._queue_statuses = list(statuses)
        self._queue_index = 0
        self._play_next_queued()

    def _play_next_queued(self) -> None:
        if self.player is None or self._queue_index >= len(self._queue_paths):
            self._queue_paths = []
            return
        path = self._queue_paths[self._queue_index]
        self._queue_index += 1
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.setPosition(0)
        if self._queue_index <= len(self._queue_statuses):
            self._set_ab_message(self._queue_statuses[self._queue_index - 1])
        self.player.play()

    def _stop_playback(self) -> None:
        self._queue_paths = []
        self._queue_index = 0
        if self.player is not None:
            self.player.stop()

    def _media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._play_next_queued()

    def _player_error(self, error, message: str = "") -> None:
        detail = message or str(error)
        if detail:
            self._set_ab_message(f"Erro ao reproduzir som de teste: {detail}", error=True)

    def _set_ab_message(self, message: str, error: bool = False) -> None:
        self.ab_message.setProperty("state", "error" if error else "info")
        self.ab_message.style().unpolish(self.ab_message)
        self.ab_message.style().polish(self.ab_message)
        self.ab_message.setText(message)
        self.ab_message.setAccessibleDescription(message)
        self.ab_message.show()