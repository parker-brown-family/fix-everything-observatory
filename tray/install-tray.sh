#!/usr/bin/env bash
# Install the Fix-Everything Tracker launch surfaces:
#  1. SNI tray icon (omarchy spiral) in the Omarchy quickshell bar — started now.
#  2. Desktop entry so app launchers can start it.
# Autostart on login is NOT wired automatically (hyprland config edits raise the
# CRT banner on this box) — the exec-once line is printed for Parker to adopt.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1 — desktop entry
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/fix-everything-tracker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Fix-Everything Tracker
Comment=Watch the Omarchy repair swarm heal the repo
Exec=$ROOT/bin/fix-everything-tracker open
Icon=$ROOT/app/omarchy-logo.png
Terminal=false
Categories=Development;Monitor;
EOF
echo "desktop entry: $APPS/fix-everything-tracker.desktop"

# 1b — hicolor theme icon (the SNI item's IconName resolves through this;
# more reliable than the ARGB pixmap fallback across tray hosts)
ICONDIR="$HOME/.local/share/icons/hicolor/128x128/apps"
mkdir -p "$ICONDIR"
cp "$ROOT/app/omarchy-logo.png" "$ICONDIR/fix-everything-tracker.png"
echo "theme icon: $ICONDIR/fix-everything-tracker.png"
# To keep the icon ALWAYS visible (not in the hover drawer), pin it in
# ~/.config/omarchy/shell.json — bar.layout.right, the omarchy.tray entry:
#   { "id": "omarchy.tray", "pinned": ["fix-everything-tracker"] }

# 2 — tray applet, single instance, survives this shell
if pgrep -f "tray/fix-tracker-sni.py" >/dev/null 2>&1; then
  echo "tray applet: already running"
else
  setsid -f python3 "$ROOT/tray/fix-tracker-sni.py" >>"$ROOT/data/tray.log" 2>&1
  sleep 0.7
  if pgrep -f "tray/fix-tracker-sni.py" >/dev/null 2>&1; then
    echo "tray applet: started (icon should be in the omarchy bar tray)"
  else
    echo "tray applet: FAILED — see $ROOT/data/tray.log" >&2
  fi
fi

echo
echo "to autostart on login, add to hyprland config yourself:"
echo "exec-once = $ROOT/bin/fix-everything-tracker tray"
