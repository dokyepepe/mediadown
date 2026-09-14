from http.cookiejar import Cookie

from mediadownloader.core.downloader import DownloadEngine


def _session_jar(name: str) -> object:
    jar = __import__("yt_dlp.cookies", fromlist=["YoutubeDLCookieJar"]).YoutubeDLCookieJar(None)
    jar.set_cookie(Cookie(
        0, name, "test-value", None, False,
        ".youtube.com", True, False, "/", True, True, None, False, None, None, {},
    ))
    return jar


def test_check_cookies_none() -> None:
    result = DownloadEngine().check_cookies()
    assert result.ok is True
    assert result.cookie_count == 0
    assert not result.logged_in


def test_check_cookies_file_missing() -> None:
    result = DownloadEngine().check_cookies("file")
    assert result.ok is False
    assert "arquivo" in result.message.lower()


def test_check_cookies_file_not_found() -> None:
    result = DownloadEngine().check_cookies("file", "C:\\nao_existe_cookies.txt")
    assert result.ok is False
    assert "não encontrado" in result.message.lower()


def test_check_cookies_file_valid(tmp_path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tabc123\n",
        encoding="utf-8",
    )
    result = DownloadEngine().check_cookies("file", str(cookie_file))
    assert result.ok is True
    assert result.cookie_count >= 1
    assert result.logged_in is True


def test_check_cookies_browser_unsupported() -> None:
    result = DownloadEngine().check_cookies("browser", browser="no-such-browser")
    assert result.ok is False


def test_cookie_report_detects_youtube_session() -> None:
    engine = DownloadEngine()
    report = engine._cookie_report(_session_jar("SAPISID"), "teste")
    assert report.ok is True
    assert report.logged_in is True
    assert report.cookie_count == 1


def test_cookie_report_flags_empty_jar() -> None:
    jar = __import__("yt_dlp.cookies", fromlist=["YoutubeDLCookieJar"]).YoutubeDLCookieJar(None)
    report = DownloadEngine()._cookie_report(jar, "teste")
    assert report.ok is False


def test_browser_cookie_failure_misspelled_database() -> None:
    engine = DownloadEngine()
    result = engine._browser_cookie_failure(
        "whale", 'could not find whale cookies database in "C:\\Users\\x"'
    )
    assert "nenhum perfil" in result.message.lower()


def test_check_cookies_file_invalid(tmp_path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("isto não é um arquivo netscape", encoding="utf-8")
    result = DownloadEngine().check_cookies("file", str(cookie_file))
    assert result.ok is False