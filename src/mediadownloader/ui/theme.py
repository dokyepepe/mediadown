"""Central Qt stylesheet for the desktop visual language.

The application deliberately keeps all colour and density decisions here. Pages
only opt into semantic object names/properties, which keeps live theme switching
reliable and prevents one-off styles from drifting apart.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


LIGHT = {
    "bg": "#F3F7F5",
    "card": "#FFFFFF",
    "surface_alt": "#EDF4F0",
    "surface_hover": "#E7F0EB",
    "text": "#17251D",
    "muted": "#5D6B63",
    "primary": "#0D6841",
    "primary_hover": "#095735",
    "action_fill": "#0B6B40",
    "action_hover": "#085735",
    "border": "#D9E5DE",
    "border_strong": "#BFCFC6",
    "danger": "#A62F3B",
    "warning": "#83550A",
    "selection": "#DDF5E7",
    "placeholder": "#68756D",
    "disabled": "#78837D",
    "highlight_text": "#FFFFFF",
    "sidebar": "#10251B",
    "sidebar_hover": "#19392B",
    "sidebar_active": "#DDF5E7",
    "sidebar_text": "#EEF6F1",
    "sidebar_muted": "#9CB0A5",
    "hero_start": "#E7F8EE",
    "hero_end": "#F7FBF9",
    "status_good_bg": "#DDF5E7",
    "status_good": "#17623E",
    "status_error_bg": "#FBE8EB",
    "status_error": "#A62F3B",
    "status_neutral_bg": "#E8EEEA",
    "status_neutral": "#56635C",
    "status_wait_bg": "#FFF0D4",
    "status_wait": "#815207",
}

DARK = {
    "bg": "#101713",
    "card": "#17211D",
    "surface_alt": "#1D2A24",
    "surface_hover": "#24342C",
    "text": "#ECF3EF",
    "muted": "#ABB8B1",
    "primary": "#82DFA8",
    "primary_hover": "#A0EABB",
    "action_fill": "#1C6A43",
    "action_hover": "#245F41",
    "border": "#314139",
    "border_strong": "#45594E",
    "danger": "#FFADB5",
    "warning": "#F0CB7B",
    "selection": "#173D2A",
    "placeholder": "#AAB8B0",
    "disabled": "#89958F",
    "highlight_text": "#FFFFFF",
    "sidebar": "#0A110E",
    "sidebar_hover": "#16251E",
    "sidebar_active": "#1C4B32",
    "sidebar_text": "#EEF6F1",
    "sidebar_muted": "#91A49A",
    "hero_start": "#173D2A",
    "hero_end": "#18251F",
    "status_good_bg": "#1B4931",
    "status_good": "#9BE5B7",
    "status_error_bg": "#4C292F",
    "status_error": "#FFB3BA",
    "status_neutral_bg": "#2B3832",
    "status_neutral": "#CBD5D0",
    "status_wait_bg": "#4B3D22",
    "status_wait": "#F0CB7B",
}


def apply_theme(app: QApplication, preference: str = "system") -> None:
    dark = preference == "dark" or (
        preference == "system"
        and QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    )
    c = DARK if dark else LIGHT
    app.setProperty("themeMode", "dark" if dark else "light")
    app.setProperty("themePrimary", c["primary"])
    app.setProperty("sidebarText", c["sidebar_text"])
    app.setProperty("sidebarActiveText", c["primary"])
    app.setStyle("Fusion")

    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["bg"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["card"],
        QPalette.ColorRole.AlternateBase: c["surface_alt"],
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
        QPalette.ColorRole.Shadow: "#07110C",
        QPalette.ColorRole.Accent: c["primary"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    app.setPalette(palette)

    # Clearing first also refreshes popup views already created by QComboBox.
    app.setStyleSheet("")
    app.setStyleSheet(f"""
        * {{
            font-family: "Segoe UI Variable Text", "Segoe UI";
            font-size: 10pt;
            color: {c['text']};
        }}
        QMainWindow, QDialog, QWidget#Page {{ background: {c['bg']}; }}
        QStackedWidget {{ background: {c['bg']}; }}

        QWidget#Sidebar {{
            background: {c['sidebar']};
            border-right: 1px solid {c['sidebar_hover']};
        }}
        QWidget#Sidebar QLabel#BrandName {{ color: {c['sidebar_text']}; }}
        QWidget#Sidebar QLabel#BrandCaption,
        QWidget#Sidebar QLabel#SidebarSection,
        QWidget#Sidebar QLabel#SidebarFooterCaption,
        QWidget#Sidebar QLabel#SidebarVersion {{ color: {c['sidebar_muted']}; }}
        QLabel#SidebarSection {{
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 1.4px;
        }}
        QFrame#SidebarFooter {{
            background: {c['sidebar_hover']};
            border: 1px solid {c['border_strong']};
            border-radius: 11px;
        }}
        QLabel#SidebarFooterTitle {{ color: {c['sidebar_text']}; font-weight: 650; }}
        QLabel#SidebarFooterCaption {{ font-size: 8.5pt; }}
        QLabel#SidebarVersion {{ font-size: 8.5pt; }}

        QLabel#PageTitle {{ font-size: 22pt; font-weight: 700; letter-spacing: -0.3px; }}
        QLabel#PageSubtitle {{ color: {c['muted']}; font-size: 10.5pt; }}
        QLabel#Muted {{ color: {c['muted']}; }}
        QLabel#SectionTitle {{ font-size: 12pt; font-weight: 650; }}
        QLabel#SectionEyebrow, QLabel#Eyebrow {{
            color: {c['primary']}; font-size: 8.5pt; font-weight: 750; letter-spacing: 1px;
        }}
        QLabel#PageHeaderIcon {{
            background: {c['selection']};
            border: 1px solid {c['border']};
            border-radius: 12px;
        }}
        QLabel#BrandName {{ color: {c['primary']}; font-size: 12pt; font-weight: 700; }}
        QLabel#HeroName {{ font-size: 21pt; font-weight: 700; letter-spacing: -0.2px; }}
        QLabel#HeroTitle {{ font-size: 18pt; font-weight: 700; }}
        QLabel#HeroSubtitle {{ color: {c['muted']}; font-size: 10.5pt; }}
        QLabel#BrandCaption {{ color: {c['primary']}; font-size: 7pt; font-weight: 750; letter-spacing: .8px; }}
        QLabel#Metric {{ color: {c['primary']}; font-size: 18pt; font-weight: 700; }}
        QLabel#TintedIcon, QLabel#StepIcon {{
            background: {c['selection']}; border: 1px solid {c['border']}; border-radius: 12px;
        }}
        QLabel#WarningText {{ color: {c['warning']}; }}
        QLabel#ErrorText {{ color: {c['danger']}; }}
        QLabel#MetaPill {{
            color: {c['primary']}; background: {c['selection']}; border-radius: 8px;
            padding: 4px 9px; font-size: 8.5pt; font-weight: 650;
        }}
        QLabel#Notice {{
            padding: 11px 13px; border-radius: 9px; border: 1px solid {c['border']};
        }}
        QLabel#Notice[state="info"] {{ background: {c['selection']}; color: {c['primary']}; }}
        QLabel#Notice[state="error"] {{
            background: {c['status_error_bg']}; color: {c['status_error']};
            border-color: {c['status_error']};
        }}
        QLabel#Thumbnail {{
            background: {c['surface_alt']}; color: {c['muted']};
            border: 1px solid {c['border']}; border-radius: 9px;
        }}
        QLabel#SpotifyLogo {{
            background: #FFFFFF; border: 1px solid {c['border']};
            border-radius: 9px; padding: 6px;
        }}
        QLabel#StatusBadge {{ border-radius: 8px; font-size: 8.5pt; font-weight: 700; }}
        QLabel#StatusBadge[status="completed"] {{ background: {c['status_good_bg']}; color: {c['status_good']}; }}
        QLabel#StatusBadge[status="error"] {{ background: {c['status_error_bg']}; color: {c['status_error']}; }}
        QLabel#StatusBadge[status="cancelled"] {{ background: {c['status_neutral_bg']}; color: {c['status_neutral']}; }}
        QLabel#StatusBadge[status="queued"] {{ background: {c['status_wait_bg']}; color: {c['status_wait']}; }}
        QLabel#StatusBadge[status="active"] {{ background: {c['selection']}; color: {c['primary']}; }}

        QFrame#Card, QFrame#DownloadCard, QFrame#MediaPreviewCard {{
            background: {c['card']}; border: 1px solid {c['border']}; border-radius: 13px;
        }}
        QFrame#Card[accent="true"], QFrame#MediaPreviewCard {{ border-top: 3px solid {c['primary']}; }}
        QFrame#SoftCard, QFrame#WorkflowStep {{
            background: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 11px;
        }}
        QFrame#HeroCard {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {c['hero_start']}, stop:1 {c['hero_end']});
            border: 1px solid {c['border_strong']}; border-radius: 16px;
        }}
        QFrame#Toolbar {{
            background: {c['card']}; border: 1px solid {c['border']}; border-radius: 11px;
        }}
        QFrame#ComponentStatus {{
            background: {c['surface_alt']}; border: 1px solid {c['border']};
            border-radius: 9px; padding: 8px 10px;
        }}
        QFrame#ComponentStatus[state="ready"] {{ background: {c['status_good_bg']}; border-color: {c['status_good']}; }}
        QFrame#ComponentStatus[state="pending"] {{ background: {c['status_wait_bg']}; border-color: {c['status_wait']}; }}
        QFrame#ComponentStatus[state="error"] {{ background: {c['status_error_bg']}; border-color: {c['status_error']}; }}
        QWidget#EmptyState {{
            background: {c['card']}; border: 1px dashed {c['border_strong']}; border-radius: 14px;
        }}

        QLineEdit, QComboBox, QSpinBox {{
            background: {c['card']}; border: 1px solid {c['border_strong']}; border-radius: 9px;
            padding: 8px 11px; min-height: 27px; color: {c['text']};
            selection-background-color: {c['action_fill']}; selection-color: {c['highlight_text']};
        }}
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {c['muted']}; }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 2px solid {c['primary']}; padding: 7px 10px;
        }}
        QLineEdit:read-only {{ background: {c['surface_alt']}; color: {c['muted']}; }}
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
            background: {c['surface_alt']}; color: {c['disabled']}; border-color: {c['border']};
        }}
        QComboBox::drop-down {{ border: 0; width: 30px; }}
        QComboBox:on {{ border: 2px solid {c['primary']}; padding: 7px 10px; }}
        QComboBox QAbstractItemView {{
            background: {c['card']}; color: {c['text']}; border: 1px solid {c['border_strong']};
            outline: 0; padding: 5px; selection-background-color: {c['primary']};
            selection-color: {c['highlight_text']};
        }}
        QComboBox QAbstractItemView::item {{ min-height: 34px; padding: 6px 9px; border-radius: 6px; }}
        QComboBox QAbstractItemView::item:hover {{ background: {c['selection']}; color: {c['text']}; }}
        QComboBox QAbstractItemView::item:selected,
        QComboBox QAbstractItemView::item:selected:active {{
            background: {c['action_fill']}; color: {c['highlight_text']};
        }}

        QPushButton {{
            min-height: 27px; padding: 8px 14px; border-radius: 9px;
            border: 1px solid {c['border_strong']}; background: {c['card']}; font-weight: 550;
        }}
        QPushButton:hover {{ background: {c['surface_alt']}; border-color: {c['primary']}; }}
        QPushButton:pressed {{ background: {c['selection']}; border-color: {c['primary_hover']}; }}
        QPushButton:focus {{ border: 2px solid {c['primary']}; padding: 7px 13px; }}
        QPushButton:disabled {{ color: {c['disabled']}; background: {c['surface_alt']}; border-color: {c['border']}; }}
        QPushButton[role="primary"] {{
            color: white; background: {c['action_fill']}; border-color: {c['action_fill']}; font-weight: 700;
        }}
        QPushButton[role="primary"]:hover, QPushButton[role="primary"]:pressed {{
            color: white; background: {c['action_hover']}; border-color: {c['action_hover']};
        }}
        QPushButton[role="primary"]:disabled {{
            color: {c['disabled']}; background: {c['surface_alt']}; border-color: {c['border']};
        }}
        QPushButton[role="danger"] {{ color: {c['danger']}; border-color: {c['danger']}; }}
        QPushButton[role="danger"]:hover {{ background: {c['status_error_bg']}; }}
        QPushButton[role="quiet"] {{ background: transparent; border-color: transparent; }}
        QPushButton[segment="true"] {{ min-width: 88px; }}
        QPushButton[segment="true"]:checked {{
            color: {c['primary']}; background: {c['selection']};
            border-color: {c['primary']}; font-weight: 700;
        }}
        QPushButton#SidebarButton {{
            color: {c['sidebar_text']}; text-align: left; padding: 10px 14px;
            border: 1px solid transparent; border-radius: 10px; background: transparent;
        }}
        QPushButton#SidebarButton:hover {{ color: {c['sidebar_text']}; background: {c['sidebar_hover']}; }}
        QPushButton#SidebarButton:checked {{
            color: {c['primary']}; background: {c['sidebar_active']};
            border-color: {c['sidebar_active']}; font-weight: 700;
        }}

        QProgressBar {{
            border: 0; border-radius: 4px; background: {c['surface_alt']};
            min-height: 8px; max-height: 8px; text-align: center;
        }}
        QProgressBar::chunk {{ border-radius: 4px; background: {c['primary']}; }}
        QScrollArea {{ border: 0; background: transparent; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}

        QTableWidget {{
            background: {c['card']}; alternate-background-color: {c['surface_alt']};
            border: 1px solid {c['border']}; border-radius: 11px; gridline-color: transparent;
            selection-background-color: {c['selection']}; selection-color: {c['text']}; outline: 0;
        }}
        QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {c['border']}; }}
        QTableWidget::item:selected {{ color: {c['text']}; }}
        QTableWidget:focus, QListWidget:focus {{ border: 2px solid {c['primary']}; }}
        QHeaderView::section {{
            background: {c['surface_alt']}; border: 0; border-bottom: 1px solid {c['border_strong']};
            padding: 10px; font-size: 9pt; font-weight: 700;
        }}
        QListWidget {{
            background: {c['card']}; border: 1px solid {c['border']}; border-radius: 9px; outline: 0;
        }}
        QListWidget::item {{ min-height: 31px; padding: 6px 8px; border-radius: 6px; }}
        QListWidget::item:hover {{ background: {c['surface_alt']}; }}
        QListWidget::item:selected {{ background: {c['selection']}; color: {c['text']}; }}

        QMenu {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; }}
        QMenu::item {{ min-height: 28px; padding: 8px 28px 8px 11px; border-radius: 6px; }}
        QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
        QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}
        QToolTip {{ background: {c['card']}; border: 1px solid {c['border_strong']}; color: {c['text']}; padding: 5px; }}

        QCheckBox::indicator {{ width: 20px; height: 20px; }}
        QCheckBox {{
            min-height: 32px; spacing: 9px; padding: 4px; border: 1px solid transparent; border-radius: 7px;
        }}
        QCheckBox:hover {{ background: {c['surface_alt']}; }}
        QCheckBox:focus {{ border-color: {c['primary']}; background: {c['selection']}; }}

        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 3px 2px; }}
        QScrollBar::handle:vertical {{ background: {c['border_strong']}; min-height: 34px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px 3px; }}
        QScrollBar::handle:horizontal {{ background: {c['border_strong']}; min-width: 34px; border-radius: 4px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        QFormLayout QLabel {{ padding-top: 4px; }}
    """)

    from .icons import refresh_button_icons

    refresh_button_icons(app)
