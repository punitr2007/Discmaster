#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/build/DiscMaster.AppDir"
DIST_DIR="$SCRIPT_DIR/dist"

echo "==> Building DiscMaster AppImage structure..."

rm -rf "$APP_DIR" "$DIST_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DIST_DIR"

# Copy python scripts and assets
cp "$SCRIPT_DIR/discmaster.py" "$APP_DIR/usr/bin/discmaster.py"
cp "$SCRIPT_DIR/discmaster_engine.py" "$APP_DIR/usr/bin/discmaster_engine.py"
cp "$SCRIPT_DIR/fix_vcd_video.py" "$APP_DIR/usr/bin/fix_vcd_video.py"
chmod +x "$APP_DIR/usr/bin/"*.py

# Copy Icon and Desktop file
cp "$SCRIPT_DIR/assets/discmaster.png" "$APP_DIR/discmaster.png"
cp "$SCRIPT_DIR/assets/discmaster.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/discmaster.png"
cp "$SCRIPT_DIR/assets/discmaster.svg" "$APP_DIR/discmaster.svg"

cat << 'EOF' > "$APP_DIR/discmaster.desktop"
[Desktop Entry]
Name=DiscMaster
GenericName=Optical Disc Studio & Ripper
Comment=Extract, convert, stitch, and rip CD/VCD/DVD optical media
Exec=discmaster
Icon=discmaster
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Video;AudioVideoEditing;DiscBurning;
StartupNotify=true
EOF

# Create AppRun entrypoint
cat << 'EOF' > "$APP_DIR/AppRun"
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

export PATH="${HERE}/usr/bin:${PATH}"
export PYTHONPATH="${HERE}/usr/bin:${PYTHONPATH}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 is required to run DiscMaster." >&2
    exit 1
fi

exec python3 "${HERE}/usr/bin/discmaster.py" "$@"
EOF

chmod +x "$APP_DIR/AppRun"

echo "==> Fetching appimagetool..."
APPIMAGETOOL="$SCRIPT_DIR/build/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    mkdir -p "$SCRIPT_DIR/build"
    curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> Packaging DiscMaster-x86_64.AppImage..."
cd "$DIST_DIR"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APP_DIR" "$DIST_DIR/DiscMaster-x86_64.AppImage"

echo "==> AppImage created successfully: $DIST_DIR/DiscMaster-x86_64.AppImage"
