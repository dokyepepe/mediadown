"""Application logging with rotation and basic secret redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from .paths import logs_dir


class RedactSecretsFilter(logging.Filter):
    PATTERNS = (
        (
            re.compile(r"(?i)\b(authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"),
            r"\1=[REMOVIDO]",
        ),
        (
            re.compile(
                r"(?i)\b(access[_-]?token|refresh[_-]?token|token|password|passwd)\b"
                r"[\"']?\s*[:=]\s*[\"']?[^\"'\s,;&]+"
            ),
            r"\1=[REMOVIDO]",
        ),
        (re.compile(r"(?i)\b(cookie|set-cookie)\s*:\s*[^\r\n]+"), r"\1=[REMOVIDO]"),
        (re.compile(r"(?i)(https?://[^:/\s]+:)[^@/\s]+@"), r"\1[REMOVIDO]@"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        logs_dir() / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    handler.addFilter(RedactSecretsFilter())
    root.addHandler(handler)
