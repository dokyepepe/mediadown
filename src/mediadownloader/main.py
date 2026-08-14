"""GUI entry point."""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--internal-ytdlp-probe":
        from mediadownloader.services.update_service import run_internal_ytdlp_probe

        return run_internal_ytdlp_probe(sys.argv[2])

    from PySide6.QtCore import QLockFile

    from mediadownloader.utils.logger import configure_logging
    from mediadownloader.utils.paths import app_data_dir

    configure_logging()
    instance_lock = QLockFile(str(app_data_dir() / "MediaDownloader.lock"))
    if not instance_lock.tryLock(0):
        from PySide6.QtWidgets import QApplication, QMessageBox

        duplicate_app = QApplication(sys.argv)
        QMessageBox.information(
            None,
            "Media Downloader já está aberto",
            "Use a janela que já está aberta. Isso também protege atualizações e downloads em andamento.",
        )
        duplicate_app.quit()
        return 0

    # Select and probe the user-local yt-dlp component before any engine import.
    from mediadownloader.services.update_service import activate_updated_ytdlp
    activation = activate_updated_ytdlp()

    from PySide6.QtCore import QLocale, QTimer, Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from mediadownloader.services import HistoryService, SettingsService
    from mediadownloader.ui.main_window import MainWindow
    from mediadownloader.ui.theme import apply_theme
    from mediadownloader.ui.welcome_dialog import WelcomeDialog
    from mediadownloader.version import APP_NAME, APP_VERSION, ORGANIZATION_NAME

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
    else:
        if activation.automatic_rollback:
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    window,
                    "Componente restaurado",
                    activation.message,
                ),
            )
        if settings.get("general.first_run", True):
            welcome = WelcomeDialog(window)
            welcome.exec()
            settings.set("general.first_run", False)
    try:
        return app.exec()
    finally:
        instance_lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
