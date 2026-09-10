#!/usr/bin/env bash
# Re-shoot until a take survives the desktop it was shot on.
#
# Several agents drive this machine at once, and any of them raising a window
# lands it in the recording. capture.py notices and exits 3; this keeps going
# until one comes back clean, which is cheaper than a human checking contact
# sheets. Any other exit code is the rig being broken, and retrying that would
# just hide it.
set -uo pipefail
cd "$(dirname "$0")"

OUT=${OUT:-build/take.mp4}
DURATION=${DURATION:-42}
TRIES=${TRIES:-1}

for i in $(seq 1 "$TRIES"); do
  echo "=== attempt $i/$TRIES"
  rm -f "${OUT%.mp4}.mp4" "${OUT%.mp4}.beats.json"
  python3 capture.py --duration "$DURATION" --rate 1 --out "$OUT" "$@" 2>&1 | tail -5
  rc=${PIPESTATUS[0]}
  case $rc in
    0) echo "clean take -> $OUT"; exit 0 ;;
    3) echo "  spoiled by the desktop, retrying"; sleep 2 ;;
    4) echo "no consent — a human at the machine must pass --i-am-watching" >&2; exit 4 ;;
    *) echo "capture failed (exit $rc) — not a desktop problem, stopping" >&2; exit "$rc" ;;
  esac
done
echo "no clean take in $TRIES attempts — the desktop is too busy right now" >&2
exit 1
