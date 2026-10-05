#!/bin/bash
#
# Build a pop-fe2 AppImage for x86_64 linux.
#
# Run from anywhere:
#
#   ./appimage/build-appimage.sh
#
# Expects the helper sources to already be checked out in the source tree
# (see the README):
#   atracdenc/     (with its libgha submodule)
#   make_npdata/   (the modern-linux branch)
#   PSL1GHT/       (the use-python3 branch)
#
# Optionally:
#   crunch/bin/crunch*.exe   bundled for creating manuals (run under wine)
#   chdman in $PATH          bundled for .chd support, if it is new enough
#                            to know about extractdvd
#
# The result is written to $OUTPUT_DIR (default: <source>/dist).
# Everything else goes into $BUILD_DIR (default: <source>/build/appimage).
#
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT/build/appimage}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/dist}"
PYTHON="${PYTHON:-python3}"
ARCH=x86_64

FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

VENV="$BUILD_DIR/venv"
DL="$BUILD_DIR/downloads"
APPDIR="$BUILD_DIR/AppDir"
BIN="$APPDIR/usr/bin"
LIBEXEC="$APPDIR/usr/lib/pop-fe2"

log() { echo "==> $*"; }

mkdir -p "$BUILD_DIR" "$DL" "$OUTPUT_DIR"

#
# Python environment
#
if [ ! -x "$VENV/bin/python" ]; then
    log "Creating virtualenv in $VENV"
    "$PYTHON" -m venv "$VENV"
fi
log "Installing python packages"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet pillow pycryptodome requests pycdlib ecdsa \
    pyinstaller pygubu tkinterdnd2 yt-dlp PyPDF2 rarfile setuptools
"$VENV/bin/python" -c "import tkinter" || {
    echo "The python used to build the AppImage has no tkinter." >&2
    exit 1
}

#
# Native helpers
#
log "Building atracdenc"
cmake -S "$ROOT/atracdenc/src" -B "$BUILD_DIR/atracdenc" \
      -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$BUILD_DIR/atracdenc" -j"$(nproc)" >/dev/null

log "Building make_npdata"
make -C "$ROOT/make_npdata/Linux" >/dev/null

log "Building pkgcrypt"
(cd "$ROOT/PSL1GHT/tools/ps3py" && "$VENV/bin/python" setup.py build_ext --inplace >/dev/null)

if [ ! -x "$DL/ffmpeg" ]; then
    log "Downloading static ffmpeg"
    curl -fsSL -o "$DL/ffmpeg.tar.xz" "$FFMPEG_URL"
    tar -xJf "$DL/ffmpeg.tar.xz" -C "$DL" --wildcards --strip-components=1 '*/ffmpeg'
    rm "$DL/ffmpeg.tar.xz"
fi

if [ ! -x "$DL/appimagetool" ]; then
    log "Downloading appimagetool"
    curl -fsSL -o "$DL/appimagetool" "$APPIMAGETOOL_URL"
    chmod +x "$DL/appimagetool"
fi

#
# Freeze the python programs.  Like the windows build we freeze pop-fe2,
# pop-fe2-ps3 and pkg.py separately and then merge them into one directory.
#
log "Running pyinstaller"
SRC="$BUILD_DIR/src"
rm -rf "$SRC" "$BUILD_DIR/dist"
mkdir -p "$SRC"
# pop-fe2-ps3 imports pop-fe2 as "popfe2"
cp "$ROOT/pop-fe2.py" "$SRC/popfe2.py"

pyinst() {
    "$VENV/bin/pyinstaller" --noconfirm --log-level WARN \
        --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/work" \
        --specpath "$BUILD_DIR/spec" "$@"
}
pyinst --paths "$ROOT/PSL1GHT/tools/ps3py" "$ROOT/PSL1GHT/tools/ps3py/pkg.py"
pyinst --paths "$ROOT" --collect-all yt_dlp "$ROOT/pop-fe2.py"
pyinst --paths "$SRC" --paths "$ROOT" \
    --add-data "$ROOT/pop-fe2-ps3.ui:." \
    --hidden-import pygubu.builder.tkstdwidgets \
    --hidden-import pygubu.builder.ttkstdwidgets \
    --hidden-import pygubu.builder.widgets.pathchooserinput \
    --collect-all tkinterdnd2 --collect-all yt_dlp \
    "$ROOT/pop-fe2-ps3.py"

#
# Assemble the AppDir
#
log "Assembling $APPDIR"
rm -rf "$APPDIR"
mkdir -p "$BIN" "$LIBEXEC/bin" "$LIBEXEC/lib"
cp -a "$BUILD_DIR/dist/pop-fe2-ps3/." "$BIN/"
cp -a "$BUILD_DIR/dist/pop-fe2/." "$BIN/"
cp -a "$BUILD_DIR/dist/pkg/." "$BIN/"

# Libraries that must come from the host and never be bundled.
EXCLUDE_LIBS='^(linux-vdso|ld-linux|libc|libm|libdl|libpthread|librt|libresolv|libutil|libanl|libnsl)\.so'

# Copy a dynamically linked binary plus the libraries it needs into
# usr/lib/pop-fe2 and put a small wrapper script for it in usr/bin, where
# pop-fe2 looks for its helpers.  The wrapper also undoes any
# LD_LIBRARY_PATH that pyinstaller set up for the python side.
bundle_binary() {
    local src="$1" name
    name="$(basename "$src")"
    install -m 755 "$src" "$LIBEXEC/bin/$name"
    ldd "$src" | awk '/=> \// { print $1, $3 }' | while read -r soname path; do
        if ! [[ "$soname" =~ $EXCLUDE_LIBS ]]; then
            [ -e "$LIBEXEC/lib/$soname" ] || cp -L "$path" "$LIBEXEC/lib/$soname"
        fi
    done
    cat > "$BIN/$name" <<EOF
#!/bin/sh
LIB="\$(dirname "\$(readlink -f "\$0")")/../lib/pop-fe2"
LD_LIBRARY_PATH="\$LIB/lib\${LD_LIBRARY_PATH_ORIG:+:\$LD_LIBRARY_PATH_ORIG}" exec "\$LIB/bin/$name" "\$@"
EOF
    chmod 755 "$BIN/$name"
}

bundle_binary "$BUILD_DIR/atracdenc/atracdenc"
bundle_binary "$ROOT/make_npdata/Linux/make_npdata"

CHDMAN="$(command -v chdman || true)"
if [ -n "$CHDMAN" ] && [[ "$("$CHDMAN" help 2>&1 || true)" == *extractdvd* ]]; then
    log "Bundling $CHDMAN"
    bundle_binary "$CHDMAN"
else
    log "WARNING: no chdman with extractdvd support found, not bundling chdman"
fi

install -m 755 "$DL/ffmpeg" "$BIN/ffmpeg"

if ls "$ROOT"/crunch/bin/crunch*.exe >/dev/null 2>&1; then
    cp "$ROOT"/crunch/bin/crunch*.exe "$BIN/"
else
    log "WARNING: crunch/bin not found, manuals will need crunch.exe from \$PATH"
fi

cp "$ROOT/2P0001-PS2U10000_00-0000111122223333.rap" "$ROOT/SCEVMC0.VMC" "$BIN/"

install -m 755 "$ROOT/appimage/AppRun" "$APPDIR/AppRun"
cp "$ROOT/appimage/pop-fe2.desktop" "$APPDIR/"
cp "$ROOT/appimage/pop-fe2.svg" "$APPDIR/"
ln -s pop-fe2.svg "$APPDIR/.DirIcon"

#
# And pack it up
#
OUT="$OUTPUT_DIR/pop-fe2-$ARCH.AppImage"
log "Creating $OUT"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=$ARCH "$DL/appimagetool" --no-appstream "$APPDIR" "$OUT"
log "Done: $OUT"
