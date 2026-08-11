"""Windows-safe output filename and yt-dlp template helpers."""

from __future__ import annotations

import re
from pathlib import Path

INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
ALLOWED_TEMPLATE_FIELDS = {
    "title", "ext", "uploader", "channel", "artist", "playlist",
    "playlist_index", "track", "track_number", "id", "upload_date", "year",
}
TEMPLATE_FIELD_RE = re.compile(r"%\(([^)]+)\)[#0+\-.0-9]*[a-zA-Z]")


def sanitize_filename(value: str, replacement: str = "_") -> str:
    cleaned = INVALID_WINDOWS_CHARS.sub(replacement, value).strip().rstrip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return "sem_nome"
    stem = cleaned.split(".", 1)[0].upper()
    if stem in RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned[:240].rstrip(". ")


def validate_template(template: str) -> tuple[bool, str]:
    if not template.strip():
        return False, "O template não pode ficar vazio."
    fields = set(TEMPLATE_FIELD_RE.findall(template))
    unknown = fields - ALLOWED_TEMPLATE_FIELDS
    if unknown:
        return False, f"Campos não permitidos: {', '.join(sorted(unknown))}"
    if "ext" not in fields:
        return False, "Inclua %(ext)s no template."
    if ".." in template or Path(template).is_absolute():
        return False, "O template não pode acessar diretórios externos."
    return True, ""


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for number in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Não foi possível criar um nome único para {path.name}")

