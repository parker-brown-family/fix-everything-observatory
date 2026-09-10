#!/usr/bin/env python3
"""capture.py — record a scripted run of the observatory, frame-aligned to the script.

    tools/reel/capture.py --duration 40 --out build/take.mp4

WHY A SCRIPTED TAKE AND NOT A HAND-DRIVEN ONE

A reel's camera has to arrive on a thing at the instant a word is said. That is
only authorable if the thing is in the same place on every take, which a hand
driving a mouse cannot promise. Here the page is driven over DevTools, the
replay transport does the moving, and the take is repeatable — so a shot list
written against take one still lines up against take nine.

HOW THE CLOCK IS ALIGNED

The recorder and the page cannot be started on the same instant, and guessing
the lag is how a camera ends up a third of a second behind its own narration.
So the page holds a full-screen black card over itself until the take starts and
drops it on the first frame that counts; `blackdetect` then finds that frame in
the recording and everything downstream is measured from there. The reel opening
on a hard cut from black is a side effect, and a welcome one.

WHAT IS DELIBERATELY NOT RECORDED

The cursor. Every beat in this reel is a camera move, not a click, and a pointer
sitting in frame doing nothing is the clearest tell that a demo was performed
rather than composed. The pointer is also parked on the other monitor, because a
compositor draws it on the output it is physically on.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Chrome  # noqa: E402

URL = "http://127.0.0.1:4517/app/swarm.html"
MONITOR = "eDP-1"
PARK_MONITOR_X = 2000     # a point on DP-2, off the recorded output


# The card the page wears until the take begins. Painted by the page rather than
# by the compositor so it is inside the recorded surface, which is the only place
# blackdetect can see it.
CURTAIN = """
(() => {
  let d = document.getElementById('__reel_curtain');
  if (!d) {
    d = document.createElement('div');
    d.id = '__reel_curtain';
    d.style.cssText = 'position:fixed;inset:0;background:#000;z-index:2147483647;' +
                      'pointer-events:none;transition:none';
    document.body.appendChild(d);
  }
  d.style.display = '';
  return true;
})()
"""

DROP_CURTAIN = """
(() => {
  const d = document.getElementById('__reel_curtain');
  if (d) d.style.display = 'none';
  return performance.now();
})()
"""


def sh(cmd: list[str], check: bool = False) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"{cmd[0]} failed: {p.stderr.strip()}")
    return p.stdout


def hypr(*args: str) -> str:
    return sh(["hyprctl", *args])


def cursor_pos() -> tuple[int, int]:
    out = hypr("cursorpos").strip()
    try:
        x, y = out.split(",")
        return int(x), int(y)
    except ValueError:
        return 800, 500


def place_window(page, monitor: str, tries: int = 30) -> dict:
    """Put the window THIS PAGE is in onto the output the recorder is pointed at.

    Identifying it by pid or by class both failed, and failed quietly: Chrome
    opens more than one surface, several share a class, and the biggest one by
    area is not reliably the one holding the document. The rig then fullscreened
    a window nobody was looking at while the real page sat tiled at 781x950, and
    the only symptom was a viewport check refusing a take for no visible reason.

    So the page names itself. A token written into document.title appears in
    Hyprland's client list, and the window carrying it is the window the page is
    in — by construction, not by inference. App-mode windows have no titlebar, so
    nothing of this reaches the recording, and the title is put back anyway.
    """
    token = f"__reel__{os.getpid()}__"
    original = page.eval("document.title")
    page.eval(f"document.title = {json.dumps(token)}; true")
    try:
        for _ in range(tries):
            try:
                clients = json.loads(sh(["hyprctl", "clients", "-j"]))
            except json.JSONDecodeError:
                clients = []
            mine = [c for c in clients if token in (c.get("title") or "")]
            if mine:
                return _to_monitor(mine[0]["address"], monitor)
            time.sleep(0.3)
        raise SystemExit(
            "no Hyprland window ever carried the page's own title token — "
            "the compositor is not seeing this browser window")
    finally:
        page.eval(f"document.title = {json.dumps(original)}; true")


def _monitor_info(name: str) -> tuple[int, int]:
    """(id, active workspace id) for a monitor, read live."""
    for m in json.loads(sh(["hyprctl", "monitors", "-j"])):
        if m["name"] == name:
            return m["id"], m["activeWorkspace"]["id"]
    raise SystemExit(f"no monitor named {name}")


def _to_monitor(addr: str, monitor: str, tries: int = 6) -> dict:
    """Move the window to `monitor`. Fullscreen is somebody else's job.

    Ordering here was learned the expensive way. `movewindow mon:<name>` is
    ignored for a window that is currently fullscreen, and Hyprland's
    `fullscreen` dispatcher is a toggle that cannot clear a fullscreen the CLIENT
    asked for (`fullscreenClient: 2`) — so a window launched with Chrome's
    --start-fullscreen lands wherever Hyprland first put it and will not be
    moved off. The way out is to never let the client open fullscreen: place the
    plain window here, then ask Chrome for fullscreen over DevTools once it is on
    the right output.
    """
    want, ws = _monitor_info(monitor)
    for _ in range(tries):
        cur = _client(addr)
        if not cur:
            break
        if cur.get("monitor") == want:
            return cur
        # `movewindow mon:<name>` is accepted and does nothing here, so the move
        # goes via the workspace instead: a workspace belongs to exactly one
        # output, so putting the window on the output's workspace puts it on the
        # output. This is also what makes it deterministic rather than dependent
        # on which monitor happened to be focused when Chrome opened.
        hypr("dispatch", "movetoworkspacesilent", f"{ws},address:{addr}")
        time.sleep(0.4)
        hypr("dispatch", "focusmonitor", monitor)
        hypr("dispatch", "workspace", str(ws))
        hypr("dispatch", "focuswindow", f"address:{addr}")
        time.sleep(0.5)
    raise SystemExit(
        f"could not move the window onto {monitor} (workspace {ws}); "
        f"last state {_client(addr)}")


def _client(addr: str) -> dict | None:
    try:
        for c in json.loads(sh(["hyprctl", "clients", "-j"])):
            if c["address"] == addr:
                return c
    except json.JSONDecodeError:
        pass
    return None


def _descendants(pid: int) -> set[int]:
    out = {pid}
    frontier = [pid]
    while frontier:
        p = frontier.pop()
        try:
            kids = sh(["pgrep", "-P", str(p)]).split()
        except Exception:
            kids = []
        for k in kids:
            k = int(k)
            if k not in out:
                out.add(k)
                frontier.append(k)
    return out


class Watchdog(threading.Thread):
    """Notice when something else takes the screen mid-take.

    This machine routinely runs several agents against one live desktop, and a
    window opening on the recorded workspace forty seconds in produces a file
    that is perfectly valid, mostly correct, and unusable — a failure that is
    otherwise found by eye, one contact sheet at a time. Polling the active
    window costs nothing and turns it into a fact the take carries.
    """

    def __init__(self, addr: str, period: float = 0.4):
        super().__init__(daemon=True)
        self.addr, self.period = addr, period
        self.intrusions: list[dict] = []
        self._stop = threading.Event()
        self.t0 = time.monotonic()

    def run(self) -> None:
        while not self._stop.wait(self.period):
            try:
                cur = json.loads(sh(["hyprctl", "activewindow", "-j"]) or "{}")
            except json.JSONDecodeError:
                continue
            if cur.get("address") and cur["address"] != self.addr:
                self.intrusions.append({
                    "t": round(time.monotonic() - self.t0, 2),
                    "class": cur.get("class"),
                    "title": (cur.get("title") or "")[:60],
                })
                self._stop.set()      # one is enough; the take is already spoiled
                return

    def stop(self) -> list[dict]:
        self._stop.set()
        return self.intrusions


def stage_hygiene() -> tuple[int, int]:
    """Everything that would otherwise land in frame. Config is never written —
    a config reload recompiles the CRT shader and raises Hyprland's sticky red
    error banner across the top of the capture."""
    here = cursor_pos()
    # Omarchy's notifications are Quickshell's, not mako's, and neither is
    # guaranteed present. A missing dismisser is not a reason to lose the take —
    # it is a reason to say so, since an unread toast will land in frame.
    for cmd in (["makoctl", "dismiss", "-a"],
                ["omarchy-shell", "notifications", "dismiss-all"],
                ["dunstctl", "close-all"]):
        try:
            if subprocess.run(cmd, capture_output=True).returncode == 0:
                break
        except FileNotFoundError:
            continue
    else:
        print("  ! no notification dismisser found — a toast may land in frame",
              file=sys.stderr)
    hypr("seterror", "disable")
    hypr("dispatch", "movecursor", str(PARK_MONITOR_X), "540")
    return here


def require_consent(args) -> None:
    """Refuse to hijack a screen someone is using.

    A take is not a background job. It focuses MONITOR, opens Chrome fullscreen
    over whatever is there, paints it black for --lead seconds and then plays —
    call it `lead + duration + tail` seconds during which the machine belongs to
    the rig rather than to its owner. Several agents hold sessions in this repo
    at once and any of them can call this file. On 2026-09-08 one did: about ten
    raises between 13:44 and 14:18, over a human recording content on eDP-1, who
    had no idea what was doing it.

    Worse, the Watchdog counts his clicking away as an intrusion, so the take
    was spoiled, so the wrapper re-shot — his reaction to the interruption is
    what caused the next one.

    Consent is therefore explicit and per-run. There is deliberately no env var
    and no config key, because the failure mode of those is an agent finding the
    opt-out and setting it.
    """
    if args.i_am_watching:
        return
    held = args.lead + args.duration + args.tail
    # Exit 4, not 1: a wrapper must be able to tell "nobody consented" from
    # "the rig is broken", or it reports the first as the second and sends the
    # reader hunting a fault that is not there.
    print(
        f"refusing to take over {MONITOR} for ~{held:.0f}s without consent.\n\n"
        f"A take opens Chrome fullscreen on {MONITOR}, holds it black for "
        f"{args.lead:g}s, then plays. Anyone using that screen loses it.\n\n"
        "If you are at the machine and ready:\n\n"
        f"    python3 capture.py --i-am-watching --out {args.out} "
        f"--duration {args.duration:g}\n\n"
        "If you are an agent: do not pass that flag. Ask the human to shoot it.",
        file=sys.stderr)
    raise SystemExit(4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/take.mp4")
    ap.add_argument("--duration", type=float, default=40.0)
    ap.add_argument("--rate", type=int, default=1,
                    help="presses of '>' from 1x before playing (1 => 2x)")
    ap.add_argument("--motion", type=int, default=0,
                    help="presses of '+' to speed the swarm's own rotation")
    ap.add_argument("--lead", type=float, default=5.0, help="black lead-in seconds")
    ap.add_argument("--tail", type=float, default=1.5)
    ap.add_argument("--url", default=URL)
    ap.add_argument("--i-am-watching", action="store_true",
                    help="consent: a human is at the machine and has agreed to "
                         f"lose {MONITOR} for the length of the take")
    args = ap.parse_args()

    require_consent(args)

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    beats_path = os.path.splitext(out)[0] + ".beats.json"

    # Deliberately NOT --start-fullscreen: see _to_monitor(). Chrome is asked for
    # fullscreen over DevTools after the window is on the right output.
    Chrome.FLAGS = Chrome.FLAGS + [
        "--ozone-platform=wayland", "--enable-features=UseOzonePlatform",
    ]

    # A new window opens on whatever monitor happens to be focused, and this box
    # has a portrait second display — a take that silently records the wrong
    # output looks like a recorder failure and is not one. Focus the output the
    # recorder is pointed at, then check the page agrees before spending 40s.
    hypr("dispatch", "focusmonitor", MONITOR)
    time.sleep(0.3)

    restore_cursor = None
    rec = None
    browser = Chrome(args.url, width=1600, height=1000)
    try:
        with browser as page:
            # `readyState === 'complete'` is true of the about:blank the target
            # attaches to before the navigation lands, so it is not a signal that
            # the page exists. Wait for the page's own elements instead.
            page.wait_for("document.body && document.getElementById('world') && "
                          "document.readyState === 'complete'", 45)
            page.eval(CURTAIN)
            win = place_window(page, MONITOR)
            wid = page.call("Browser.getWindowForTarget")["windowId"]
            page.call("Browser.setWindowBounds", windowId=wid,
                      bounds={"windowState": "fullscreen"})
            time.sleep(1.0)
            win = _client(win["address"]) or win
            print(f"  window on {win.get('monitor')} at {win.get('at')} "
                  f"size {win.get('size')} fullscreen={win.get('fullscreen')}")
            # Whatever stole focus while Chrome was starting gets it back now,
            # before the watchdog begins caring.
            hypr("dispatch", "focuswindow", f"address:{win['address']}")
            time.sleep(0.4)
            page.wait_for("window.SWARM_DATA && SWARM_DATA.artifacts.length > 0", 60)

            # A window resize reaches the document asynchronously, so a fixed
            # sleep here samples whatever the page happened to think a moment
            # ago — which read 781x950 while the compositor had already given the
            # window the whole 1600x1000 output. Wait for the page to agree.
            try:
                page.wait_for("innerWidth === 1600 && innerHeight === 1000", 10)
            except TimeoutError:
                pass
            time.sleep(1.5)   # first WebGL frames and the rail

            meta = json.loads(page.eval(
                "JSON.stringify({vw:innerWidth, vh:innerHeight, dpr:devicePixelRatio,"
                " n:SWARM_DATA.artifacts.length, repo:SWARM_DATA.repo})"))
            if meta["vw"] != 1600 or abs(meta["dpr"] - 1.6) > 0.01:
                raise SystemExit(
                    f"viewport {meta['vw']}x{meta['vh']} @dpr {meta['dpr']} is not "
                    f"{MONITOR}'s native geometry (1600x1000 @1.6) — the window opened "
                    "on the wrong output, so the recorder would capture a screen the "
                    "page is not on. Refusing the take.")

            # Transport to the beginning of history, paused, then set the rate.
            page.key("Home", "Home", 36)
            time.sleep(0.4)
            for _ in range(args.rate):
                page.key(">", "Period", 190, text=">")
                time.sleep(0.12)
            for _ in range(args.motion):
                page.key("+", "Equal", 187, text="+")
                time.sleep(0.12)
            rate_label = page.eval(
                "document.getElementById('rateBtn').textContent")
            clock_label = page.eval("document.getElementById('clock').textContent")

            restore_cursor = stage_hygiene()

            rec = subprocess.Popen(
                ["gpu-screen-recorder", "-w", MONITOR, "-f", "60",
                 "-k", "h264", "-q", "ultra", "-cursor", "no",
                 "-fm", "cfr", "-ac", "aac", "-o", out],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(args.lead)
            if rec.poll() is not None:
                raise SystemExit("gpu-screen-recorder exited immediately")

            dog = Watchdog(win["address"])
            dog.start()

            beats = [{"t": 0.0, "name": "curtain-drop"}]
            page.eval(DROP_CURTAIN)
            t0 = time.monotonic()
            page.key(" ", "Space", 32, text=" ")
            beats.append({"t": round(time.monotonic() - t0, 3), "name": "play"})

            # Poll the transport clock through the take. Two jobs: an idle
            # DevTools socket gets closed under us and kills the run forty
            # seconds in, and the samples are the map from reel time to the date
            # on screen — which is what lets a shot be written as "be on the
            # flow diagram when the replay reaches spring".
            while time.monotonic() - t0 < args.duration:
                time.sleep(1.0)
                try:
                    beats.append({
                        "t": round(time.monotonic() - t0, 2),
                        "name": "clock",
                        "clock": page.eval(
                            "document.getElementById('clock').textContent"),
                    })
                except Exception as exc:
                    beats.append({"t": round(time.monotonic() - t0, 2),
                                  "name": "poll-failed", "error": str(exc)[:80]})
                    break

            beats.append({"t": round(time.monotonic() - t0, 3), "name": "end"})
            intrusions = dog.stop()
            page.eval(CURTAIN)
            time.sleep(args.tail)

            with open(beats_path, "w") as fh:
                json.dump({
                    "source_url": args.url, "monitor": MONITOR,
                    "viewport": [meta["vw"], meta["vh"]], "dpr": meta["dpr"],
                    "artifacts": meta["n"], "repo": meta["repo"],
                    "rate_label": rate_label, "clock_at_start": clock_label,
                    "duration": args.duration, "beats": beats,
                    "lead": args.lead, "intrusions": intrusions,
                }, fh, indent=1)
    finally:
        if rec and rec.poll() is None:
            rec.send_signal(signal.SIGINT)
            try:
                rec.wait(timeout=20)
            except subprocess.TimeoutExpired:
                rec.kill()
        if restore_cursor:
            hypr("dispatch", "movecursor", str(restore_cursor[0]), str(restore_cursor[1]))

    if not os.path.exists(out):
        raise SystemExit("no file written — gpu-screen-recorder produced nothing")
    print(f"raw take -> {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    print(f"beats    -> {beats_path}")
    if intrusions:
        print("  ! TAKE SPOILED — another window took the screen: "
              + ", ".join(f"{i['t']}s {i['class']}" for i in intrusions))
        # A distinct exit code, so a re-shoot loop can tell "the desktop moved"
        # from "the rig is broken" and only retry the first.
        raise SystemExit(3)


if __name__ == "__main__":
    main()
