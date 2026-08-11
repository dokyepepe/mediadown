"""Non-invasive clipboard URL detection."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QClipboard

from mediadownloader.utils.validators import is_valid_url


class ClipboardService(QObject):
    url_detected = Signal(str)

    def __init__(self, clipboard: QClipboard) -> None:
        super().__init__()
        self.clipboard = clipboard
        clipboard.dataChanged.connect(self._on_change)

    def current_url(self) -> str:
        text = self.clipboard.text().strip()
        return text if is_valid_url(text) else ""

    def _on_change(self) -> None:
        if url := self.current_url():
            self.url_detected.emit(url)

