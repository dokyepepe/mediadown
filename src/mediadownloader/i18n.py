"""Runtime translation for the desktop UI.

Portuguese (Brazil) is the source language: its strings are written literally in
the widgets, so no catalogue is needed for it. Other locales load a compiled
``.qm`` from :mod:`mediadownloader.translations`; anything the catalogue does not
cover keeps the Portuguese text, which keeps a partial translation usable.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QObject, QTranslator, Signal

#: Every string goes through this context, which keeps one small catalogue per
#: language instead of one per widget class.
CONTEXT = "MediaDown"

#: Locales offered in Settings, mapped to the language shown to the user.
SUPPORTED_LOCALES: dict[str, str] = {
    "pt_BR": "Português (Brasil)",
    "pt": "Português",
    "es": "Español",
}

DEFAULT_LOCALE = "pt_BR"


def translations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "translations"


def normalize_locale(value: str) -> str:
    """Map any stored spelling of a locale onto one of :data:`SUPPORTED_LOCALES`."""
    text = (value or "").strip().replace("-", "_")
    if not text:
        return DEFAULT_LOCALE
    if text in SUPPORTED_LOCALES:
        return text
    lowered = text.lower()
    for code in SUPPORTED_LOCALES:
        if code.lower() == lowered:
            return code
    language = lowered.split("_")[0]
    for code in SUPPORTED_LOCALES:
        if code.lower() == language:
            return code
    return DEFAULT_LOCALE


def tr(text: str, disambiguation: str | None = None) -> str:
    """Translate ``text`` through the installed catalogue."""
    if disambiguation:
        return QCoreApplication.translate(CONTEXT, text, disambiguation)
    return QCoreApplication.translate(CONTEXT, text)


class TranslationService(QObject):
    """Installs the Qt and application translators for one locale."""

    locale_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app_translator = QTranslator(self)
        self._qt_translator = QTranslator(self)
        self.locale = DEFAULT_LOCALE

    def apply(self, locale: str) -> str:
        """Switch to ``locale``; unknown locales fall back to the source language."""
        target = normalize_locale(locale)
        app = QCoreApplication.instance()
        if app is None:
            self.locale = target
            return target

        app.removeTranslator(self._app_translator)
        app.removeTranslator(self._qt_translator)

        if target != DEFAULT_LOCALE:
            catalogue = translations_dir() / f"mediadown_{target}.qm"
            if catalogue.exists() and self._app_translator.load(str(catalogue)):
                app.installTranslator(self._app_translator)
            qt_catalogue = (
                Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
                / f"qtbase_{target}.qm"
            )
            if qt_catalogue.exists() and self._qt_translator.load(str(qt_catalogue)):
                app.installTranslator(self._qt_translator)

        QLocale.setDefault(QLocale(target))
        self.locale = target
        self.locale_changed.emit(target)
        return target
