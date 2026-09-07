#!/usr/bin/env bash
# Render the app/tray/favicon icons from the official Omarchy glyph.
# The mark is U+E900 in the "omarchy" icon font (used by the bar's menu button,
# BarWidget.qml: text "", fontFamily "omarchy"). We render from that font
# so the icon is pixel-faithful to the system mark, not a hand-drawn guess.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONT="$(fc-list 2>/dev/null | grep -i omarchy | head -1 | cut -d: -f1)"
GLYPH=$''
COLOR="${1:-#9ece6a}"   # Tokyo Night green

if [ -z "$FONT" ]; then
  echo "omarchy font not found (fc-list | grep omarchy) — keeping existing icons" >&2
  exit 0
fi

magick -background none -fill "$COLOR" -font "$FONT" -pointsize 200 \
  label:"$GLYPH" -trim +repage -resize 220x220 -gravity center \
  -extent 256x256 "$ROOT/app/omarchy-mark-256.png"
magick "$ROOT/app/omarchy-mark-256.png" -resize 128x128 "$ROOT/app/omarchy-logo.png"

ICONDIR="$HOME/.local/share/icons/hicolor/128x128/apps"
mkdir -p "$ICONDIR"
cp "$ROOT/app/omarchy-logo.png" "$ICONDIR/fix-everything-tracker.png"
echo "rendered omarchy mark → app/omarchy-mark-256.png, app/omarchy-logo.png, $ICONDIR/"
