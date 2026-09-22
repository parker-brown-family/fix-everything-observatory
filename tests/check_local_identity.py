#!/usr/bin/env python3
"""Who the server will answer, and why the custom header was never the answer.

`X-Fix-Observatory: 1` is a CSRF defence: a browser cannot set a custom header
cross-origin without a preflight, so a page in another tab cannot reach the
routes with side effects. It is also a public constant in a public repository,
so it stops a browser and stops nothing else. Until 2026-09-17 it was the only
thing standing in front of the write routes, which meant any other account on
this machine could send it, POST a path of its choosing to /api/induct, have the
server read that repository as the owner of this process, resolve the
repository's `gh` token, and read the private issue and comment data back out of
the mined manifest. Neither the Host check nor CORS touches a caller that is not
a browser. Raised in a marketplace security review,
omacom/omarchy-plugin-marketplace#5534.

So identity now comes from the kernel. /proc/net/tcp carries the owning uid of
every socket, and a connection is refused at admission unless the socket on the
other end belongs to the same user this process runs as.

Testing the refusal needs a connection owned by somebody else, and a test suite
cannot make one without a second account. What it CAN do is pin both halves
separately: that the lookup really reads this user's uid off a live connection —
so the parse is not quietly returning None and passing for the wrong reason —
and that the admission gate refuses every answer that is not this uid, including
no answer at all.

    python3 tests/check_local_identity.py
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
os.environ["FIX_OBSERVATORY_PORT"] = str(PORT)
os.environ["FIX_OBSERVATORY_STATE"] = tempfile.mkdtemp(prefix="identity-")
sys.path.insert(0, str(ROOT))
import observatory as obs  # noqa: E402

obs.log = lambda *a, **k: None

fails = []


def check(label, cond, detail=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ")
          + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(label)


REAL_PEER_UID = obs.peer_uid
handler = functools.partial(obs.QuietHandler, directory=str(ROOT))
httpd = obs.BoundedServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()


def connect():
    s = socket.create_connection(("127.0.0.1", PORT), timeout=6)
    s.settimeout(6)
    return s


def status_of(s):
    try:
        buf = b""
        while b"\r\n" not in buf and len(buf) < 4096:
            chunk = s.recv(256)
            if not chunk:
                break
            buf += chunk
    except OSError:
        buf = b""
    line = buf.split(b"\r\n")[0].decode("latin-1")
    return line.split(" ")[1] if line.startswith("HTTP/") else ""


def ask_from(src_addr, src_port=0, path=b"/api/caps", verb=b"GET"):
    """Ask from a chosen loopback address and source port.

    The whole of 127.0.0.0/8 routes to lo and any unprivileged account may bind
    any of it, which is what makes this reachable from ONE account: the bypass
    did not need a second user, only a second address.
    """
    s = socket.socket()
    s.settimeout(6)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((src_addr, src_port))
        s.connect(("127.0.0.1", PORT))
        s.sendall(verb + b" " + path + b" HTTP/1.1\r\n"
                  + f"Host: 127.0.0.1:{PORT}\r\n".encode()
                  + b"X-Fix-Observatory: 1\r\nConnection: close\r\n\r\n")
        return status_of(s)
    except OSError as e:
        return "conn-refused:" + type(e).__name__
    finally:
        s.close()


def ask(header=b"X-Fix-Observatory: 1\r\n", verb=b"POST", path=b"/api/mine"):
    s = connect()
    try:
        s.sendall(verb + b" " + path + b" HTTP/1.1\r\n"
                  + f"Host: 127.0.0.1:{PORT}\r\n".encode() + header
                  + b"Content-Length: 2\r\nConnection: close\r\n\r\n{}")
        buf = b""
        while b"\r\n" not in buf and len(buf) < 4096:
            chunk = s.recv(256)
            if not chunk:
                break
            buf += chunk
    except OSError:
        buf = b""
    finally:
        s.close()
    line = buf.split(b"\r\n")[0].decode("latin-1")
    return line.split(" ")[1] if line.startswith("HTTP/") else ""


print("\n\033[1mwho the server answers\033[0m")

# THE LOOKUP HAS TO ACTUALLY READ THE KERNEL. If the /proc parse were wrong it
# would return None, everything would fail closed, and a suite that only checked
# "the stranger is refused" would pass while the instrument was dead.
probe = connect()
mine = REAL_PEER_UID("127.0.0.1", probe.getsockname()[1], PORT)
probe.close()
check("the lookup reads this user's uid off a live connection",
      mine == os.getuid(), f"got {mine!r}, expected {os.getuid()}")

check("a request from this user is served", ask() == "200")
check("and the header is still required, so the CSRF defence is intact",
      ask(header=b"") == "403")

# ---------------------------------------------------------------------------
# THE BYPASS THIS SUITE USED TO MISS, and the reason it missed it.
#
# Everything below the next divider stands in for a second account by replacing
# peer_uid — which is the function the bug was IN, so those checks exercise the
# comparison in process_request and never the lookup. The lookup identified a
# socket by its two PORTS and assumed the peer's address was 127.0.0.1, while
# the real address sat unused one frame up. Since all of 127.0.0.0/8 routes to
# lo and needs no privilege to bind, a caller from 127.0.0.2 that reused a
# source port some genuine same-uid client was holding matched THAT client's
# row, and was admitted as this user. No second account required — which means
# no second account is required to test it either.
# ---------------------------------------------------------------------------
held = connect()                       # a genuine same-uid client, kept open
held_port = held.getsockname()[1]
check("a caller from another loopback address is refused",
      ask_from("127.0.0.2") == "403")
check("even when it reuses a source port a real client of ours is holding",
      ask_from("127.0.0.2", held_port) == "403",
      "this is the bypass: it was answered 200")
held.close()

# The served tree is the whole checkout, so the /app/ guard is the only thing
# between a caller and .git/. It read the path before it was decoded, while the
# resolver unquotes first and normalises second — so %2e%2e walked straight out.
check("an encoded traversal out of /app/ is refused",
      ask_from("127.0.0.1", 0, b"/app/%2e%2e/observatory.py") == "404",
      "the source of this server was served")
check("and so is the uppercase form",
      ask_from("127.0.0.1", 0, b"/app/%2E%2E/.git/config") == "404",
      "the git config was served")
check("while the app itself still loads",
      ask_from("127.0.0.1", 0, b"/app/swarm.html") == "200")

# Everything below stands in for an account this test cannot create.
before_rejected, before_refused = httpd.rejected, httpd.refused

obs.peer_uid = lambda *a: os.getuid() + 1
check("a connection owned by another uid is refused", ask() == "403")
check("and the public header buys it nothing — the reviewer's exact path",
      ask(verb=b"POST", path=b"/api/induct") == "403")

# UNKNOWN IS NOT PERMISSION. If the kernel will not say who is on the other end,
# that is a third answer, and it is not yes.
obs.peer_uid = lambda *a: None
check("a peer the kernel will not identify is refused too", ask() == "403")

obs.peer_uid = REAL_PEER_UID
check("and this user is served again once the lookup is honest", ask() == "200")

check("every refusal was counted as an identity rejection",
      httpd.rejected == before_rejected + 3,
      f"{httpd.rejected - before_rejected} counted")
# The served request's worker releases its slot after the client has already
# read the status line, so drain before asserting the budget is untouched —
# otherwise this races the one connection that was SUPPOSED to be admitted.
deadline = time.monotonic() + 5
while httpd._live > 0 and time.monotonic() < deadline:
    time.sleep(0.05)
check("and none of them spent a connection from the budget",
      httpd.refused == before_refused and httpd._live == 0,
      f"refused={httpd.refused - before_refused} live={httpd._live}")

httpd.shutdown()
print()
if fails:
    print(f"\033[31m{len(fails)} identity check(s) failed\033[0m")
    sys.exit(1)
print("\033[32mthe server answers only this user\033[0m")
