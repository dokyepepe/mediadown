"""GUI entry point."""

from __future__ import annotations

import sys


_FAULTHANDLER_LOG_FILE = None


def _set_windows_app_user_model_id() -> None:
    """Give Windows one stable identity for the window, taskbar, and shortcuts."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MediaDownloader.Desktop"
        )
    except (AttributeError, OSError):
        pass


def _install_exception_hooks() -> None:
    """Turn uncaught errors into log entries instead of a silent process exit.

    Frozen Qt apps have no console: an exception that escapes a slot or a worker
    thread used to close the window with no traceback. Faulthandler also dumps
    the state after a native crash (e.g. a DLL failure), which then shows up in
    the logs page.
    """
    import faulthandler
    import logging
    import sys
    import threading

    from mediadownloader.utils.paths import logs_dir

    global _FAULTHANDLER_LOG_FILE
    if _FAULTHANDLER_LOG_FILE is None:
        try:
            _FAULTHANDLER_LOG_FILE = open(logs_dir() / "faulthandler.log", "ab", buffering=0)
        except OSError:
            _FAULTHANDLER_LOG_FILE = False
    if _FAULTHANDLER_LOG_FILE is not False:
        try:
            faulthandler.enable(_FAULTHANDLER_LOG_FILE)
        except (OSError, ValueError, RuntimeError):  # already enabled or unusable
            pass

    logger = logging.getLogger("uncaught")

    previous_sys_hook = sys.excepthook

    def main_excepthook(exc_type, exc_value, exc_traceback) -> None:
        logger.error(
            "Exceção não tratada no thread principal: %s: %s",
            exc_type.__name__,
            exc_value,
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if previous_sys_hook is not None:
            try:
                previous_sys_hook(exc_type, exc_value, exc_traceback)
            except Exception:  # logging backend must never re-raise
                pass

    sys.excepthook = main_excepthook

    def thread_excepthook(args) -> None:
        thread_name = getattr(args, "thread", None)
        logger.error(
            "Exceção não tratada na thread %s: %s: %s",
            thread_name.name if thread_name else "desconhecida",
            getattr(args, "exc_type", None).__name__ if getattr(args, "exc_type", None) else "?",
            getattr(args, "exc_value", None),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_excepthook


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--internal-ytdlp-probe":
        from mediadownloader.services.update_service import run_internal_ytdlp_probe

        return run_internal_ytdlp_probe(sys.argv[2])

    from PySide6.QtCore import QLockFile

    from mediadownloader.utils.logger import configure_logging
    from mediadownloader.utils.paths import app_data_dir

    configure_logging()
    _install_exception_hooks()
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
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from mediadownloader.services import HistoryService, SettingsService
    from mediadownloader.ui.main_window import MainWindow
    from mediadownloader.ui.theme import apply_theme
    from mediadownloader.ui.welcome_dialog import WelcomeDialog
    from mediadownloader.utils.paths import asset_path
    from mediadownloader.version import APP_NAME, APP_VERSION, ORGANIZATION_NAME

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(True)
    app_icon = QIcon(str(asset_path("app.ico")))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
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
