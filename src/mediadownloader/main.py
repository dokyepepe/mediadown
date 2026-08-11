"""GUI entry point."""

from __future__ import annotations

import sys


def main() -> int:
    # The verified user-local yt-dlp component must precede the bundled fallback.
    from mediadownloader.services.update_service import activate_updated_ytdlp
    activate_updated_ytdlp()

    from PySide6.QtCore import QLocale, QTimer, Qt
    from PySide6.QtWidgets import QApplication

    from mediadownloader.services import HistoryService, SettingsService
    from mediadownloader.ui.main_window import MainWindow
    from mediadownloader.ui.theme import apply_theme
    from mediadownloader.ui.welcome_dialog import WelcomeDialog
    from mediadownloader.utils.logger import configure_logging
    from mediadownloader.version import APP_NAME, APP_VERSION, ORGANIZATION_NAME

    configure_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(True)
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    settings = SettingsService()
    apply_theme(app, settings.get("general.theme", "system"))
    smoke_test = "--smoke-test" in sys.argv
    window = MainWindow(settings, HistoryService())
    window.show()
    if smoke_test:
        QTimer.singleShot(750, app.quit)
    elif settings.get("general.first_run", True):
        welcome = WelcomeDialog(window)
        welcome.exec()
        settings.set("general.first_run", False)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
