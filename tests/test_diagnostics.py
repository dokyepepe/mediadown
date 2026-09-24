from mediadownloader.ui.pages.about_page import build_diagnostics_summary
from mediadownloader.version import APP_VERSION


def test_diagnostics_summary_contains_identity_and_version() -> None:
    summary = build_diagnostics_summary("C:\\s", "C:\\h", "C:\\l", 128)
    assert APP_VERSION in summary
    assert "Media Downloader" in summary


def test_diagnostics_summary_lists_the_local_locations() -> None:
    summary = build_diagnostics_summary("C:\\settings.json", "C:\\history.sqlite3", "C:\\logs", 4)
    assert "Configurações: C:\\settings.json" in summary
    assert "Histórico: C:\\history.sqlite3" in summary
    assert "Logs: C:\\logs" in summary


def test_diagnostics_summary_reports_extractor_count() -> None:
    summary = build_diagnostics_summary("", "", "", 321)
    assert "Extractors disponíveis: 321" in summary


def test_diagnostics_summary_does_not_require_qtsupport_widgets() -> None:
    summary = build_diagnostics_summary("a", "b", "c", 0)
    assert isinstance(summary, str)
    assert summary.count("\n") >= 8