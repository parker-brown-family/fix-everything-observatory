# tools/reel — the observatory, cut for a feed

A recording of a dense landscape dashboard is unwatchable on a phone. At 1080
wide a 2560-wide interface arrives at 42% scale and every number in it is
illegible, so the format the whole of short-form has converged on is a camera:
hold wide, arrive on the thing being talked about, hold there while it is talked
about, leave. What makes it feel authored rather than mechanical is that the
arrival lands on the **word**.

So a shot names the moment it must have **arrived**, on the same clock the script
is written in:

```json
{"t": 23.70, "label": "lifespan", "rect": [1920, 500, 640, 220], "arrive": 0.5}
```

The camera holds whatever it had until `t - arrive`, eases so it is settled
exactly at `t`, and stays until the next shot pulls it away. `t` comes straight
out of the narration's own word timings, so re-writing a line re-times the
camera and nobody counts frames.

## Run it

```
tools/reel/narration.py cues/vertical.txt -o build/words-vertical.json --show
```
```
tools/reel/geometry.py -o build/geometry.json
```
```
OUT=build/take.mp4 DURATION=42 bash tools/reel/take-until-clean.sh --i-am-watching
```
```
tools/reel/sync.py build/take.mp4
```
```
tools/reel/render.py reel-vertical.json --preview 8
```
```
tools/reel/render.py reel-vertical.json
```

`--preview N` renders the first N seconds at draft quality, which is the loop you
actually work in. `--check` validates the spec and renders nothing.

## The pieces

| File | What it does |
|---|---|
| `narration.py` | A cue list becomes word-level timings. Each word's length comes from its own length (`170ms + 42ms/char`, clamped, plus a beat after a clause), so the reel can be cut, watched and re-cut with **no audio in the building**. A real take transcribes into the same shape. |
| `cues/*.txt` | The script. Blank-line-separated cards, one idea each; `@12.5` pins a card to a time. |
| `geometry.py` | Reads every camera target off the **live page** at the capture viewport and converts once into recording pixels. Coordinates typed off a screenshot go stale the first time a margin moves. |
| `cdp.py` | An eighty-line stdlib DevTools client. The capture must be re-runnable from a cold shell, so the driver ships with the repository rather than depending on whatever tooling happened to be attached. |
| `capture.py` | Drives a scripted take and records it. Places the window, checks the geometry, watches for the desktop intruding, and frame-aligns the clock. |
| `take-until-clean.sh` | Re-shoots while `capture.py` keeps exiting 3. |
| `sync.py` | Finds the frame the take actually starts on, and how long it stays clean. |
| `camera.py` | The shot list resolved to a rect for any time — aspect fitting, clamping, easing. |
| `render.py` | Camera path plus captions plus audio, out to every delivery aspect. |
| `fix-audio.sh` | Brings a voiceover to **-14 LUFS**, which is where every feed normalises. |

## Things that are true here and cost a take each to learn

**A 9:16 crop of a 16:10 interface can show 35% of its width.** The widest legal
900x1600 window of a 2560x1600 source is a third of the screen. Everything wider
letterboxes, and that is fine — the letterbox is where the captions live — but it
means a wide establishing shot spends most of the frame on background. Shots in
the 900–1400px range are the ones that fill a phone.

**Rects are a minimum, never a frame.** Aspect fitting only ever grows a rect, so
a delivery format cannot crop out the thing the shot is about. Clamping runs
after fitting and before easing, so no interpolated frame between two legal rects
can be illegal.

**Keep rects at least as wide as the delivery, or accept soft text.** `render.py`
counts the frames that break this and says so. The rail is only 518px wide, so
its shots knowingly upscale — readable because the page renders at DPR 1.6, but
soft. That is a real trade, made on purpose.

**`crop` accepts per-frame commands.** The camera is a `sendcmd` script with one
entry per frame feeding `crop`, with a fixed-size `scale` downstream absorbing
the frame size changing underneath it. Rects round to even pixels because an odd
crop against yuv420p chroma siting shimmers.

**The window has to be found by something it owns.** Matching Chrome's window by
pid or by class both failed quietly — Chrome opens more than one surface and
several share a class, so the rig fullscreened a window nobody was looking at
while the real page sat tiled at 781x950. The page now writes a token into
`document.title` and the window carrying it is the window the page is in, by
construction. App-mode windows have no titlebar, so none of it reaches the take.

**`fullscreen` is a toggle and `movewindow mon:` is ignored on a fullscreen
window.** Chrome therefore must not open fullscreen: place the plain window on
the right output first (via its workspace, which belongs to exactly one output),
then ask Chrome for fullscreen over DevTools.

**`blackdetect` cannot see the lead-in.** Omarchy composites a CRT shader over
the screen, so the black card records as a dark red-brown gradient that crosses
no pixel threshold. `sync.py` uses mean luma with a threshold derived from the
take's own two levels instead.

**A take gets spoiled by the desktop it is shot on.** Several agents drive this
machine, and a window raised forty seconds in produces a file that is valid,
mostly correct and unusable. `capture.py` polls the active window and exits 3, so
that is a fact the take carries rather than something found later by eye.

**A take needs a human's consent, every run — `--i-am-watching`.** Shooting is
not a background job: it takes eDP-1 fullscreen, black for the lead-in and then
playing, for about `lead + duration + tail` seconds. Whoever is at the machine
loses that screen for the whole of it.

On 2026-09-08 an agent shot roughly ten takes between 13:44 and 14:18 while a
human was recording content on the same panel. He watched a black tile cover his
work every few minutes, wait five seconds, become this app, and vanish — with no
way to tell what was doing it. The re-shoot loop made it worse rather than
better: the Watchdog reads *his clicking away from the hijacked window* as an
intrusion, spoils the take, and the wrapper shoots again. His reaction to being
interrupted is what caused the next interruption.

So `capture.py` refuses to run without `--i-am-watching`, and the flag is a
per-run argument on purpose — no env var, no config key, because the failure
mode of those is an agent finding the opt-out and setting it. `take-until-clean.sh`
forwards its arguments through, and now defaults to `TRIES=1`: a spoiled take
reports and stops instead of re-shooting into whoever spoiled it. Raise `TRIES`
by hand when the desk is genuinely empty.

**Do not write compositor config while staging.** A config reload recompiles the
CRT shader and raises Hyprland's sticky red error banner across every workspace,
which lands in frame.

## Delivery

| Where | Aspect | Length | Notes |
|---|---|---|---|
| Shorts / TikTok / Reels | 9:16 1080x1920 | 25–35s | Captions burned in. Watch time beats length — a 30s clip watched through outperforms a 15s one that is not. |
| X | 1:1 1080x1080 | under 60s | Square takes more vertical space in the feed than landscape, and under 60s the post auto-loops. |
| Repo / landing hero | 16:9 | 8–15s | Silent, no captions, seamless loop. |

Audio, when there is any, lands at **-14 LUFS** with a -1.5 dBTP ceiling. Spoken
word mastered to -18 or -19 is right for headphones and about five units under
what a feed normalises to, which plays as "the sound is broken" — and nobody
reaches for the volume slider to fix a stranger's video.

## The script

`cues/vertical.txt` is a narrative loop: the last card is written to lead into
the first, so a replay reads as the next line rather than a restart. Read them
back to back out loud — that is the whole test.

**No figure that moves week to week is spoken.** The rail's volume and lifespan
blocks are windowed on the scrub cursor, and two probes an hour apart returned
"1,062 born last week" and "1,058". The camera lands on the rail and the screen
reports the live number instead, so the cut cannot go stale. The durable figures
— nine thousand artifacts, 8,082 carrying no signal, a 27.6h median — are the
only ones said out loud.
