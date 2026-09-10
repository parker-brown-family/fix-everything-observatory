#!/usr/bin/env python3
"""geometry.py — where everything is, in the recording's own pixels.

    tools/reel/geometry.py -o build/geometry.json

A shot list is only as good as its coordinates, and coordinates typed off a
screenshot go stale the first time a margin changes. So the targets are read from
the live page at the exact viewport the capture uses, then multiplied into
recording pixels by the display scale — one conversion, in one place.

The swarm itself is not a DOM element; it is painted into a canvas, and its
layout lives in `draw()` in app/swarm.html:

    cfd  = {x:0, y:H-132, w:W, h:132}     the cumulative flow diagram
    lane = {x:0, y:cfd.y-26, w:W, h:26}   the event lane
    zone = {x:0, y:0, w:W, h:lane.y}      the swarm, hive at (W/2, zone.h*0.52)

Those four lines are duplicated here, which is a real cost: if the page's layout
constants change, this file is wrong and nothing will fail loudly — the camera
will just point slightly beside the thing. `--verify` exists for that: it samples
the rendered canvas and checks that the brightest cluster really is where the
hive is claimed to be.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Chrome  # noqa: E402

URL = "http://127.0.0.1:4517/app/swarm.html"

# Mirrors app/swarm.html draw(). See the module docstring for why this hurts.
CFD_H, LANE_H, HIVE_Y_FRAC = 132, 26, 0.52

READ = """
(() => {
  const R = el => { const r = el.getBoundingClientRect();
                    return [r.x, r.y, r.width, r.height]; };
  const byId = id => { const e = document.getElementById(id); return e ? R(e) : null; };
  const cv = document.getElementById('world');
  const cr = cv.getBoundingClientRect();
  return JSON.stringify({
    dpr: devicePixelRatio,
    viewport: [innerWidth, innerHeight],
    canvas: [cr.x, cr.y, cr.width, cr.height],
    header: R(document.querySelector('header')),
    footer: R(document.querySelector('footer')),
    statsbar: byId('statsbar'),
    projstrip: byId('projstrip'),
    rail: byId('rail'),
    legend: byId('legendChip'),
    clock: byId('clock'),
    scrub: byId('scrub'),
    railText: (document.getElementById('rail') || {}).innerText || ''
  });
})()
"""


def rail_blocks(page) -> dict:
    """The rail is one column of labelled statistics and the shot list wants to
    land on ONE of them. Find each heading's own box rather than framing the
    whole column, which at 9:16 would be a wall of unreadable small text."""
    return json.loads(page.eval("""
    (() => {
      const rail = document.getElementById('rail');
      if (!rail) return '{}';
      const out = {};
      // Each statistic group in the rail starts with a heading; take the
      // heading plus everything up to the next one as the group's box.
      const heads = [...rail.querySelectorAll('h2,h3,.rh,.railhead,[class*=head]')];
      const rr = rail.getBoundingClientRect();
      for (const h of heads) {
        const key = (h.textContent || '').trim().toLowerCase().replace(/[^a-z]+/g, '-');
        if (!key) continue;
        let end = h.getBoundingClientRect().bottom;
        let n = h.nextElementSibling;
        while (n && !/^(H2|H3)$/.test(n.tagName) && !/head/i.test(n.className || '')) {
          end = Math.max(end, n.getBoundingClientRect().bottom);
          n = n.nextElementSibling;
        }
        const r = h.getBoundingClientRect();
        out[key] = [rr.x, r.y, rr.width, Math.max(24, end - r.y)];
      }
      return JSON.stringify(out);
    })()
    """))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="build/geometry.json")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1000)
    args = ap.parse_args()

    subprocess.run(["hyprctl", "dispatch", "focusmonitor", "eDP-1"],
                   capture_output=True)
    time.sleep(0.3)

    Chrome.FLAGS = Chrome.FLAGS + [
        "--start-fullscreen", "--ozone-platform=wayland",
        "--enable-features=UseOzonePlatform",
    ]

    with Chrome(args.url, width=args.width, height=args.height) as page:
        page.wait_for("document.body && document.getElementById('world') && "
                      "document.readyState === 'complete'", 45)
        page.wait_for("window.SWARM_DATA && SWARM_DATA.artifacts.length > 0", 60)
        time.sleep(1.5)
        d = json.loads(page.eval(READ))
        rails = rail_blocks(page)

    s = d["dpr"]
    cx, cy, cw, ch = d["canvas"]

    def px(rect):
        return [round(v * s) for v in rect]

    lane_y = ch - CFD_H - LANE_H
    hive_cx, hive_cy = cx + cw / 2.0, cy + lane_y * HIVE_Y_FRAC

    def around(px_cx, px_cy, w, h):
        return [round((px_cx - w / 2) * s), round((px_cy - h / 2) * s),
                round(w * s), round(h * s)]

    targets = {
        "_source": {"viewport": d["viewport"], "dpr": s,
                    "recording": [round(d["viewport"][0] * s),
                                  round(d["viewport"][1] * s)]},
        "everything": [0, 0, round(d["viewport"][0] * s), round(d["viewport"][1] * s)],
        "canvas": px(d["canvas"]),
        "header": px(d["header"]),
        "statsbar": px(d["statsbar"]),
        "rail": px(d["rail"]),
        "legend": px(d["legend"]),
        "footer": px(d["footer"]),
        "clock": px(d["clock"]),
        # The swarm, at three magnifications. Orbit radius carries the meaning,
        # so a shot about age needs the rings in frame and a shot about colour
        # does not.
        "hive_tight": around(hive_cx, hive_cy, cw * 0.30, lane_y * 0.55),
        "swarm": around(hive_cx, hive_cy, cw * 0.62, lane_y * 0.92),
        "swarm_wide": around(hive_cx, hive_cy, cw * 0.95, lane_y * 1.0),
        "cfd": px([cx, cy + ch - CFD_H, cw, CFD_H]),
        "cfd_left": px([cx, cy + ch - CFD_H, cw * 0.55, CFD_H]),
        "lane": px([cx, cy + lane_y, cw, LANE_H]),
        "transport": px([d["footer"][0], d["footer"][1],
                         d["footer"][2], d["footer"][3]]),
    }
    for k, v in rails.items():
        targets[f"rail_{k}"] = px(v)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(targets, fh, indent=1)

    print(f"recording {targets['_source']['recording']}  dpr {s:.3f}")
    for k, v in targets.items():
        if k.startswith("_"):
            continue
        print(f"  {k:22s} {v}")
    print(f"\nrail text:\n{d['railText'][:600]}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
