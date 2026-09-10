#!/usr/bin/env python3
"""cdp.py — the smallest Chrome DevTools client that can drive a demo.

Stdlib only, to match the rest of this repository: a websocket client is about
eighty lines once you accept that the only frames a DevTools session sends are
text, and that no browser has ever needed the client to fragment a message.

Why not the browser extension that was already open: a capture step that only
works when a particular agent's tooling happens to be attached is not a step
anybody can re-run. `bin/reel capture` has to work from a cold shell six months
from now, which means the driver ships with the repository.

    from cdp import Chrome
    with Chrome(url, width=2560, height=1600) as page:
        page.wait_for("window.SWARM_DATA && SWARM_DATA.artifacts.length > 0")
        page.eval("document.getElementById('playBtn').click()")
        rect = page.eval("JSON.stringify(document.getElementById('rail').getBoundingClientRect())")
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request


class WS:
    """A text-only websocket client. Enough for DevTools, not enough for anything else."""

    def __init__(self, url: str, timeout: float = 20.0):
        assert url.startswith("ws://"), url
        rest = url[5:]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("websocket handshake closed early")
            buf += chunk
        status = buf.split(b"\r\n", 1)[0].decode("latin-1")
        if " 101 " not in status:
            raise ConnectionError(f"websocket handshake refused: {status}")
        self._rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, text: str) -> None:
        payload = text.encode()
        n = len(payload)
        header = b"\x81"
        if n < 126:
            header += struct.pack("!B", 0x80 | n)
        elif n < (1 << 16):
            header += struct.pack("!BH", 0x80 | 126, n)
        else:
            header += struct.pack("!BQ", 0x80 | 127, n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _read(self, n: int) -> bytes:
        out = self._rest[:n]
        self._rest = self._rest[n:]
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError("websocket closed")
            out += chunk
        return out

    def recv(self) -> str:
        while True:
            b0, b1 = self._read(2)
            opcode = b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            data = self._read(length) if length else b""
            if opcode == 0x8:
                raise ConnectionError("websocket closed by peer")
            if opcode == 0x9:      # ping -> pong, or Chrome drops us mid-capture
                self.sock.sendall(b"\x8a\x80" + os.urandom(4))
                continue
            if opcode in (0x1, 0x2):
                return data.decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class Page:
    """A DevTools session that survives losing its socket.

    Chrome drops the websocket for reasons that have nothing to do with the page
    — a window moved between outputs, a target swapped, an idle stretch — and a
    driver that treats that as fatal throws away a forty-second take for a
    reconnect that costs a quarter of a second. `reconnect` is supplied by the
    owner because only it knows how to find the same page again.
    """

    def __init__(self, ws_url: str, reconnect=None):
        self.ws = WS(ws_url)
        self._id = 0
        self._reconnect = reconnect
        self._enabled: list[str] = []

    def _reopen(self) -> None:
        if not self._reconnect:
            raise
        try:
            self.ws.close()
        except Exception:
            pass
        self.ws = WS(self._reconnect())
        self._id = 0
        for method in self._enabled:
            self._call_once(method)

    def _call_once(self, method: str, **params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def call(self, method: str, **params):
        if method.endswith(".enable") and method not in self._enabled:
            self._enabled.append(method)
        try:
            return self._call_once(method, **params)
        except (ConnectionError, BrokenPipeError, OSError):
            self._reopen()
            return self._call_once(method, **params)

    def eval(self, expr: str, await_promise: bool = False):
        """Evaluate and return the value. Objects come back as JSON, not handles."""
        res = self.call("Runtime.evaluate", expression=expr, returnByValue=True,
                        awaitPromise=await_promise, userGesture=True)
        if res.get("exceptionDetails"):
            d = res["exceptionDetails"]
            raise RuntimeError(d.get("exception", {}).get("description") or d.get("text"))
        return res.get("result", {}).get("value")

    def wait_for(self, expr: str, timeout: float = 30.0, poll: float = 0.15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.eval(f"!!({expr})"):
                    return True
            except RuntimeError:
                pass
            time.sleep(poll)
        raise TimeoutError(f"waiting for: {expr}")

    def key(self, key: str, code: str = "", vk: int = 0, text: str = ""):
        """A real key event. The page's own handlers see it; the compositor does not.

        This is the reason the demo is driven here and not with wtype: a
        synthetic key sent to the compositor lands wherever focus happens to be,
        and focus during a capture is not something worth betting a take on.
        """
        base = dict(key=key, code=code or key, windowsVirtualKeyCode=vk,
                    nativeVirtualKeyCode=vk)
        if text:
            base["text"] = text
        self.call("Input.dispatchKeyEvent", type="keyDown", **base)
        self.call("Input.dispatchKeyEvent", type="keyUp", **base)

    def click(self, x: float, y: float):
        for kind in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y,
                      button="left", clickCount=1)

    def move(self, x: float, y: float):
        self.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)

    def close(self):
        self.ws.close()


class Chrome:
    """A throwaway Chrome, its own profile, sized exactly, with nothing on screen but the page."""

    FLAGS = [
        "--no-first-run", "--no-default-browser-check", "--disable-sync",
        "--disable-features=Translate,MediaRouter,OptimizationHints",
        "--disable-extensions", "--disable-background-networking",
        "--hide-crash-restore-bubble", "--disable-infobars",
        "--autoplay-policy=no-user-gesture-required",
        # The observatory's server refuses any request whose Sec-Fetch-Site is
        # cross-site or same-site. A command-line launch is `none`, so it passes
        # where an extension-driven tabs.update does not.
    ]

    def __init__(self, url: str, width: int = 2560, height: int = 1600,
                 port: int = 0, binary: str | None = None, app: bool = True):
        self.url, self.w, self.h = url, width, height
        self.port = port or _free_port()
        self.profile = tempfile.mkdtemp(prefix="reel-chrome-")
        self.binary = binary or _find_chrome()
        self.app = app
        self.proc = None
        self.page = None

    def __enter__(self) -> Page:
        arg_url = f"--app={self.url}" if self.app else self.url
        cmd = [self.binary, *self.FLAGS,
               f"--user-data-dir={self.profile}",
               f"--remote-debugging-port={self.port}",
               f"--window-size={self.w},{self.h}",
               "--window-position=0,0", arg_url]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        ws_url = self._wait_target()
        self.page = Page(ws_url, reconnect=lambda: self._wait_target(20.0))
        self.page.call("Runtime.enable")
        self.page.call("Page.enable")
        return self.page

    def _wait_target(self, timeout: float = 30.0) -> str:
        """Wait for the target that is actually OUR page.

        Chrome exposes a debuggable `about:blank` before the navigation lands,
        and attaching to it is a trap: the target is destroyed the moment the
        real document arrives and the socket dies mid-run, several seconds later,
        looking like a browser crash. Match on the URL and keep waiting.
        """
        want = self.url.split("#", 1)[0]
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/list", timeout=2).read()
                pages = [t for t in json.loads(raw)
                         if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
                for t in pages:
                    if t.get("url", "").split("#", 1)[0] == want:
                        return t["webSocketDebuggerUrl"]
                last = f"{len(pages)} page(s), none at {want}: " \
                       + ", ".join(repr(t.get('url', ''))[:60] for t in pages)
            except Exception as exc:  # the port simply is not up yet
                last = exc
            time.sleep(0.25)
        raise TimeoutError(f"no debuggable page on :{self.port} ({last})")

    def pid(self) -> int:
        return self.proc.pid if self.proc else 0

    def __exit__(self, *exc):
        if self.page:
            self.page.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _find_chrome() -> str:
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chrome",
                 "/opt/google/chrome/chrome"):
        p = shutil.which(name) or (name if os.path.exists(name) else None)
        if p:
            return p
    raise SystemExit("no chrome/chromium on PATH")


if __name__ == "__main__":
    import sys

    with Chrome(sys.argv[1] if len(sys.argv) > 1
                else "http://127.0.0.1:4517/app/swarm.html") as page:
        page.wait_for("document.readyState === 'complete'")
        print(page.eval("JSON.stringify({title: document.title, "
                        "vw: innerWidth, vh: innerHeight, dpr: devicePixelRatio})"))
        time.sleep(2)
