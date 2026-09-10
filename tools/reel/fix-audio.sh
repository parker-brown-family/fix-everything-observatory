#!/usr/bin/env bash
# Repair a screencast's voice track to social-delivery loudness.
#
# The failure this exists for: a capture that measures -24 LUFS integrated is
# not silent, it is ten units under what YouTube, X and TikTok normalise to.
# Played back at any normal system volume it reads as "dead quiet", and the
# instinct — raise the master gain — clips the one stray transient that is
# already sitting at -1 dBTP.
#
# Two passes, because loudnorm's single-pass mode guesses at the programme it
# has not heard yet and lands several units off.
set -euo pipefail

IN=${1:?usage: fix-audio.sh <input> [output]}
OUT=${2:-${IN%.*}-audiofix.mp4}
TARGET_I=${TARGET_I:--14}     # X / YouTube / TikTok all normalise near here
TARGET_TP=${TARGET_TP:--1.5}  # headroom for the lossy transcode on upload
TARGET_LRA=${TARGET_LRA:-9}   # a talking head does not need 26 LU of range

# 80 Hz high-pass kills desk rumble; the de-esser runs BEFORE the gain stage
# because +10 dB applied to an MV7's 6-8 kHz sibilance is the ear-bleed.
PRE="highpass=f=80,deesser=i=0.35:m=0.5:f=0.35,acompressor=threshold=-24dB:ratio=3:attack=5:release=120"

echo "== pass 1: measure ==" >&2
MEASURE=$(ffmpeg -hide_banner -nostats -i "$IN" -map 0:a \
  -af "${PRE},loudnorm=I=${TARGET_I}:TP=${TARGET_TP}:LRA=${TARGET_LRA}:print_format=json" \
  -f null - 2>&1 | sed -n '/^{/,/^}/p')

get() { printf '%s' "$MEASURE" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p"; }
MI=$(get input_i); MTP=$(get input_tp); MLRA=$(get input_lra)
MTHRESH=$(get input_thresh); MOFF=$(get target_offset)
echo "measured: I=${MI} TP=${MTP} LRA=${MLRA} thresh=${MTHRESH} offset=${MOFF}" >&2

echo "== pass 2: render ==" >&2
ffmpeg -hide_banner -nostats -y -i "$IN" \
  -map 0:v -map 0:a -c:v copy \
  -af "${PRE},loudnorm=I=${TARGET_I}:TP=${TARGET_TP}:LRA=${TARGET_LRA}:measured_I=${MI}:measured_TP=${MTP}:measured_LRA=${MLRA}:measured_thresh=${MTHRESH}:offset=${MOFF}:linear=true,alimiter=limit=0.92:level=disabled,aresample=48000" \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  "$OUT" 2>&1 | tail -3

echo "== verify ==" >&2
ffmpeg -hide_banner -nostats -i "$OUT" -map 0:a -af ebur128=peak=true -f null - 2>&1 \
  | grep -A8 'Integrated loudness' | head -14
echo "wrote $OUT" >&2
