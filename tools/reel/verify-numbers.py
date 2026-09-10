#!/usr/bin/env python3
"""verify-numbers.py — pin every figure the narration says to a cursor position.

The rail's VOLUME and LIFESPAN blocks are windowed statistics: they describe the
seven days ending at the SCRUB CURSOR, not the seven days ending today. Read a
page a second after load and you get whatever the cursor was on while the first
frames were still settling, which is how two probes of the same instrument
produced "1,062 born last week, median 27.6h" and "79 born last week, median
11.0h" ten minutes apart.

Neither reading was wrong. One of them was of a different week.

So a number cannot go in a script until it is attached to a stated cursor, and
this prints the rail at both ends of the history plus the settled live value,
three times each, so a figure that moves is visibly one that moves.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Chrome  # noqa: E402

URL = "http://127.0.0.1:4517/app/swarm.html"

WANT = [
    ("alive at cursor", r"alive at cursor"),
    ("born, last 7d", r"born, last 7d(?: of cursor)?"),
    ("born, prior 7d", r"born, prior 7d"),
    ("trend", r"trend"),
    ("median, settled", r"median, settled"),
    ("p90, settled", r"p90, settled"),
    ("settled / born", r"settled / born"),
    ("agent smell", r"agent smell[^\n]*"),
    ("no signal", r"no signal"),
    ("artifacts fetched", r"artifacts fetched"),
]


def parse_rail(text: str) -> dict:
    """The rail renders as label line followed by value line."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = {}
    for label, pat in WANT:
        for i, ln in enumerate(lines):
            if re.fullmatch(pat, ln, re.I) and i + 1 < len(lines):
                out[label] = lines[i + 1]
                break
    return out


def snapshot(page) -> tuple[str, dict]:
    clock = page.eval("document.getElementById('clock').textContent")
    rail = page.eval("document.getElementById('rail').innerText")
    return clock, parse_rail(rail)


def main() -> None:
    subprocess.run(["hyprctl", "dispatch", "focusmonitor", "eDP-1"], capture_output=True)
    Chrome.FLAGS = Chrome.FLAGS + ["--ozone-platform=wayland",
                                   "--enable-features=UseOzonePlatform"]
    results = {}
    with Chrome(URL, width=1600, height=1000) as page:
        page.wait_for("document.body && document.getElementById('world')", 45)
        page.wait_for("window.SWARM_DATA && SWARM_DATA.artifacts.length > 0", 60)

        for name, key, vk, code in (("live (End)", "End", 35, "End"),
                                    ("start (Home)", "Home", 36, "Home")):
            page.key(key, code, vk)
            # Three reads a second apart: a value still settling shows itself.
            reads = []
            for _ in range(3):
                time.sleep(1.2)
                reads.append(snapshot(page))
            results[name] = reads

        page.key("End", "End", 35)
        time.sleep(3.0)
        results["live (End), settled 3s"] = [snapshot(page)]

    for name, reads in results.items():
        clock, vals = reads[-1]
        print(f"\n=== {name}\n  clock: {clock}")
        for k, _ in WANT:
            if k in vals:
                print(f"    {k:22s} {vals[k]}")
        for k, _ in WANT:
            seen = {r[1].get(k) for r in reads}
            seen.discard(None)
            if len(seen) > 1:
                print(f"    ! {k} moved while settling: {sorted(seen)}")


if __name__ == "__main__":
    main()
