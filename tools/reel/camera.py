#!/usr/bin/env python3
"""camera.py — turn a shot list into a per-frame camera path over recorded footage.

The grammar this implements is the one every good product demo has converged on:
hold wide, arrive on the thing being talked about, hold there while it is talked
about, leave. Authoring it means saying *when* to be somewhere, not how to get
there, so a shot names the moment it must have ARRIVED:

    {"t": 12.30, "rect": [1180, 240, 620, 300], "arrive": 0.45, "ease": "expo"}

The camera holds whatever it had until t-arrive, eases to `rect` so that it is
settled exactly at t, and stays until the next shot pulls it away. `t` is the
instant the voice says the word the shot is about, so a shot list can be written
straight off a transcript's word timestamps without anybody counting frames.

Rects are in SOURCE PIXELS, because that is what a browser hands you when you
ask an element where it is. Fitting them to a 9:16 or 1:1 delivery frame is this
module's job, not the author's — the same shot list renders to every aspect.

Two rules the fitting obeys, both learned the hard way:

  * A rect is a MINIMUM, never an exact frame. Fitting to an aspect only ever
    grows it, so the thing the shot is about cannot be cropped out by the
    delivery format. A 9:16 cut of a landscape UI grows the rect vertically
    until it fits, and if that runs past the top of the source it slides down
    rather than clipping the subject.
  * A camera that leaves the source frame shows black. Clamping runs after
    aspect-fitting and before easing, so no interpolated frame between two legal
    rects can be illegal — a rect is clamped at both ends of the move, and the
    interpolation of two in-bounds rects is in bounds.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


# --------------------------------------------------------------------- easing
#
# Easing is on the CAMERA, not on the content, so the curves that read well are
# the ones that decelerate hard: the eye tolerates a fast departure and needs a
# slow arrival. Anything with overshoot (back, elastic) reads as a toy and is
# deliberately absent.

def _ease_linear(p: float) -> float:
    return p


def _ease_expo(p: float) -> float:
    # The default. Nearly all of the distance is covered in the first third,
    # which is what makes a zoom feel like a cut that changed its mind.
    return 1.0 if p >= 1.0 else 1.0 - pow(2.0, -10.0 * p)


def _ease_cubic(p: float) -> float:
    return 1.0 - pow(1.0 - p, 3.0)


def _ease_sine(p: float) -> float:
    # For slow drifts across a wide shot, where expo's snap would read as a jolt.
    return math.sin((p * math.pi) / 2.0)


EASES = {
    "linear": _ease_linear,
    "expo": _ease_expo,
    "cubic": _ease_cubic,
    "sine": _ease_sine,
}


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.w, self.h]

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0


def fit_aspect(r: Rect, aspect: float) -> Rect:
    """Grow `r` about its centre until it matches `aspect` (w/h). Never shrinks.

    Growing rather than cropping is the whole point: the author said "this
    element matters", and a delivery format is not allowed to disagree.
    """
    cur = r.w / r.h
    if abs(cur - aspect) < 1e-9:
        return Rect(r.x, r.y, r.w, r.h)
    if cur < aspect:
        w = r.h * aspect
        return Rect(r.cx - w / 2.0, r.y, w, r.h)
    h = r.w / aspect
    return Rect(r.x, r.cy - h / 2.0, r.w, h)


def clamp(r: Rect, sw: float, sh: float) -> Rect:
    """Keep the camera inside the source. Shrink only as a last resort.

    Sliding first and shrinking second matters: a rect nudged off the top of the
    frame should come back down at the same magnification, because a shot that
    silently zooms out to stay legal breaks the rhythm of the shot list around
    it — the next shot's `arrive` was written against a magnification that no
    longer holds.
    """
    w = min(r.w, sw)
    h = min(r.h, sh)
    # Shrinking to fit must preserve aspect, or the delivery scale distorts.
    if w != r.w or h != r.h:
        k = min(w / r.w, h / r.h)
        w, h = r.w * k, r.h * k
    x = min(max(r.x, 0.0), sw - w)
    y = min(max(r.y, 0.0), sh - h)
    return Rect(x, y, w, h)


class Camera:
    """The shot list, resolved to a rect for any time."""

    def __init__(self, shots: list[dict], source_w: int, source_h: int, aspect: float):
        if not shots:
            raise ValueError("a shot list needs at least one shot")
        self.sw, self.sh = float(source_w), float(source_h)
        self.aspect = aspect

        self.shots = []
        for s in sorted(shots, key=lambda s: s["t"]):
            r = Rect(*[float(v) for v in s["rect"]])
            r = clamp(fit_aspect(r, aspect), self.sw, self.sh)
            self.shots.append({
                "t": float(s["t"]),
                "rect": r,
                "arrive": float(s.get("arrive", 0.45)),
                "ease": EASES[s.get("ease", "expo")],
                "label": s.get("label", ""),
            })

        # The first shot is where the camera already is when the clip opens; a
        # move onto the opening frame would be a move from nowhere.
        self.shots[0]["arrive"] = 0.0

    def at(self, t: float) -> Rect:
        prev = self.shots[0]
        for s in self.shots:
            if t < s["t"] - s["arrive"]:
                break
            prev_candidate = s
            if s["t"] - s["arrive"] <= t < s["t"]:
                # Mid-move: interpolate from whatever the camera held before it.
                start = self._settled_before(s)
                p = (t - (s["t"] - s["arrive"])) / s["arrive"] if s["arrive"] > 0 else 1.0
                return self._lerp(start, s["rect"], s["ease"](min(max(p, 0.0), 1.0)))
            prev = prev_candidate
        return prev["rect"]

    def _settled_before(self, shot: dict) -> Rect:
        i = self.shots.index(shot)
        return self.shots[i - 1]["rect"] if i > 0 else shot["rect"]

    @staticmethod
    def _lerp(a: Rect, b: Rect, p: float) -> Rect:
        return Rect(
            a.x + (b.x - a.x) * p,
            a.y + (b.y - a.y) * p,
            a.w + (b.w - a.w) * p,
            a.h + (b.h - a.h) * p,
        )

    def sample(self, fps: float, duration: float) -> list[Rect]:
        n = int(round(duration * fps))
        return [self.at(i / fps) for i in range(n)]


def load(path: str, aspect: float) -> tuple[Camera, dict]:
    with open(path) as fh:
        doc = json.load(fh)
    src = doc["source"]
    return Camera(doc["shots"], src["w"], src["h"], aspect), doc


if __name__ == "__main__":
    import sys

    cam, doc = load(sys.argv[1], 9 / 16)
    for i in range(0, 40):
        t = i * 0.25
        r = cam.at(t)
        print(f"{t:6.2f}  x={r.x:7.1f} y={r.y:7.1f} w={r.w:7.1f} h={r.h:7.1f}")
