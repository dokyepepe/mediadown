"""Validation for the proxy address typed in Settings.

yt-dlp only receives the string, so a typo surfaces much later as a confusing
network error on every download. Catching it here turns a silent failure into an
inline message next to the field.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from PySide6.QtCore import QCoreApplication

#: Proxy schemes accepted for each entry of the ``network.proxy_type`` combo.
SCHEMES = {
    "http": ("http", "https"),
    "https": ("http", "https"),
    "socks": ("socks5", "socks5h", "socks4", "socks"),
}

#: Kept for callers that only need the display order of the combo.
TYPES = ("http", "https", "socks")


def _tr(message: str) -> str:
    return QCoreApplication.translate("ProxySettings", message)


def validate_proxy_url(proxy_type: str, url: str) -> tuple[bool, str]:
    """``(ok, message)`` for the current proxy type and address."""
    kind = str(proxy_type or "none").strip().lower()
    address = str(url or "").strip()
    if kind in ("", "none"):
        return True, ""
    if kind not in SCHEMES:
        return False, _tr("Tipo de proxy desconhecido.")
    if not address:
        return False, _tr("Informe o endereço do proxy ou selecione “Nenhum”.")
    try:
        parts = urlsplit(address)
    except ValueError:
        return False, _tr("Endereço de proxy inválido.")
    scheme = parts.scheme.lower()
    if scheme not in SCHEMES[kind]:
        expected = ", ".join(f"{item}://" for item in SCHEMES[kind])
        return False, _tr("Use um destes esquemas: {expected}.").format(expected=expected)
    if not parts.hostname:
        return False, _tr("O endereço do proxy precisa de um host.")
    if parts.username or parts.password:
        return False, _tr(
            "Não coloque usuário e senha no campo. O aplicativo não registra credenciais."
        )
    try:
        port = parts.port
    except ValueError:
        return False, _tr("A porta do proxy não é um número válido.")
    if port is None:
        return False, _tr("Informe a porta do proxy, por exemplo 8080.")
    if not 1 <= port <= 65535:
        return False, _tr("A porta do proxy deve estar entre 1 e 65535.")
    if parts.path.strip("/"):
        return False, _tr("O endereço do proxy não deve ter caminho.")
    return True, ""
