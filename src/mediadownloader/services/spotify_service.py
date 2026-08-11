"""Official, metadata-only Spotify integration with OAuth 2.0 PKCE."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from mediadownloader.models import MediaInfo, PlaylistEntry
from mediadownloader.utils.errors import FriendlyError
from mediadownloader.utils.validators import is_spotify_url
from mediadownloader.version import APP_NAME, APP_VERSION

from .secure_store import SecretStore, default_secret_store
from .settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SpotifyResource:
    """Normalized public Spotify resource identifier."""

    kind: str
    resource_id: str
    url: str


class SpotifyService:
    """Read Spotify metadata without ever exposing or downloading its audio streams."""

    OEMBED_URL = "https://open.spotify.com/oembed"
    API_URL = "https://api.spotify.com/v1"
    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    REDIRECT_PORT = 43819
    REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
    SCOPES = "playlist-read-private playlist-read-collaborative"
    DISPLAY_ITEM_LIMIT = 20
    RESOURCE_TYPES = {"track", "album", "artist", "playlist", "show", "episode", "audiobook"}

    def __init__(
        self,
        settings: SettingsService,
        secret_store: SecretStore | None = None,
        browser_open: Callable[[str], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.secret_store = secret_store or default_secret_store()
        self.browser_open = browser_open or (lambda url: webbrowser.open(url, new=2))

    @classmethod
    def parse_resource(cls, url: str) -> SpotifyResource | None:
        """Parse official Spotify URLs, including localized and embed paths."""
        if not is_spotify_url(url):
            return None
        parsed = urlparse(url.strip())
        if (parsed.hostname or "").lower() == "spotify.link":
            return SpotifyResource("short", "", url.strip())
        parts = [part for part in parsed.path.split("/") if part]
        parts = [part for part in parts if not part.lower().startswith("intl-")]
        if parts and parts[0].lower() == "embed":
            parts.pop(0)
        if len(parts) < 2 or parts[0].lower() not in cls.RESOURCE_TYPES:
            return None
        kind, resource_id = parts[0].lower(), parts[1]
        if not re.fullmatch(r"[A-Za-z0-9]+", resource_id):
            return None
        return SpotifyResource(kind, resource_id, url.strip())

    @staticmethod
    def valid_client_id(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9]{20,64}", value.strip()))

    def analyze(self, url: str) -> MediaInfo:
        """Resolve public oEmbed data and enrich authorized resources when possible."""
        resource = self.parse_resource(url)
        if not resource:
            raise FriendlyError("Este link do Spotify não possui um formato reconhecido.", code="spotify_url")
        oembed = self._request_json(f"{self.OEMBED_URL}?{urlencode({'url': url.strip()})}")
        embedded = self.parse_resource(str(oembed.get("iframe_url") or ""))
        if resource.kind == "short" and embedded:
            resource = SpotifyResource(embedded.kind, embedded.resource_id, url.strip())

        media = MediaInfo(
            url=url.strip(),
            title=str(oembed.get("title") or "Conteúdo do Spotify"),
            thumbnail=str(oembed.get("thumbnail_url") or ""),
            platform="Spotify",
            media_id=resource.resource_id,
            webpage_url=url.strip(),
            is_playlist=resource.kind == "playlist",
            download_supported=False,
            source_notice=(
                "O Spotify fornece somente metadados nesta integração. "
                "O áudio protegido não pode ser exportado pelo Media Downloader."
            ),
            raw={
                "spotify": True,
                "spotify_resource_type": resource.kind,
                "spotify_authenticated": False,
                "spotify_attribution": True,
            },
        )

        if not resource.resource_id or not self.has_authorization():
            media.raw["spotify_requires_auth"] = resource.kind == "playlist"
            return media

        try:
            details = self._resource_details(resource)
            self._enrich_media(media, resource, details)
        except FriendlyError as error:
            LOGGER.info("Metadados Spotify limitados: %s", error.code)
            media.raw["spotify_auth_error"] = error.message
            media.raw["spotify_requires_auth"] = resource.kind == "playlist"
        return media

    def has_authorization(self) -> bool:
        token = self._load_token()
        return bool(
            token
            and token.get("client_id") == self.client_id
            and (token.get("access_token") or token.get("refresh_token"))
        )

    @property
    def client_id(self) -> str:
        return str(self.settings.get("spotify.client_id", "")).strip()

    def connection_name(self) -> str:
        token = self._load_token()
        if not token or token.get("client_id") != self.client_id:
            return "Não conectado"
        return str(token.get("profile_name") or token.get("profile_id") or "Conta conectada")

    def authorize(self, timeout: int = 180) -> str:
        """Open the consent page and wait for a single loopback PKCE callback."""
        client_id = self.client_id
        if not self.valid_client_id(client_id):
            raise FriendlyError(
                "Informe um Client ID válido do Spotify antes de conectar.",
                code="spotify_client_id",
            )
        verifier = secrets.token_urlsafe(72)[:96]
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")
        state = secrets.token_urlsafe(32)
        result: dict[str, str] = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(handler) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                parsed = urlparse(handler.path)
                if parsed.path != "/callback":
                    handler.send_error(404)
                    return
                values = parse_qs(parsed.query)
                for key in ("code", "state", "error"):
                    if values.get(key):
                        result[key] = values[key][0]
                success = "code" in result and "error" not in result
                title = "Spotify conectado" if success else "Autorização não concluída"
                body = (
                    "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width'><title>Media Downloader</title>"
                    "<style>body{font-family:Segoe UI,sans-serif;background:#f5f6f7;color:#252525;"
                    "display:grid;place-items:center;min-height:90vh}main{background:white;border:1px solid #dadde1;"
                    "border-radius:8px;padding:28px;max-width:520px}h1{color:#2e8b57}</style></head>"
                    f"<body><main><h1>{title}</h1><p>Você pode fechar esta janela e voltar ao "
                    "Media Downloader.</p></main></body></html>"
                ).encode("utf-8")
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)

            def log_message(handler, format: str, *args: object) -> None:
                return

        try:
            server = HTTPServer(("127.0.0.1", self.REDIRECT_PORT), CallbackHandler)
        except OSError as error:
            raise FriendlyError(
                f"A porta local {self.REDIRECT_PORT} está ocupada. Feche o outro aplicativo e tente novamente.",
                details=str(error),
                code="spotify_callback",
            ) from error

        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": self.REDIRECT_URI,
            "scope": self.SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "show_dialog": "true",
        }
        try:
            server.timeout = max(30, min(timeout, 300))
            if not self.browser_open(f"{self.AUTHORIZE_URL}?{urlencode(params)}"):
                raise FriendlyError("Não foi possível abrir o navegador para autorização.", code="browser")
            server.handle_request()
        finally:
            server.server_close()

        if not result:
            raise FriendlyError("A autorização do Spotify expirou. Tente novamente.", code="spotify_timeout")
        if not secrets.compare_digest(result.get("state", ""), state):
            raise FriendlyError("A resposta de autorização não pôde ser validada.", code="spotify_state")
        if result.get("error"):
            raise FriendlyError("A autorização do Spotify foi cancelada.", code="spotify_denied")
        code = result.get("code", "")
        if not code:
            raise FriendlyError("O Spotify não retornou um código de autorização.", code="spotify_code")

        token = self._request_json(
            self.TOKEN_URL,
            method="POST",
            form={
                "client_id": client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        token["expires_at"] = int(time.time()) + int(token.get("expires_in") or 3600)
        token["client_id"] = client_id
        access_token = str(token.get("access_token") or "")
        if not access_token:
            raise FriendlyError("O Spotify não retornou um token de acesso.", code="spotify_token")
        try:
            profile = self._request_json(
                f"{self.API_URL}/me", headers={"Authorization": f"Bearer {access_token}"}
            )
            token["profile_name"] = str(profile.get("display_name") or "")
            token["profile_id"] = str(profile.get("id") or "")
        except FriendlyError:
            token["profile_name"] = "Conta conectada"
        self._save_token(token)
        return str(token.get("profile_name") or token.get("profile_id") or "Conta conectada")

    def disconnect(self) -> None:
        self.secret_store.delete()

    def _resource_details(self, resource: SpotifyResource) -> dict[str, Any]:
        endpoint = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "playlist": "playlists",
            "show": "shows",
            "episode": "episodes",
            "audiobook": "audiobooks",
        }.get(resource.kind)
        if not endpoint:
            return {}
        details = self._api_get(f"/{endpoint}/{resource.resource_id}")
        if resource.kind == "playlist":
            page = self._api_get(
                f"/playlists/{resource.resource_id}/items?"
                f"{urlencode({'limit': self.DISPLAY_ITEM_LIMIT, 'offset': 0, 'additional_types': 'track,episode'})}"
            )
            details["_display_items"] = page.get("items") or []
            details["_items_total"] = page.get("total")
        return details

    def _enrich_media(
        self,
        media: MediaInfo,
        resource: SpotifyResource,
        details: dict[str, Any],
    ) -> None:
        media.raw["spotify_authenticated"] = True
        media.raw["spotify_requires_auth"] = False
        media.title = str(details.get("name") or media.title)
        media.webpage_url = str(
            (details.get("external_urls") or {}).get("spotify") or media.webpage_url
        )
        media.thumbnail = self._image(details.get("images")) or media.thumbnail
        if resource.kind in {"track", "album"}:
            media.author = self._artists(details.get("artists"))
        elif resource.kind == "artist":
            media.author = "Artista"
        elif resource.kind == "playlist":
            owner = details.get("owner") or {}
            media.author = str(owner.get("display_name") or owner.get("id") or "")
            raw_items = details.get("_display_items") or []
            media.entries = [
                entry
                for index, wrapper in enumerate(raw_items, start=1)
                if (entry := self._playlist_entry(wrapper, index)) is not None
            ]
            items_block = details.get("items") or details.get("tracks") or {}
            media.playlist_count = int(
                details.get("_items_total") or items_block.get("total") or len(media.entries)
            )
            media.raw["spotify_display_limit"] = self.DISPLAY_ITEM_LIMIT
        elif resource.kind == "episode":
            show = details.get("show") or {}
            media.author = str(show.get("name") or details.get("publisher") or "")
            media.duration = self._duration(details.get("duration_ms"))
        elif resource.kind == "show":
            media.author = str(details.get("publisher") or "")
        media.duration = media.duration or self._duration(details.get("duration_ms"))

    def _playlist_entry(self, wrapper: dict[str, Any], index: int) -> PlaylistEntry | None:
        item = wrapper.get("item") or wrapper.get("track") or {}
        if not isinstance(item, dict) or not item.get("name"):
            return None
        resource_type = str(item.get("type") or "track")
        album = item.get("album") or {}
        show = item.get("show") or {}
        author = self._artists(item.get("artists")) or str(show.get("name") or "")
        images = album.get("images") or item.get("images") or show.get("images")
        return PlaylistEntry(
            url=str((item.get("external_urls") or {}).get("spotify") or item.get("uri") or ""),
            title=str(item.get("name")),
            index=index,
            thumbnail=self._image(images),
            duration=self._duration(item.get("duration_ms")),
            author=author,
            album=str(album.get("name") or show.get("name") or ""),
            resource_type=resource_type,
        )

    def _api_get(self, path: str) -> dict[str, Any]:
        token = self._access_token()
        try:
            return self._request_json(
                f"{self.API_URL}{path}", headers={"Authorization": f"Bearer {token}"}
            )
        except FriendlyError as error:
            if error.code != "spotify_unauthorized":
                raise
        token = self._access_token(force_refresh=True)
        return self._request_json(
            f"{self.API_URL}{path}", headers={"Authorization": f"Bearer {token}"}
        )

    def _access_token(self, force_refresh: bool = False) -> str:
        token = self._load_token()
        if not token or token.get("client_id") != self.client_id:
            raise FriendlyError("Conecte sua conta do Spotify nas Configurações.", code="spotify_auth")
        access_token = str(token.get("access_token") or "")
        expires_at = int(token.get("expires_at") or 0)
        if access_token and not force_refresh and expires_at > time.time() + 60:
            return access_token
        refresh_token = str(token.get("refresh_token") or "")
        if not refresh_token:
            raise FriendlyError("A sessão do Spotify expirou. Conecte a conta novamente.", code="spotify_auth")
        refreshed = self._request_json(
            self.TOKEN_URL,
            method="POST",
            form={
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        token.update(refreshed)
        token["refresh_token"] = str(refreshed.get("refresh_token") or refresh_token)
        token["expires_at"] = int(time.time()) + int(refreshed.get("expires_in") or 3600)
        self._save_token(token)
        return str(token.get("access_token") or "")

    def _load_token(self) -> dict[str, Any]:
        try:
            value = self.secret_store.read()
            loaded = json.loads(value) if value else {}
            return loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_token(self, token: dict[str, Any]) -> None:
        safe_fields = {
            key: token[key]
            for key in (
                "access_token", "refresh_token", "expires_at", "scope", "token_type",
                "client_id", "profile_name", "profile_id",
            )
            if key in token
        }
        try:
            self.secret_store.write(json.dumps(safe_fields, ensure_ascii=False))
        except OSError as error:
            raise FriendlyError(
                "Não foi possível proteger a sessão no Gerenciador de Credenciais do Windows.",
                details=str(error),
                code="spotify_credentials",
            ) from error

    def _request_json(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        form: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = urlencode(form).encode("utf-8") if form is not None else None
        request_headers = {
            "Accept": "application/json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            **(headers or {}),
        }
        if form is not None:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=body, headers=request_headers, method=method)
        for attempt in range(2):
            try:
                with urlopen(request, timeout=20) as response:
                    payload = response.read(2_000_000)
                parsed = json.loads(payload.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("Resposta JSON inesperada")
                return parsed
            except HTTPError as error:
                if error.code == 429 and attempt == 0:
                    delay = min(max(int(error.headers.get("Retry-After", "1")), 1), 5)
                    time.sleep(delay)
                    continue
                code = {
                    401: "spotify_unauthorized",
                    403: "spotify_forbidden",
                    404: "spotify_not_found",
                    429: "spotify_rate_limit",
                }.get(error.code, "spotify_http")
                message = {
                    401: "A autorização do Spotify expirou ou foi recusada.",
                    403: "O Spotify não permitiu acesso a este item. A playlist deve pertencer a você ou ser colaborativa.",
                    404: "O conteúdo do Spotify não foi encontrado.",
                    429: "O limite temporário da API do Spotify foi atingido. Aguarde e tente novamente.",
                }.get(error.code, "O Spotify não conseguiu processar esta solicitação.")
                raise FriendlyError(message, f"HTTP {error.code}", code) from error
            except (URLError, TimeoutError) as error:
                raise FriendlyError(
                    "Não foi possível conectar ao Spotify. Verifique sua conexão.",
                    details=str(getattr(error, "reason", error)),
                    code="spotify_network",
                ) from error
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                raise FriendlyError(
                    "O Spotify retornou uma resposta inválida.",
                    details=str(error),
                    code="spotify_response",
                ) from error
        raise FriendlyError("O Spotify está temporariamente indisponível.", code="spotify_network")

    @staticmethod
    def _artists(value: Any) -> str:
        if not isinstance(value, list):
            return ""
        return ", ".join(
            str(artist.get("name"))
            for artist in value
            if isinstance(artist, dict) and artist.get("name")
        )

    @staticmethod
    def _image(value: Any) -> str:
        if not isinstance(value, list):
            return ""
        for image in value:
            if isinstance(image, dict) and image.get("url"):
                return str(image["url"])
        return ""

    @staticmethod
    def _duration(value: Any) -> int | None:
        try:
            return int(value) // 1000 if value is not None else None
        except (TypeError, ValueError):
            return None
