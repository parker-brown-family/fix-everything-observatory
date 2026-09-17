#!/usr/bin/env python3
"""What a caller on this machine is allowed to cost the operator's desktop.

Loopback is an interface, not a trust boundary. Every other process and every
other user account on the box can open a socket to this server, and until
2026-09-17 two of the cheapest possible requests cost more than anyone would
choose to spend:

  a POST declaring `Content-Length: 8589934592`, because the read was sized
  from the header and the allocation was therefore the caller's to choose;

  a handful of connections that send one byte and stop, because each was
  accepted and given a thread before any of this server's own rules ran.

Both were raised in a marketplace security review
(omacom/omarchy-plugin-marketplace#5534, 2026-09-17). They are denial of
service against the operator's own desktop rather than against a server, which
is why they read as unimportant and are not.

This starts a real server on a spare port and attacks it. No network, no state
outside a temp directory.

    python3 tests/check_dos_limits.py
"""
import functools
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()
# Both before the import: the port is read at module scope and the Host gate
# compares against it, and a test that mined into the operator's real state
# directory would be a test that broke the thing it was checking.
os.environ["FIX_OBSERVATORY_PORT"] = str(PORT)
os.environ["FIX_OBSERVATORY_STATE"] = tempfile.mkdtemp(prefix="dos-limits-")
sys.path.insert(0, str(ROOT))
import observatory as obs  # noqa: E402

obs.log = lambda *a, **k: None
# Short enough that the whole file runs in a couple of seconds, long enough that
# a loaded CI runner does not trip it by being slow. Read at arm() time, so
# rebinding the module global is enough.
obs.HEADER_DEADLINE = 1.5

fails = []


def check(label, cond, detail=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ")
          + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(label)


handler = functools.partial(obs.QuietHandler, directory=str(ROOT))
httpd = obs.BoundedServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()


def connect(timeout=6.0) -> socket.socket:
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    s.settimeout(timeout)
    return s


def status(sock) -> str:
    """The status line of whatever comes back, or '' if the peer just closed."""
    buf = b""
    try:
        while b"\r\n" not in buf and len(buf) < 4096:
            chunk = sock.recv(256)
            if not chunk:
                break
            buf += chunk
    except OSError:
        pass
    line = buf.split(b"\r\n")[0].decode("latin-1")
    return line.split(" ")[1] if line.startswith("HTTP/") else ""


def post(body: bytes, declared=None, extra=b"") -> str:
    n = len(body) if declared is None else declared
    s = connect()
    s.sendall(b"POST /api/induct HTTP/1.1\r\n"
              + f"Host: 127.0.0.1:{PORT}\r\n".encode()
              + b"X-Fix-Observatory: 1\r\n"
              + f"Content-Length: {n}\r\n".encode()
              + extra + b"Connection: close\r\n\r\n" + body)
    out = status(s)
    s.close()
    return out


print("\n\033[1mwhat a caller may cost us\033[0m")

# ---- the body -----------------------------------------------------------------
# The header is the caller's opinion, not an allocation order. Eight gigabytes
# declared, nothing sent: the answer has to come back without the server having
# tried to hold it, which is why the elapsed time is part of the assertion.
t0 = time.monotonic()
code = post(b"", declared=8589934592)
elapsed = time.monotonic() - t0
check("a body declared at 8 GiB is refused", code == "413", f"got {code!r}")
check("and refused without reading it — answered in under a second",
      elapsed < 1.0, f"took {elapsed:.2f}s")

check(f"a body one byte over the {obs.MAX_BODY} ceiling is refused",
      post(b"", declared=obs.MAX_BODY + 1) == "413")
check("a body at the ceiling is not",
      post(b'{"path":"/nope-' + b"x" * (obs.MAX_BODY - 200) + b'"}') != "413")
check("a negative Content-Length is refused", post(b"", declared=-1) == "413")
check("a Content-Length that is not a number is refused",
      post(b"", declared="banana") == "400")
# Nothing here decodes chunked, so without this the body would read as empty and
# the request would quietly do the wrong thing rather than being told no.
check("a chunked body is refused rather than read as empty",
      post(b"", declared=0, extra=b"Transfer-Encoding: chunked\r\n") == "411")

# ---- the connections ----------------------------------------------------------
# Held open, sending nothing: before this they were eight threads and eight
# descriptors, taken before the Host check could look at any of them.
held = [connect() for _ in range(obs.MAX_PER_PEER)]
before = httpd.refused
extra = connect()
code = status(extra)
check(f"connection {obs.MAX_PER_PEER + 1} from one peer is refused",
      code == "503", f"got {code!r}")
check("and refused before a worker existed for it", httpd.refused == before + 1)
extra.close()
for s in held:
    s.close()

deadline = time.monotonic() + 8
while httpd._live > 0 and time.monotonic() < deadline:
    time.sleep(0.05)
check("closing them gives the budget back", httpd._live == 0,
      f"{httpd._live} still counted")

# THE CEILING HAS TO CLEAR WHAT THE APP ACTUALLY DOES. Measured with a real
# browser against the real server — a page load plus two forty-wide parallel
# bursts — the high-water mark is 6, because that is where Chrome caps
# concurrent connections to one origin. On loopback the browser shares its
# bucket with the bar widget and every terminal on the box, so the headroom
# above that number is the whole margin there is. A ceiling that throttled the
# instrument would pass every other line in this file.
BROWSER_PEAK = 6
httpd.peak = 0
before = httpd.refused
burst, codes = [], []
for _ in range(BROWSER_PEAK):
    s = connect()
    s.sendall(b"GET /api/caps HTTP/1.1\r\n"
              + f"Host: 127.0.0.1:{PORT}\r\n".encode()
              + b"Connection: close\r\n\r\n")
    burst.append(s)
for s in burst:
    codes.append(status(s))
    s.close()
check(f"a browser's own peak of {BROWSER_PEAK} at once is all answered",
      codes.count("200") == BROWSER_PEAK, f"got {codes}")
check("and none of it was refused", httpd.refused == before)
check(f"leaving headroom over the measured peak, not just over one request",
      obs.MAX_PER_PEER >= BROWSER_PEAK * 2,
      f"per-peer {obs.MAX_PER_PEER} against a measured peak of {BROWSER_PEAK}")

# ---- the deadline -------------------------------------------------------------
# A per-recv timeout is not a deadline: one byte every 300ms never idles. What
# has to end this is wall-clock time from accept, enforced by something other
# than the thread doing the reading.
drip = connect()
drip.sendall(b"POST /api/induct HTTP/1.1\r\n")
t0 = time.monotonic()
closed = False
while time.monotonic() - t0 < obs.HEADER_DEADLINE + 3:
    try:
        drip.sendall(b"X-Pad: x\r\n")
        if not drip.recv(64):
            closed = True
            break
    except OSError:
        closed = True
        break
    time.sleep(0.3)
took = time.monotonic() - t0
drip.close()
check("a request that drips headers forever is closed anyway", closed,
      f"still open after {took:.1f}s")
check("and closed on the deadline, not on an idle timeout",
      closed and took < obs.HEADER_DEADLINE + 2, f"took {took:.1f}s")

# ---- the queue, and that none of this broke the app ---------------------------
check("the listen backlog is bounded",
      obs.BoundedServer.request_queue_size == obs.REQUEST_QUEUE
      and obs.REQUEST_QUEUE <= 64,
      f"{obs.BoundedServer.request_queue_size}")

s = connect()
s.sendall(b"GET /api/caps HTTP/1.1\r\n"
          + f"Host: 127.0.0.1:{PORT}\r\n".encode()
          + b"Connection: close\r\n\r\n")
code = status(s)
s.close()
check("and an ordinary request is still answered", code == "200", f"got {code!r}")

httpd.shutdown()
print()
if fails:
    print(f"\033[31m{len(fails)} limit check(s) failed\033[0m")
    sys.exit(1)
print("\033[32mthe limits hold\033[0m")
