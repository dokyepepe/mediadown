from __future__ import annotations

import pytest

from mediadownloader.utils.proxy import validate_proxy_url


@pytest.mark.parametrize(
    ("kind", "url"),
    [
        ("none", ""),
        ("none", "http://qualquer:8080"),  # ignored while disabled
        ("", "lixo qualquer"),
        ("http", "http://127.0.0.1:8080"),
        ("http", "https://proxy.exemplo.com:443"),
        ("socks", "socks5://127.0.0.1:1080"),
        ("socks", "socks5h://127.0.0.1:1080"),
        ("socks", "socks4://127.0.0.1:1080"),
    ],
)
def test_accepted_addresses(kind: str, url: str) -> None:
    valid, message = validate_proxy_url(kind, url)
    assert valid is True
    assert message == ""


@pytest.mark.parametrize(
    ("kind", "url", "expected"),
    [
        ("banana", "http://a:1", "desconhecido"),
        ("http", "", "Informe o endereço"),
        ("http", "127.0.0.1:8080", "esquemas"),
        ("http", "socks5://127.0.0.1:1080", "esquemas"),
        ("http", "http://user:secret@127.0.0.1:8080", "usuário e senha"),
        ("http", "http://127.0.0.1", "porta"),
        ("http", "http://127.0.0.1:70000", "número válido"),
        ("http", "http://:8080", "host"),
        ("http", "http://127.0.0.1:8080/base", "caminho"),
    ],
)
def test_rejected_addresses(kind: str, url: str, expected: str) -> None:
    valid, message = validate_proxy_url(kind, url)
    assert valid is False
    assert expected in message


def test_a_url_without_a_scheme_is_rejected_instead_of_guessed() -> None:
    # yt-dlp would treat this as an unknown scheme and fail later on every
    # download; the inline message names the accepted schemes instead.
    valid, message = validate_proxy_url("socks", "127.0.0.1:1080")
    assert valid is False
    assert "socks5://" in message
