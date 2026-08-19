#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-linux}"
APPDIR="$ROOT_DIR/.build/AppDir"
APPIMAGETOOL_BIN="${APPIMAGETOOL_BIN:-$(command -v appimagetool || true)}"
VERSION="$($PYTHON_BIN -c "import sys; sys.path.insert(0, '$ROOT_DIR/src'); from mediadownloader.version import APP_VERSION; print(APP_VERSION)")"
ARCH_NAME="${ARCH:-$(uname -m)}"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "O AppImage deve ser compilado em Linux (máquina física, VM, WSL2 ou CI)." >&2
    exit 1
fi
if [[ -z "$APPIMAGETOOL_BIN" ]]; then
    echo "appimagetool não encontrado. Instale-o ou defina APPIMAGETOOL_BIN." >&2
    exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-dev.txt"

cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" -m pytest tests -q
PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/python" -m PyInstaller --noconfirm --clean MediaDownloader.spec

rm -rf "$APPDIR"
install -d "$APPDIR/usr/bin/MediaDownloader" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT_DIR/dist/MediaDownloader/." "$APPDIR/usr/bin/MediaDownloader/"
install -m 755 "$ROOT_DIR/packaging/linux/AppRun" "$APPDIR/AppRun"
install -m 644 "$ROOT_DIR/packaging/linux/io.github.mediadownloader.MediaDownloader.desktop" \
    "$APPDIR/io.github.mediadownloader.MediaDownloader.desktop"
install -m 644 "$ROOT_DIR/packaging/linux/io.github.mediadownloader.MediaDownloader.desktop" \
    "$APPDIR/usr/share/applications/io.github.mediadownloader.MediaDownloader.desktop"
install -m 644 "$ROOT_DIR/assets/app-256.png" \
    "$APPDIR/io.github.mediadownloader.MediaDownloader.png"
install -m 644 "$ROOT_DIR/assets/app-256.png" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps/io.github.mediadownloader.MediaDownloader.png"
ln -sfn io.github.mediadownloader.MediaDownloader.png "$APPDIR/.DirIcon"

QT_QPA_PLATFORM=offscreen MEDIA_DOWNLOADER_DATA_DIR="$ROOT_DIR/.build/appimage-smoke-data" \
    "$APPDIR/AppRun" --smoke-test

mkdir -p "$ROOT_DIR/release"
ARCH="$ARCH_NAME" "$APPIMAGETOOL_BIN" "$APPDIR" \
    "$ROOT_DIR/release/MediaDownloader-$VERSION-$ARCH_NAME.AppImage"
echo "AppImage gerado em release/MediaDownloader-$VERSION-$ARCH_NAME.AppImage"
