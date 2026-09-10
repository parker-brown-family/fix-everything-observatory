#!/usr/bin/env python3
"""render.py — cut one recording into the platform reels, camera and captions included.

    tools/reel/render.py reel.json                 # every target in the spec
    tools/reel/render.py reel.json --only vertical
    tools/reel/render.py reel.json --preview 6     # first 6s only, fast encode

WHAT THIS IS FOR

A screen recording of a dense landscape dashboard is unwatchable on a phone: at
1080 wide, a 2560-wide UI arrives at 42% scale and every number in it is
illegible. The fix the whole short-form format has converged on is a camera —
hold wide, arrive on the thing being talked about, hold, leave — and the thing
that makes it feel authored rather than mechanical is that the arrival lands on
the WORD. So a shot names the moment it must have arrived, in the same clock the
transcript uses, and everything else is derived.

HOW THE CAMERA IS ACTUALLY DRAWN

Every target aspect gets a WORLD: the source footage composited onto a canvas of
that aspect, on the reel's background colour. The camera is then a plain crop
over the world, which collapses two cases that would otherwise need different
filter graphs — a shot showing the whole UI (impossible as a crop of a 16:10
source into a 9:16 frame) is just the shot whose rect is the entire world.

The crop is animated by feeding ffmpeg a `sendcmd` script with one entry per
frame. `crop` accepts w/h/x/y as runtime commands, and a fixed-size `scale`
downstream absorbs the frame size changing underneath it. Rects are rounded to
even pixels because an odd crop against yuv420p chroma siting shimmers.

WHAT WILL LOOK BAD, AND IS CHECKED

Cropping 700 source pixels into a 1080-wide delivery is a 1.54x upscale, and on
text it is visibly soft. `--check` warns for any shot whose rect is narrower
than the delivery width; the fix is to author a wider rect, not to sharpen in
post.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camera import Camera, Rect, clamp, fit_aspect  # noqa: E402


# ------------------------------------------------------------------- helpers

def run(cmd: list[str], quiet: bool = True) -> None:
    proc = subprocess.run(cmd, capture_output=quiet, text=True)
    if proc.returncode != 0:
        if quiet:
            sys.stderr.write(proc.stderr or "")
        raise SystemExit(f"ffmpeg failed ({proc.returncode}): {shlex.join(cmd[:8])} …")


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {
        "w": int(st["width"]),
        "h": int(st["height"]),
        "fps": float(num) / float(den),
        "duration": float(d["format"]["duration"]),
    }


def even(v: float) -> int:
    i = int(round(v))
    return i - (i % 2)


# --------------------------------------------------------------------- world
#
# The source, letterboxed onto a canvas of the delivery aspect. Shot rects are
# authored in SOURCE pixels, so they need translating into world pixels — which
# is the only coordinate change in the whole pipeline and therefore the only
# place an off-by-one can put the camera somewhere nobody asked for.

class World:
    def __init__(self, src_w: int, src_h: int, aspect: float, headroom: float = 1.0):
        self.src_w, self.src_h = src_w, src_h
        self.aspect = aspect
        # Grow the source box to the delivery aspect. `headroom` grows it further
        # so a vertical cut has empty canvas above and below the UI for captions
        # to sit on without covering anything.
        box = fit_aspect(Rect(0, 0, src_w, src_h * headroom), aspect)
        self.w, self.h = even(box.w), even(box.h)
        self.ox = even((self.w - src_w) / 2)
        self.oy = even((self.h - src_h) / 2)

    def to_world(self, r: Rect) -> Rect:
        return Rect(r.x + self.ox, r.y + self.oy, r.w, r.h)

    @property
    def full(self) -> Rect:
        return Rect(0, 0, self.w, self.h)


# ------------------------------------------------------------------ captions
#
# The caption style is deliberately not a transcript. Three words at a time,
# large, centred in the canvas margin rather than over the UI, with the word
# currently being spoken carried in the accent colour. 85% of feed video is
# watched muted, so these are the primary channel and the voice is the backup —
# which is the opposite of how a demo voiceover is usually written.

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{font},{size},{active},{idle},{outline},&H80000000,-1,0,0,0,100,100,0,0,{bs},{ow},{sh},{align},{ml},{mr},{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def ass_colour(hex_rgb: str, opacity: float = 1.0) -> str:
    """#RRGGBB -> &HAABBGGRR. ASS is BGR, and its alpha byte is TRANSPARENCY —
    00 is fully opaque, FF fully invisible — so it is the inverse of every other
    alpha you will type that day."""
    s = hex_rgb.lstrip("#")
    r, g, b = s[0:2], s[2:4], s[4:6]
    a = round((1.0 - max(0.0, min(1.0, opacity))) * 255)
    return f"&H{a:02X}{b}{g}{r}".upper()


def chunk_words(words: list[dict], max_words: int, max_span: float) -> list[list[dict]]:
    """Group a bare word stream into caption cards.

    Only used when the narration did not come with cards of its own — a
    transcript of a recorded take, say. A card breaks on the word budget, the
    time budget, or a real pause, and the pause rule matters most.
    """
    cards, cur = [], []
    for w in words:
        if cur:
            gap = w["t"] - (cur[-1]["t"] + cur[-1]["d"])
            span = (w["t"] + w["d"]) - cur[0]["t"]
            if len(cur) >= max_words or span > max_span or gap > 0.28:
                cards.append(cur)
                cur = []
        cur.append(w)
    if cur:
        cards.append(cur)
    return cards


def split_card(card_words: list[dict], max_words: int) -> list[list[dict]]:
    """Break one authored card into screen-sized lines, never across cards.

    The cue file already decided where the ideas are — one per card — and a
    chunker that re-cuts the flat word stream throws that away, producing
    "open bug. Further" and "dot is an": lines that end mid-clause and start
    mid-clause, so the reader is always half a thought behind. Splitting inside
    a card and never across one keeps the authored boundaries, which are the
    only ones that mean anything.
    """
    if len(card_words) <= max_words:
        return [card_words]
    # Prefer to break after a word that closes a clause; fall back to even
    # halves so no line is a single orphan word.
    n = len(card_words)
    parts = max(2, -(-n // max_words))
    size = -(-n // parts)
    out, i = [], 0
    while i < n:
        j = min(n, i + size)
        # nudge the break to just after punctuation, if one is close by
        for k in range(j, min(n, j + 2)):
            if k > i and card_words[k - 1]["w"].rstrip()[-1:] in ",.;:—?!":
                j = k
                break
        out.append(card_words[i:j])
        i = j
    return out


def build_ass(spec: dict, target: dict, world: World, out_path: str) -> None:
    cap = {**spec.get("captions", {}), **target.get("captions", {})}
    words = spec.get("words") or []
    if not words or not cap.get("enabled", True):
        with open(out_path, "w") as fh:
            fh.write(ASS_HEADER.format(
                w=target["w"], h=target["h"], font=cap.get("font", "Noto Sans"),
                size=48, active=ass_colour("#ffffff"), idle=ass_colour("#ffffff"),
                outline=ass_colour("#000000"), ow=3, bs=1, sh=0,
                align=2, ml=40, mr=40, mv=60))
        return

    # A caption is sized against the frame WIDTH, not its height. At 1080 wide a
    # monospace face renders about 1080/(size*0.6) characters per line, so a
    # height-derived default put ~99px type on screen and three words ran off
    # both edges with WrapStyle 2 refusing to break them.
    size = cap.get("size") or int(target["w"] * 0.050)
    active = ass_colour(cap.get("active", "#00e5ff"))
    idle = ass_colour(cap.get("idle", "#ffffff"))

    # A caption over a dashboard has to survive landing on a wall of small text.
    # An outline alone does not: the letterforms stay legible while the line as a
    # whole disappears into the numbers behind it. A box does, and BorderStyle 3
    # draws one in the outline colour with `Outline` as its padding.
    if cap.get("box", True):
        bs, sh = 3, 0
        outline = ass_colour(cap.get("box_colour", "#04070d"),
                             cap.get("box_opacity", 0.72))
        ow = cap.get("box_pad", 10)
    else:
        bs, sh = 1, 0
        outline = ass_colour(cap.get("outline", "#04070d"))
        ow = cap.get("outline_width", 4)

    lines = [ASS_HEADER.format(
        w=target["w"], h=target["h"],
        font=cap.get("font", "JetBrainsMono Nerd Font"),
        size=size, active=idle, idle=active, outline=outline,
        ow=ow, bs=bs, sh=sh,
        align=cap.get("align", 2),
        ml=cap.get("margin_x", 60), mr=cap.get("margin_x", 60),
        mv=cap.get("margin_v") or int(target["h"] * 0.09),
    )]

    mw = cap.get("max_words", 3)
    authored = spec.get("cards")
    if authored:
        cards = [line for c in authored for line in split_card(c["words"], mw)]
    else:
        cards = chunk_words(words, mw, cap.get("max_span", 1.7))
    for i, card in enumerate(cards):
        start = card[0]["t"]
        end = card[-1]["t"] + card[-1]["d"]
        # A card that vanishes the instant the last syllable ends reads as a
        # flicker, so it holds into the gap. It may never hold INTO the next
        # card: two cards alive at once draw on top of each other, which is
        # illegible and looks like a rendering fault rather than a timing one.
        end += min(0.34, max(0.0, cap.get("hold", 0.34)))
        if i + 1 < len(cards):
            end = min(end, cards[i + 1][0]["t"] - 0.04)
        if end <= start:
            end = start + 0.2
        body = []
        # A short scale-pop on entry. 90ms — long enough to register as motion,
        # short enough that it is over before the word is.
        body.append(r"{\fscx88\fscy88\t(0,90,\fscx100\fscy100)}")
        for w in card:
            cs = max(1, int(round(w["d"] * 100)))
            body.append("{\\k%d}%s " % (cs, w["w"].replace("{", "(").replace("}", ")")))
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Pop,,0,0,0,,"
            + "".join(body).rstrip() + "\n")

    with open(out_path, "w") as fh:
        fh.writelines(lines)


# ------------------------------------------------------------------- camera

def write_sendcmd(cam: Camera, world: World, fps: float, duration: float,
                  path: str, min_w: int) -> list[str]:
    warnings, n = [], int(round(duration * fps))
    narrow = 0
    with open(path, "w") as fh:
        for i in range(n):
            t = i / fps
            r = clamp(cam.at(t), world.w, world.h)
            w, h = even(r.w), even(r.h)
            w = max(2, min(w, world.w))
            h = max(2, min(h, world.h))
            x = max(0, min(even(r.x), world.w - w))
            y = max(0, min(even(r.y), world.h - h))
            if w < min_w:
                narrow += 1
            fh.write(f"{t:.5f} crop w {w}, crop h {h}, crop x {x}, crop y {y};\n")
    if narrow:
        warnings.append(
            f"{narrow} of {n} frames crop narrower than the {min_w}px delivery width — "
            "those are upscaled and will look soft on text")
    return warnings


# ------------------------------------------------------------------- render

def render_target(spec: dict, target: dict, src: dict, args) -> str:
    aspect = target["w"] / target["h"]
    headroom = target.get("headroom", 1.0)
    world = World(src["w"], src["h"], aspect, headroom)

    shots = []
    for s in spec["shots"]:
        override = (s.get("per_target") or {}).get(target["name"], {})
        rect = override.get("rect", s.get("rect"))
        if rect == "full" or rect is None:
            wr = world.full
        else:
            wr = world.to_world(Rect(*[float(v) for v in rect]))
        shots.append({
            "t": s["t"], "rect": wr.as_list(),
            "arrive": override.get("arrive", s.get("arrive", 0.45)),
            "ease": override.get("ease", s.get("ease", "expo")),
            "label": s.get("label", ""),
        })

    fps = float(spec.get("fps") or src["fps"])
    duration = float(args.preview or spec.get("duration") or src["duration"])
    cam = Camera(shots, world.w, world.h, aspect)

    tmp = tempfile.mkdtemp(prefix="reel-")
    cmds = os.path.join(tmp, "cam.sendcmd")
    ass = os.path.join(tmp, "cap.ass")
    warns = write_sendcmd(cam, world, fps, duration, cmds, target["w"])
    build_ass(spec, target, world, ass)
    for w in warns:
        print(f"  ! {target['name']}: {w}", file=sys.stderr)

    bg = spec.get("background", "#05070c")
    out = os.path.join(spec["out_dir"], f"{spec['slug']}-{target['name']}.mp4")
    os.makedirs(spec["out_dir"], exist_ok=True)

    first = clamp(cam.at(0), world.w, world.h)
    chain = (
        f"[0:v]fps={fps:g},"
        f"pad={world.w}:{world.h}:{world.ox}:{world.oy}:color={bg},"
        f"sendcmd=f={shlex.quote(cmds)},"
        f"crop=w={even(first.w)}:h={even(first.h)}:x={even(first.x)}:y={even(first.y)},"
        f"scale={target['w']}:{target['h']}:flags=lanczos,"
        f"setsar=1,format=yuv420p[cam];"
        f"[cam]ass={shlex.quote(ass)}[v]"
    )

    # The take's own clock starts when the curtain drops, not when the recorder
    # did; sync.py measures that offset. Seeking before -i makes t=0 in every
    # expression below mean the first frame that counts.
    seek = float(spec.get("source_start") or 0.0)
    cmd = ["ffmpeg", "-y", "-v", "warning"]
    if seek:
        cmd += ["-ss", f"{seek:g}"]
    cmd += ["-i", spec["source"]]
    has_audio = bool(spec.get("audio_from_source", True)) and not target.get("silent")
    if spec.get("audio"):
        cmd += ["-i", spec["audio"]]

    cmd += ["-t", f"{duration:g}", "-filter_complex", chain, "-map", "[v]"]

    if target.get("silent") or not has_audio and not spec.get("audio"):
        cmd += ["-an"]
    else:
        a_in = "1:a" if spec.get("audio") else "0:a"
        # -14 LUFS is where every feed normalises. Delivering under it is the
        # single most common reason a demo reel sounds quiet next to everything
        # around it, and no viewer reaches for the volume slider to fix you.
        cmd += ["-map", a_in, "-af",
                "loudnorm=I=-14:TP=-1.5:LRA=9,alimiter=limit=0.92:level=disabled",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]

    preset = "veryfast" if args.preview else target.get("preset", "slow")
    crf = 26 if args.preview else target.get("crf", 19)
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-g", str(int(fps * 2)), out]

    run(cmd)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--preview", type=float, default=0.0,
                    help="render only the first N seconds, fast")
    ap.add_argument("--check", action="store_true", help="validate, render nothing")
    args = ap.parse_args()

    with open(args.spec) as fh:
        spec = json.load(fh)
    base = os.path.dirname(os.path.abspath(args.spec))
    for key in ("source", "audio", "out_dir", "words_file"):
        if spec.get(key):
            spec[key] = os.path.normpath(os.path.join(base, spec[key]))

    if spec.get("words_file") and not spec.get("words"):
        with open(spec["words_file"]) as fh:
            doc = json.load(fh)
        spec["words"] = doc["words"]
        spec.setdefault("cards", doc.get("cards"))

    src = probe(spec["source"])
    print(f"source {src['w']}x{src['h']} @{src['fps']:g}fps  {src['duration']:.2f}s")

    targets = [t for t in spec["targets"]
               if not args.only or t["name"] in args.only]
    if not targets:
        raise SystemExit(f"no target matched {args.only}")

    for t in targets:
        if args.check:
            world = World(src["w"], src["h"], t["w"] / t["h"], t.get("headroom", 1.0))
            print(f"{t['name']:10s} {t['w']}x{t['h']}  world {world.w}x{world.h} "
                  f"offset +{world.ox}+{world.oy}")
            continue
        out = render_target(spec, t, src, args)
        d = probe(out)
        print(f"  {t['name']:10s} -> {out}  ({d['w']}x{d['h']}, {d['duration']:.2f}s, "
              f"{os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
