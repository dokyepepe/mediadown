from mediadownloader.utils.cookie_profiles import (
    host_of,
    matched_profile,
    profile_matches,
    resolve_cookies,
)

PROFILE = {
    "id": "abc",
    "label": "Conta pessoal",
    "hosts": ["youtube.com", "m.youtube.com"],
    "file": "C:\\perfil\\cookies.txt",
}


def test_host_of_normalizes_www_and_case() -> None:
    assert host_of("https://WWW.YouTube.COM/watch?v=1") == "youtube.com"
    assert host_of("https://youtube.com") == "youtube.com"
    assert host_of("http://m.youtube.com/x") == "m.youtube.com"


def test_host_of_rejects_scheme_less_and_invalid() -> None:
    assert host_of("youtube.com") == ""
    assert host_of("") == ""
    assert host_of("https://") == ""
    assert host_of("https:///caminho") == ""


def test_profile_matches_domain_subdomain_and_www() -> None:
    assert profile_matches(PROFILE, "https://youtube.com/watch?v=1") is True
    assert profile_matches(PROFILE, "https://www.youtube.com/watch?v=1") is True
    assert profile_matches(PROFILE, "https://m.youtube.com/watch?v=1") is True
    assert profile_matches(PROFILE, "https://no-such-host.com/v") is False


def test_profile_matches_does_not_hit_unrelated_suffix() -> None:
    profile = {"hosts": ["ube.com"], "file": "x.txt"}
    assert profile_matches(profile, "https://youtube.com/v") is False


def test_profile_matches_ignores_schemeless_url() -> None:
    assert profile_matches(PROFILE, "youtube.com") is False


def test_matched_profile_skips_profiles_without_file() -> None:
    profiles = [{"id": "a", "label": "vazio", "hosts": ["youtube.com"], "file": ""}]
    assert matched_profile(profiles, "https://youtube.com") is None


def test_resolve_cookies_gives_profile_priority() -> None:
    result = resolve_cookies("none", "", "", [PROFILE], "https://m.youtube.com/x")
    assert result == ("C:\\perfil\\cookies.txt", "")


def test_resolve_cookies_falls_back_to_global_file() -> None:
    result = resolve_cookies("file", "C:\\global.txt", "", [], "https://example.com/x")
    assert result == ("C:\\global.txt", "")


def test_resolve_cookies_falls_back_to_global_browser() -> None:
    result = resolve_cookies("browser", "", "edge", [], "https://example.com/x")
    assert result == ("", "edge")


def test_resolve_cookies_none_yields_no_source() -> None:
    result = resolve_cookies("none", "C:\\global.txt", "edge", [], "https://example.com/x")
    assert result == ("", "")


def test_resolve_cookies_profile_wins_over_global_file() -> None:
    result = resolve_cookies(
        "file", "C:\\global.txt", "", [PROFILE], "https://youtube.com/watch?v=1"
    )
    assert result == ("C:\\perfil\\cookies.txt", "")