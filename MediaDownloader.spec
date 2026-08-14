# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sys
from importlib.metadata import distribution

root = Path(SPEC).resolve().parent
sys.path.insert(0, str(root / "src"))
from mediadownloader.version import APP_VERSION
from scripts.sync_version import write_version_info
version_file = root / ".build" / "version_info.txt"
write_version_info(version_file, APP_VERSION)
debug_build = os.environ.get("MEDIA_DOWNLOADER_DEBUG_BUILD") == "1"
build_name = "MediaDownloaderDebug" if debug_build else "MediaDownloader"

datas = [
    (str(root / "assets"), "assets"),
    (str(root / "licenses"), "licenses"),
]
for distribution_name in ("PySide6", "shiboken6", "yt-dlp", "yt-dlp-ejs", "platformdirs"):
    try:
        package = distribution(distribution_name)
        for relative in package.files or []:
            lowered = str(relative).lower().replace("\\", "/")
            if "/license" in lowered or Path(relative).name.lower().startswith(("license", "copying")):
                source = package.locate_file(relative)
                if source.is_file():
                    datas.append((str(source), f"licenses/python/{distribution_name}"))
    except Exception:
        pass
ffmpeg = root / "resources" / "ffmpeg"
if ffmpeg.exists():
    datas.append((str(ffmpeg), "resources/ffmpeg"))
deno = root / "resources" / "deno"
if deno.exists():
    datas.append((str(deno), "resources/deno"))

a = Analysis(
    [str(root / "src" / "mediadownloader" / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "yt_dlp", "yt_dlp.extractor", "yt_dlp.postprocessor",
        "PySide6.QtSvg", "PySide6.QtNetwork",
    ],
    hookspath=[str(root / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=build_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=debug_build,
    icon=str(root / "assets" / "app.ico"),
    version=str(version_file),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=build_name,
)
