"""Regression tests for theme contrast and input interaction safeguards."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPalette, QWheelEvent
from PySide6.QtWidgets import QApplication

from mediadownloader.ui.theme import DARK, LIGHT, apply_theme
from mediadownloader.ui.widgets import WheelSafeComboBox, WheelSafeSpinBox


def _wheel_event(delta: int = 120) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_mouse_wheel_does_not_change_combo_selection(qtbot) -> None:
    combo = WheelSafeComboBox()
    combo.addItems(["Um", "Dois", "Três"])
    combo.setCurrentIndex(1)
    qtbot.addWidget(combo)

    QApplication.sendEvent(combo, _wheel_event())

    assert combo.currentIndex() == 1


def test_mouse_wheel_does_not_change_spin_value(qtbot) -> None:
    spin = WheelSafeSpinBox()
    spin.setRange(1, 5)
    spin.setValue(3)
    qtbot.addWidget(spin)

    QApplication.sendEvent(spin, _wheel_event(-120))

    assert spin.value() == 3


def test_theme_switch_updates_existing_combo_selection_palette(qapp, qtbot) -> None:
    combo = WheelSafeComboBox()
    combo.addItems(["Sistema", "Claro", "Escuro"])
    qtbot.addWidget(combo)

    apply_theme(qapp, "dark")
    dark_palette = qapp.palette()
    assert dark_palette.color(QPalette.ColorRole.Base).name() == DARK["card"].lower()
    assert dark_palette.color(QPalette.ColorRole.Text).name() == DARK["text"].lower()
    assert dark_palette.color(QPalette.ColorRole.Highlight).name() == DARK["primary"].lower()
    assert dark_palette.color(QPalette.ColorRole.HighlightedText).name() == "#ffffff"
    assert combo.view().palette().color(QPalette.ColorRole.Base).name() == DARK["card"].lower()
    assert combo.view().palette().color(QPalette.ColorRole.Highlight).name() == DARK["primary"].lower()

    apply_theme(qapp, "light")
    light_palette = qapp.palette()
    assert light_palette.color(QPalette.ColorRole.Base).name() == LIGHT["card"].lower()
    assert light_palette.color(QPalette.ColorRole.Text).name() == LIGHT["text"].lower()
    assert light_palette.color(QPalette.ColorRole.Highlight).name() == LIGHT["primary"].lower()
    assert light_palette.color(QPalette.ColorRole.HighlightedText).name() == "#ffffff"
    assert combo.view().palette().color(QPalette.ColorRole.Base).name() == LIGHT["card"].lower()
    assert combo.view().palette().color(QPalette.ColorRole.Highlight).name() == LIGHT["primary"].lower()
