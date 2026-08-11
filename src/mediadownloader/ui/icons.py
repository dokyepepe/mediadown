"""Deterministic SVG icon rendering for consistent desktop controls."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

from mediadownloader.utils.paths import asset_path


@lru_cache(maxsize=256)
def svg_pixmap(name: str, size: int = 20, color: str = "#5F666B") -> QPixmap:
    path = asset_path("icons", f"{name}.svg")
    if not path.exists():
        return QPixmap()
    source = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size * ratio, size * ratio))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def svg_icon(name: str, size: int = 20, color: str = "#5F666B") -> QIcon:
    return QIcon(svg_pixmap(name, size, color))


@lru_cache(maxsize=32)
def svg_asset_pixmap(relative_path: str, width: int, height: int) -> QPixmap:
    """Render an unmodified, non-icon SVG asset at a HiDPI-friendly size."""
    path = asset_path(*relative_path.split("/"))
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    ratio = 2
    pixmap = QPixmap(width * ratio, height * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    intrinsic = renderer.defaultSize()
    scale = min(
        (width * ratio) / max(intrinsic.width(), 1),
        (height * ratio) / max(intrinsic.height(), 1),
    )
    render_width = intrinsic.width() * scale
    render_height = intrinsic.height() * scale
    renderer.render(painter, QRectF(
        (width * ratio - render_width) / 2,
        (height * ratio - render_height) / 2,
        render_width,
        render_height,
    ))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def set_button_icon(button, name: str, color: str | None = None, size: int = 18) -> None:
    """Set an SVG icon, using the active palette unless a fixed color is requested."""
    button.setProperty("svgIconName", name)
    button.setProperty("svgIconSize", size)
    button.setProperty("svgIconDynamic", color is None)
    resolved_color = color or button.palette().color(QPalette.ColorRole.ButtonText).name()
    button.setIcon(svg_icon(name, size, resolved_color))
    button.setIconSize(QSize(size, size))


def refresh_button_icons(app) -> None:
    """Re-render palette-aware SVG button icons after a live theme change."""
    for widget in app.allWidgets():
        name = widget.property("svgIconName")
        if not name or not widget.property("svgIconDynamic"):
            continue
        size = int(widget.property("svgIconSize") or 18)
        color = widget.palette().color(QPalette.ColorRole.ButtonText).name()
        widget.setIcon(svg_icon(str(name), size, color))
        widget.setIconSize(QSize(size, size))
