"""Keep yt-dlp outside PyInstaller's PYZ so verified local updates can override it."""

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules("yt_dlp")
datas = []
for distribution_name in (
    "yt-dlp",
    "brotli",
    "certifi",
    "mutagen",
    "pycryptodomex",
    "requests",
    "urllib3",
    "websockets",
    "yt-dlp-ejs",
):
    try:
        datas += copy_metadata(distribution_name)
    except Exception:
        # A missing optional distribution must not make the build hook itself fail.
        # The updater validates the exact requirements of every candidate at runtime.
        pass
module_collection_mode = "py"
