"""Generate Windows version metadata from mediadownloader.version.APP_VERSION."""

from __future__ import annotations

from pathlib import Path


def write_version_info(path: Path, version: str) -> None:
    parts = [int(part) for part in version.split(".")]
    numeric = tuple((parts + [0, 0, 0, 0])[:4])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric}, prodvers={numeric}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604e4', [
      StringStruct('CompanyName', 'Media Downloader Project'),
      StringStruct('FileDescription', 'Media Downloader'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'MediaDownloader'),
      StringStruct('OriginalFilename', 'MediaDownloader.exe'),
      StringStruct('ProductName', 'Media Downloader'),
      StringStruct('ProductVersion', '{version}')
    ])]),
    VarFileInfo([VarStruct('Translation', [1046, 1252])])
  ]
)\n""",
        encoding="utf-8",
    )

