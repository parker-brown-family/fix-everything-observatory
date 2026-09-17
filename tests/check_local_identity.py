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
mine = REAL_PEER_UID(probe.getsockname()[1], PORT)
probe.close()
check("the lookup reads this user's uid off a live connection",
      mine == os.getuid(), f"got {mine!r}, expected {os.getuid()}")

check("a request from this user is served", ask() == "200")
check("and the header is still required, so the CSRF defence is intact",
      ask(header=b"") == "403")

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
