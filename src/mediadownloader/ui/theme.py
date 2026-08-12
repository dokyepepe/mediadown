"""Central Qt stylesheet for the compact, touch-friendly visual language."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


LIGHT = {
    "bg": "#F5F6F7", "card": "#FFFFFF", "text": "#252525", "muted": "#666666",
    "primary": "#257349", "primary_hover": "#1D603C", "action_fill": "#257349",
    "action_hover": "#1D603C", "border": "#DADDE1", "danger": "#A92E2E",
    "warning": "#79500C", "selection": "#DDEFE5", "placeholder": "#61676C",
    "disabled": "#767C81", "highlight_text": "#FFFFFF",
    "status_good_bg": "#E3F4EA", "status_good": "#217346",
    "status_error_bg": "#FBE9E9", "status_error": "#A92E2E",
    "status_neutral_bg": "#ECEEEF", "status_neutral": "#60656A",
    "status_wait_bg": "#FFF3DB", "status_wait": "#8A5A0A",
}
DARK = {
    "bg": "#202224", "card": "#292C2F", "text": "#F2F2F2", "muted": "#B3B6B9",
    "primary": "#79D5A1", "primary_hover": "#94E3B5", "action_fill": "#2B7951",
    "action_hover": "#236541", "border": "#4B5055", "danger": "#FFAAAA",
    "warning": "#F2CD7D", "selection": "#193B2A", "placeholder": "#AAB2B8",
    "disabled": "#92999F", "highlight_text": "#FFFFFF",
    "status_good_bg": "#244A35", "status_good": "#8ED5AB",
    "status_error_bg": "#522D2D", "status_error": "#FFAAAA",
    "status_neutral_bg": "#3A3E42", "status_neutral": "#CFD3D6",
    "status_wait_bg": "#504328", "status_wait": "#F2CD7D",
}


def apply_theme(app: QApplication, preference: str = "system") -> None:
    dark = preference == "dark" or (
        preference == "system"
        and QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    )
    c = DARK if dark else LIGHT
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["bg"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["card"],
        QPalette.ColorRole.AlternateBase: c["bg"],
        QPalette.ColorRole.ToolTipBase: c["card"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["card"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.BrightText: c["danger"],
        QPalette.ColorRole.Highlight: c["action_fill"],
        QPalette.ColorRole.HighlightedText: c["highlight_text"],
        QPalette.ColorRole.PlaceholderText: c["placeholder"],
        QPalette.ColorRole.Link: c["primary"],
        QPalette.ColorRole.LinkVisited: c["primary_hover"],
        QPalette.ColorRole.Light: c["card"],
        QPalette.ColorRole.Midlight: c["border"],
        QPalette.ColorRole.Mid: c["border"],
        QPalette.ColorRole.Dark: c["muted"],
        QPalette.ColorRole.Shadow: "#111111",
        QPalette.ColorRole.Accent: c["primary"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    app.setPalette(palette)
    # Clearing first also refreshes popup views already created by QComboBox.
    app.setStyleSheet("")
    app.setStyleSheet(f"""
        * {{ font-family: "Segoe UI"; font-size: 10pt; color: {c['text']}; }}
        QMainWindow, QDialog, QWidget#Page {{ background: {c['bg']}; }}
        QWidget#AppShell {{ background: {c['bg']}; }}
        QFrame#AppBar {{ background: {c['card']}; border-bottom: 1px solid {c['border']}; }}
        QFrame#BottomNav, QFrame#StickyFooter {{ background: {c['card']}; border-top: 1px solid {c['border']}; }}
        QLabel#AppVersion {{ color: {c['muted']}; font-size: 8.5pt; }}
        QLabel#PageTitle {{ font-size: 18pt; font-weight: 650; }}
        QLabel#PageSubtitle, QLabel#Muted {{ color: {c['muted']}; }}
        QLabel#SectionTitle {{ font-size: 12pt; font-weight: 600; }}
        QLabel#PageHeaderIcon {{ background: {c['selection']}; border: 1px solid {c['border']}; border-radius: 7px; }}
        QLabel#BrandName {{ color: {c['primary']}; font-size: 12pt; font-weight: 650; }}
        QLabel#HeroName {{ font-size: 20pt; font-weight: 650; }}
        QLabel#BrandCaption {{ color: {c['primary']}; font-size: 7pt; font-weight: 700; }}
        QLabel#BrandName, QLabel#Eyebrow, QLabel#Metric {{ color: {c['primary']}; }}
        QLabel#TintedIcon {{ background: {c['selection']}; border-radius: 6px; }}
        QLabel#WarningText {{ color: {c['warning']}; }}
        QLabel#ErrorText {{ color: {c['danger']}; }}
        QLabel#Notice {{ padding: 9px 11px; border-radius: 5px; border: 1px solid {c['border']}; }}
        QLabel#Notice[state="info"] {{ background: {c['selection']}; color: {c['primary']}; }}
        QLabel#Notice[state="error"] {{ background: {c['card']}; color: {c['danger']}; border-color: {c['danger']}; }}
        QLabel#Thumbnail {{ background: {c['bg']}; color: {c['muted']}; border-radius: 5px; }}
        QLabel#SpotifyLogo {{ background: #FFFFFF; border: 1px solid {c['border']}; border-radius: 5px; padding: 6px; }}
        QLabel#StatusBadge {{ border-radius: 4px; font-size: 9pt; font-weight: 600; }}
        QLabel#StatusBadge[status="completed"] {{ background: {c['status_good_bg']}; color: {c['status_good']}; }}
        QLabel#StatusBadge[status="error"] {{ background: {c['status_error_bg']}; color: {c['status_error']}; }}
        QLabel#StatusBadge[status="cancelled"] {{ background: {c['status_neutral_bg']}; color: {c['status_neutral']}; }}
        QLabel#StatusBadge[status="queued"] {{ background: {c['status_wait_bg']}; color: {c['status_wait']}; }}
        QLabel#StatusBadge[status="active"] {{ background: {c['selection']}; color: {c['primary']}; }}
        QFrame#Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 7px; }}
        QFrame#SoftCard {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 6px; }}
        QLineEdit, QComboBox, QSpinBox {{
            background: {c['card']}; border: 1px solid {c['border']}; border-radius: 5px;
            padding: 8px 10px; min-height: 24px; color: {c['text']}; selection-background-color: {c['action_fill']};
            selection-color: {c['highlight_text']};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {c['primary']}; padding: 7px 9px; }}
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ background: {c['bg']}; color: {c['disabled']}; }}
        QComboBox::drop-down {{ border: 0; width: 28px; }}
        QComboBox:on {{ border: 2px solid {c['primary']}; padding: 7px 9px; }}
        QComboBox QAbstractItemView {{
            background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']};
            outline: 0; padding: 4px; selection-background-color: {c['primary']};
            selection-color: {c['highlight_text']};
        }}
        QComboBox QAbstractItemView::item {{ min-height: 34px; padding: 5px 8px; border-radius: 3px; }}
        QComboBox QAbstractItemView::item:hover {{ background: {c['selection']}; color: {c['text']}; }}
        QComboBox QAbstractItemView::item:selected {{ background: {c['action_fill']}; color: {c['highlight_text']}; }}
        QComboBox QAbstractItemView::item:selected:active {{ background: {c['action_fill']}; color: {c['highlight_text']}; }}
        QPushButton {{ min-height: 26px; padding: 8px 14px; border-radius: 5px; border: 1px solid {c['border']}; background: {c['card']}; }}
        QPushButton:hover {{ background: {c['bg']}; border-color: {c['primary']}; }}
        QPushButton:pressed {{ background: {c['selection']}; border-color: {c['primary_hover']}; }}
        QPushButton:focus {{ border: 2px solid {c['primary']}; padding: 7px 13px; }}
        QPushButton:disabled {{ color: {c['disabled']}; background: {c['bg']}; }}
        QPushButton[role="primary"] {{ color: white; background: {c['action_fill']}; border-color: {c['action_fill']}; font-weight: 600; }}
        QPushButton[role="primary"]:hover, QPushButton[role="primary"]:pressed {{ background: {c['action_hover']}; }}
        QPushButton[role="danger"] {{ color: {c['danger']}; }}
        QPushButton[segment="true"]:checked {{ color: {c['primary']}; background: {c['selection']}; border-color: {c['primary']}; font-weight: 600; }}
        QToolButton#BottomNavButton {{
            border: 0; border-radius: 7px; background: transparent; padding: 5px 2px 4px 2px;
            font-size: 8pt; font-weight: 550;
        }}
        QToolButton#BottomNavButton:hover {{ background: {c['bg']}; }}
        QToolButton#BottomNavButton:focus {{ border: 2px solid {c['primary']}; padding: 3px 0 2px 0; }}
        QToolButton#BottomNavButton:pressed {{ background: {c['selection']}; }}
        QToolButton#BottomNavButton:checked {{ color: {c['primary']}; background: {c['selection']}; font-weight: 700; }}
        QProgressBar {{ border: 0; border-radius: 3px; background: {c['border']}; height: 7px; text-align: center; }}
        QProgressBar::chunk {{ border-radius: 3px; background: {c['primary']}; }}
        QScrollArea {{ border: 0; background: transparent; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QTableWidget {{ background: {c['card']}; border: 1px solid {c['border']}; gridline-color: {c['border']}; selection-background-color: {c['action_fill']}; selection-color: {c['highlight_text']}; }}
        QTableWidget:focus, QListWidget:focus {{ border: 2px solid {c['primary']}; }}
        QHeaderView::section {{ background: {c['bg']}; border: 0; border-bottom: 1px solid {c['border']}; padding: 9px; font-weight: 600; }}
        QListWidget {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 5px; }}
        QListWidget::item {{ min-height: 30px; padding: 6px; border-radius: 3px; }}
        QListWidget::item:selected {{ background: {c['action_fill']}; color: {c['highlight_text']}; }}
        QMenu {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
        QMenu::item {{ min-height: 28px; padding: 8px 28px 8px 10px; border-radius: 3px; }}
        QMenu::item:selected {{ background: {c['action_fill']}; color: {c['highlight_text']}; }}
        QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 8px; }}
        QToolTip {{ background: {c['card']}; border: 1px solid {c['border']}; color: {c['text']}; }}
        QCheckBox::indicator {{ width: 22px; height: 22px; }}
        QCheckBox {{ min-height: 34px; spacing: 8px; padding: 4px; border: 1px solid transparent; border-radius: 4px; }}
        QCheckBox:focus {{ border-color: {c['primary']}; background: {c['selection']}; }}
        QScrollBar:vertical {{ background: transparent; width: 16px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c['border']}; min-height: 28px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QLabel#Eyebrow {{ font-size: 9pt; font-weight: 700; }}
        QLabel#Metric {{ font-size: 18pt; font-weight: 600; }}
    """)
    from .icons import refresh_button_icons
    refresh_button_icons(app)
