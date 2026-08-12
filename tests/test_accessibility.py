"""Regression tests for theme contrast and input interaction safeguards."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPalette, QWheelEvent
from PySide6.QtWidgets import QApplication

from mediadownloader.ui.theme import DARK, LIGHT, apply_theme
from mediadownloader.ui.widgets import ThemedIconLabel, WheelSafeComboBox, WheelSafeSpinBox


def _relative_luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


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
    assert dark_palette.color(QPalette.ColorRole.Highlight).name() == DARK["action_fill"].lower()
    assert dark_palette.color(QPalette.ColorRole.HighlightedText).name() == "#ffffff"
    assert combo.view().palette().color(QPalette.ColorRole.Base).name() == DARK["card"].lower()
    assert combo.view().palette().color(QPalette.ColorRole.Highlight).name() == DARK["primary"].lower()

    apply_theme(qapp, "light")
    light_palette = qapp.palette()
    assert light_palette.color(QPalette.ColorRole.Base).name() == LIGHT["card"].lower()
    assert light_palette.color(QPalette.ColorRole.Text).name() == LIGHT["text"].lower()
    assert light_palette.color(QPalette.ColorRole.Highlight).name() == LIGHT["action_fill"].lower()
    assert light_palette.color(QPalette.ColorRole.HighlightedText).name() == "#ffffff"
    assert combo.view().palette().color(QPalette.ColorRole.Base).name() == LIGHT["card"].lower()
    assert combo.view().palette().color(QPalette.ColorRole.Highlight).name() == LIGHT["primary"].lower()


def test_interactive_theme_colors_meet_normal_text_contrast() -> None:
    for theme in (LIGHT, DARK):
        assert _contrast(theme["action_fill"], theme["highlight_text"]) >= 4.5
        assert _contrast(theme["primary"], theme["selection"]) >= 4.5
        assert _contrast(theme["placeholder"], theme["card"]) >= 4.5


def test_themed_icon_refreshes_after_theme_change(qapp, qtbot) -> None:
    apply_theme(qapp, "light")
    icon = ThemedIconLabel("home", 22)
    qtbot.addWidget(icon)
    icon.show()
    light_key = icon.pixmap().cacheKey()

    apply_theme(qapp, "dark")
    qapp.processEvents()

    assert icon.palette().color(QPalette.ColorRole.Link).name() == DARK["primary"].lower()
    assert icon.pixmap().cacheKey() != light_key
