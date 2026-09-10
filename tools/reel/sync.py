#!/usr/bin/env python3
"""sync.py — find the frame the take actually starts on, and how long it stays clean.

    tools/reel/sync.py build/take02.mp4

The recorder and the page cannot be started on the same instant, so capture.py
holds a black card over the page through the lead-in and drops it on the first
frame that counts. This finds that frame.

`blackdetect` was the obvious tool and it does not work here: Omarchy composites
a CRT glass shader over the whole screen, so the "black" card records as a dark
red-brown gradient that never crosses any pixel threshold. Mean luma does work,
because the difference between the curtain and the lit interface is enormous
even after the shader — the curtain sits near 4/255 and the running page near 25.
The threshold is therefore derived from the take's own two levels rather than
written down, so it survives a theme change.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys


def luma_series(path: str, upto: float | None = None) -> list[tuple[float, float]]:
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if upto:
        cmd += ["-t", str(upto)]
    cmd += ["-i", path, "-vf",
            "scale=160:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
            "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stderr
    series, t = [], None
    for line in out.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", line)
        if m and t is not None:
            series.append((t, float(m.group(1))))
    return series


def find_start(series: list[tuple[float, float]]) -> tuple[float, float, float]:
    """The first sustained rise out of the curtain."""
    vals = sorted(v for _, v in series)
    if not vals:
        raise SystemExit("no frames measured")
    low = vals[len(vals) // 20]              # the curtain
    high = vals[-len(vals) // 5]             # the running page
    if high - low < 3.0:
        raise SystemExit(
            f"no curtain found (luma spans {low:.1f}..{high:.1f}) — was this take "
            "recorded by capture.py?")
    gate = low + (high - low) * 0.35
    for i, (t, v) in enumerate(series):
        if v > gate and all(v2 > gate for _, v2 in series[i:i + 6]):
            return t, low, high
    raise SystemExit("the curtain never lifted")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    series = luma_series(args.take)
    start, low, high = find_start(series)

    # The tail: the curtain goes back up at the end, so the last sustained fall
    # is where usable footage stops.
    gate = low + (high - low) * 0.35
    end = series[-1][0]
    for t, v in reversed(series):
        if v > gate:
            end = t
            break

    beats_path = args.take.rsplit(".", 1)[0] + ".beats.json"
    intrusions = []
    try:
        with open(beats_path) as fh:
            intrusions = json.load(fh).get("intrusions", [])
    except OSError:
        pass
    # An intrusion time is measured from the curtain drop, which is exactly the
    # clock this file establishes — so it converts straight into a take offset.
    clean_until = end - start
    for i in intrusions:
        clean_until = min(clean_until, float(i["t"]))

    doc = {
        "take": args.take,
        "start": round(start, 3),
        "end": round(end, 3),
        "usable": round(clean_until, 3),
        "curtain_luma": round(low, 2),
        "page_luma": round(high, 2),
        "intrusions": intrusions,
    }
    if args.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"curtain drops at {start:.3f}s (luma {low:.1f} -> {high:.1f})")
        print(f"last lit frame  {end:.3f}s")
        print(f"usable          {clean_until:.2f}s of footage from the drop")
        if intrusions:
            print("  ! cut short by: " + ", ".join(
                f"{i['t']}s {i.get('class')}" for i in intrusions))
    return doc


if __name__ == "__main__":
    main()
