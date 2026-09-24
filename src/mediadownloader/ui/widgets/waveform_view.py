"""A theme-aware waveform strip with draggable in/out selection handles."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

_MARGIN = 10
_MIN_GAP_SECONDS = 0.1
_HANDLE_HIT_RADIUS = 8


class WaveformView(QWidget):
    """Paints a peak envelope and a selected segment bounded by two handles.

    The selection is editable by dragging the handles or clicking anywhere on
    the strip (which moves the nearest boundary). ``range_changed`` is emitted
    once the drag ends, with time values in seconds.
    """

    range_changed = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration = 0.0
        self._peaks: tuple[tuple[float, float], ...] = ()
        self._start = 0.0
        self._end = 0.0
        self._drag: str | None = None
        self._active: str = "end"
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Forma de onda com seleção de trecho para edição")
        self.setAccessibleDescription(
            "Setas esquerda/direita movem o marcador ativo, Shift amplia o passo, "
            "Início e Fim saltam para os extremos."
        )

    def clear_media(self) -> None:
        """Reset the waveform and selection (no media loaded)."""
        self._duration = 0.0
        self._peaks = ()
        self._start = 0.0
        self._end = 0.0
        self._drag = None
        self._active = "end"
        self.update()

    def set_media(self, duration: float, peaks: tuple[tuple[float, float], ...]) -> None:
        """Load a new waveform; the selection is reset to the whole media."""
        self._duration = max(0.0, float(duration))
        self._peaks = peaks
        self._start = 0.0
        self._end = self._duration
        self._drag = None
        self._active = "end"
        self.update()

    def duration(self) -> float:
        return self._duration

    def set_range(self, start: float, end: float) -> None:
        """Clamp and repaint bounds without emitting (used by time inputs)."""
        self._start, self._end = self._clamped_range(start, end)
        self.update()

    def has_media(self) -> bool:
        return self._duration > 0

    def _clamped_range(self, start: float, end: float) -> tuple[float, float]:
        if self._duration <= 0:
            return start, end
        start = min(max(0.0, float(start)), self._duration)
        end = min(max(0.0, float(end)), self._duration)
        if end - start < _MIN_GAP_SECONDS:
            if start <= self._end and self._start <= start:
                end = start + _MIN_GAP_SECONDS
            else:
                start = max(0.0, end - _MIN_GAP_SECONDS)
        return start, min(end, self._duration)

    def _plot_rect(self) -> tuple[int, int, int, int]:
        left = _MARGIN
        right = max(left + 1, self.width() - _MARGIN)
        return left, _MARGIN, right - left, max(1, self.height() - 2 * _MARGIN)

    def _x_for_time(self, seconds: float) -> int:
        left, top, width, height = self._plot_rect()
        if self._duration <= 0:
            return left
        ratio = min(max(seconds, 0.0), self._duration) / self._duration
        return left + round(ratio * width)

    def _time_for_x(self, x: int) -> float:
        left, top, width, height = self._plot_rect()
        if self._duration <= 0 or width <= 0:
            return 0.0
        ratio = min(max(x - left, 0), width) / width
        return self._duration * ratio

    def _nearest_handle(self, x: int) -> str | None:
        start_x = self._x_for_time(self._start)
        end_x = self._x_for_time(self._end)
        start_d = abs(x - start_x)
        end_d = abs(x - end_x)
        if start_d <= _HANDLE_HIT_RADIUS and start_d <= end_d:
            return "start"
        if end_d <= _HANDLE_HIT_RADIUS:
            return "end"
        return None

    def _move_boundary(self, which: str, seconds: float) -> None:
        if which == "start":
            self._start = min(max(0.0, seconds), self._end - _MIN_GAP_SECONDS)
        else:
            self._end = max(min(seconds, self._duration), self._start + _MIN_GAP_SECONDS)

    def _nudge_active(self, delta: float) -> None:
        target = self._start + delta if self._active == "start" else self._end + delta
        self._move_boundary(self._active, target)
        self.update()
        self.range_changed.emit(self._start, self._end)

    def mousePressEvent(self, event) -> None:
        if not self.has_media():
            return
        self._drag = self._nearest_handle(int(event.position().x()))
        if self._drag is None:
            seconds = self._time_for_x(int(event.position().x()))
            start_d = abs(seconds - self._start)
            end_d = abs(seconds - self._end)
            self._drag = "start" if start_d <= end_d else "end"
            self._move_boundary(self._drag, seconds)
        else:
            self._move_boundary(self._drag, self._time_for_x(int(event.position().x())))
        self._active = self._drag
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag is not None and self.has_media():
            self._move_boundary(self._drag, self._time_for_x(int(event.position().x())))
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag is not None:
            self._drag = None
            self.range_changed.emit(self._start, self._end)

    def keyPressEvent(self, event) -> None:
        if not self.has_media():
            event.ignore()
            return
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            step = 1.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.1
            delta = -step if key == Qt.Key.Key_Left else step
            self._nudge_active(delta)
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self._move_boundary(self._active, 0.0)
            self.update()
            self.range_changed.emit(self._start, self._end)
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self._move_boundary(self._active, self._duration)
            self.update()
            self.range_changed.emit(self._start, self._end)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        left, top, width, height = self._plot_rect()
        if width <= 0:
            return
        base = self.palette().color(self.palette().ColorRole.Base)
        painter.fillRect(self.rect(), base)

        if not self.has_media():
            painter.setPen(QPen(self.palette().color(self.palette().ColorRole.Mid), 1))
            painter.drawText(
                self.rect().adjusted(_MARGIN, 0, -_MARGIN, 0),
                Qt.AlignmentFlag.AlignCenter,
                "Abra um arquivo de áudio para ver a forma de onda",
            )
            return

        midpoint = top + height // 2
        painter.setPen(QPen(self.palette().color(self.palette().ColorRole.Mid), 1))
        painter.drawLine(left, midpoint, left + width, midpoint)

        peak_color = QColor(self.palette().color(self.palette().ColorRole.Text))
        peak_color.setAlpha(150)
        painter.setPen(QPen(peak_color, 1))
        peaks = self._peaks
        if peaks:
            n = len(peaks)
            step = width / n
            half = height / 2.0
            for index, (lo, hi) in enumerate(peaks):
                x = left + round(index * step)
                y1 = round(midpoint - hi * half)
                y2 = round(midpoint - lo * half)
                painter.drawLine(x, y1, x, max(y2, y1 + 1))

        start_x = self._x_for_time(self._start)
        end_x = self._x_for_time(self._end)
        highlight = QColor(self.palette().color(self.palette().ColorRole.Highlight))
        selection_fill = QColor(highlight)
        selection_fill.setAlpha(50)
        painter.fillRect(start_x, top, max(1, end_x - start_x), height, QBrush(selection_fill))
        painter.setPen(QPen(highlight, 2))
        painter.drawLine(start_x, top, start_x, top + height)
        painter.drawLine(end_x, top, end_x, top + height)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        danger = QColor(self.palette().color(self.palette().ColorRole.BrightText))
        for x, color in ((start_x, highlight), (end_x, danger)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(x - 4, top - 2, 8, 14, 3, 3)
        painter.end()