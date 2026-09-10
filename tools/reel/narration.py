#!/usr/bin/env python3
"""narration.py — a cue list, and the word clock the camera and captions share.

    tools/reel/narration.py cues/vertical.txt -o build/words-vertical.json

WHY THE TIMING IS GENERATED RATHER THAN MEASURED

A reel needs word-level timestamps twice over: the captions walk a highlight
along the line, and the camera has to have ARRIVED somewhere by the moment a
particular word is said. Both normally wait on a recorded voiceover and a
transcription pass, which means nothing can be cut until somebody has performed
the script — and every rewrite costs another take.

So the cue list carries its own clock. Each word gets a duration from its
length, because "the" and "something" are not the same length out loud and a
flat rate sounds like a metronome:

    170 ms + 42 ms per character, clamped to 200-620 ms
    plus ~180 ms of breath after any word that ends a clause

Over a card that lands near 170 words per minute, which is a person talking
rather than a voiceover performing. The whole reel can then be cut, watched and
re-cut with no audio in the building — and when a real take does arrive, the
same JSON shape comes out of `transcribe.sh` and nothing downstream changes.

CUE FILE FORMAT

Blank-line-separated cards, one idea each. A card is what appears on screen at
once; the highlight only says where the voice is. A line beginning `#` is a
comment, and `@1.8` on its own line forces the next card to start at that time
(for holding on a visual beat).

    # the hook has to be grammatically open at the front
    The moment a repository starts
    healing faster than it breaks —

    @2.4
    you can actually watch it happen.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

MIN_MS, MAX_MS = 200, 620
PER_CHAR_MS = 42
BASE_MS = 170
BREATH_MS = 180          # after a word ending a clause
CARD_GAP_MS = 150        # between cards, on top of any breath


def word_duration(word: str) -> float:
    core = re.sub(r"[^\w'’-]", "", word)
    ms = BASE_MS + PER_CHAR_MS * len(core)
    ms = max(MIN_MS, min(MAX_MS, ms))
    if word.rstrip() and word.rstrip()[-1] in ",.;:—–?!":
        ms += BREATH_MS
    return ms / 1000.0


def parse(path: str) -> list[dict]:
    cards, cur, forced = [], [], None
    def flush():
        nonlocal cur, forced
        if cur:
            cards.append({"text": " ".join(cur), "at": forced})
        cur, forced = [], None

    with open(path) as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.strip().startswith("#"):
                continue
            if not line.strip():
                flush()
                continue
            m = re.fullmatch(r"@([0-9.]+)", line.strip())
            if m:
                flush()
                forced = float(m.group(1))
                continue
            cur.append(line.strip())
    flush()
    return cards


def build(cards: list[dict]) -> dict:
    words, t = [], 0.0
    out_cards = []
    for card in cards:
        if card["at"] is not None:
            if card["at"] < t:
                print(f"  ! @{card['at']} is before the clock ({t:.2f}s) — ignored",
                      file=sys.stderr)
            else:
                t = card["at"]
        start = t
        card_words = []
        for w in card["text"].split():
            d = word_duration(w)
            entry = {"w": w, "t": round(t, 3), "d": round(d, 3)}
            words.append(entry)
            card_words.append(entry)
            t += d
        out_cards.append({
            "text": card["text"],
            "t": round(start, 3),
            "end": round(t, 3),
            "words": card_words,
        })
        t += CARD_GAP_MS / 1000.0

    total = round(t, 3)
    spoken = sum(len(c["text"].split()) for c in cards)
    return {
        "words": words,
        "cards": out_cards,
        "duration": total,
        "wpm": round(spoken / (total / 60.0), 1) if total else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cues")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    doc = build(parse(args.cues))
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=1)

    print(f"{len(doc['cards'])} cards · {len(doc['words'])} words · "
          f"{doc['duration']:.2f}s · {doc['wpm']} wpm -> {args.out}")
    if args.show:
        for c in doc["cards"]:
            print(f"  {c['t']:6.2f}  {c['text']}")


if __name__ == "__main__":
    main()
