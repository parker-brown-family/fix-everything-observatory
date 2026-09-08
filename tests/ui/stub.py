#!/usr/bin/env python3
"""A fixed observatory, so the interface can be tested without a real one.

The swarm page decides what to render from two things: /api/projects and the
manifest. Both move — projects get inducted, mines land, counts change — so a
test pointed at the live server measures whatever the machine happens to be
doing this minute. This serves a frozen registry instead, which is what makes
"four projects need 1450px" an assertion rather than an observation.

    python3 tests/ui/stub.py --port 4531 --projects 4

Serves the real app/swarm.html unmodified. Only its data is fake.
"""
import argparse, http.server, json, pathlib, socketserver, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Deliberately varied name lengths: the collapse rule is about laid-out width,
# so a fixture of four identical short names would not exercise it.
PROJECTS = [
    dict(slug="omacom__omarchy", repo="omacom/omarchy", artifacts=8989,
         mining=False, seeded=False, error=None),
    dict(slug="pbf__fix-everything-observatory",
         repo="parker-brown-family/fix-everything-observatory", artifacts=13,
         mining=True, seeded=False, error=None),
    dict(slug="pbf__omarchy-terminal-delight-theme",
         repo="parker-brown-family/omarchy-terminal-delight-theme", artifacts=47,
         mining=False, seeded=True, error=None),
    dict(slug="pbf__terminal-delight", repo="parker-brown-family/terminal-delight",
         artifacts=None, mining=False, seeded=False, error="git: repository not found"),
]

MANIFEST = {
    "schema": "fix-everything-manifest:v2",
    "repo": "omacom/omarchy",
    "fetched_at": "2026-09-08T12:00:00+00:00",
    "error": None,
    "coverage": {"per_page": 100, "order": "asc", "issue_pages": 1,
                 "comment_pages": 1, "event_pages": 1, "complete": True},
    "artifacts": [
        {"number": 1, "type": "issue", "title": "a fixture ticket", "user": "someone",
         "opened": "2026-09-01T00:00:00Z", "closed": None, "merged": False,
         "reopened": False, "comments": 0, "labels": [], "body": ""},
    ],
    "comments": [],
    "events": [],
}


def make_handler(n_projects):
    projects = [dict(p, label=p["repo"], path=None, builtin=False, added_at=None,
                     comments=0, events=0, complete=True, authenticated=True,
                     fetched_at="2026-09-08T12:00:00+00:00")
                for p in PROJECTS[:n_projects]]

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def log_message(self, *a):
            pass                                   # a test runner is not a web log

        def _json(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/projects":
                return self._json({"active": projects[0]["slug"] if projects else None,
                                   "roots": ["/home/tester/Work"], "projects": projects})
            if path == "/api/scan":
                return self._json({"roots": ["/home/tester/Work"], "found": [],
                                   "hidden": 0, "dirs": 0, "ms": 1})
            if path == "/data/manifest.js":
                body = ("window.SWARM_DATA = " + json.dumps(MANIFEST) + ";").encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            return super().do_GET()

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            return self._json({"ok": True})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--projects", type=int, default=4)
    args = ap.parse_args()
    socketserver.TCPServer.allow_reuse_address = True
    try:
        srv = socketserver.TCPServer(("127.0.0.1", args.port), make_handler(args.projects))
    except OSError as e:
        # Loudly, because a stub that cannot bind leaves the previous run's
        # fixture answering — and the tests then pass or fail against data
        # nobody chose.
        print(f"stub: cannot bind 127.0.0.1:{args.port}: {e}", file=sys.stderr)
        sys.exit(2)
    with srv:
        print(f"stub: {args.projects} projects on 127.0.0.1:{args.port}", file=sys.stderr)
        srv.serve_forever()


if __name__ == "__main__":
    main()
