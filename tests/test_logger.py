"""Logging must not preserve authentication material."""

from __future__ import annotations

import logging

import pytest

from mediadownloader.utils.logger import RedactSecretsFilter


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("Authorization: Bearer spotify-access-secret", "spotify-access-secret"),
        ('{"refresh_token": "spotify-refresh-secret"}', "spotify-refresh-secret"),
        ("Cookie: session=cookie-secret; account=private", "cookie-secret"),
        ("https://user:password-secret@example.com/media", "password-secret"),
        ("https://example.com/callback?access_token=query-secret&state=ok", "query-secret"),
    ],
)
def test_secret_redaction(message: str, secret: str) -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, (), None)

    assert RedactSecretsFilter().filter(record)
    assert secret not in record.getMessage()
    assert "[REMOVIDO]" in record.getMessage()
