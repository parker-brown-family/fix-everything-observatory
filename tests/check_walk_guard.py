#!/usr/bin/env python3
"""A walk that stops early must not be allowed to call itself the end.

On 2026-09-15 GitHub's issues endpoint began withholding the `rel="next"` link
at random — after one page, five, thirty-one — on a repository holding 9,972
artifacts. Every one of those walks came back with complete=True, because the
only end-of-stream signal the miner had was the absence of that link. The slice
guard keys on completeness, so it waved them through, and a manifest of 9,963
artifacts was overwritten by the 400 oldest. All of them closed in 2025, none
alive at the cursor: the swarm went empty and the attribution panel read 390 of
400 "no signal", which is a measurement of June 2025 dressed as a measurement
of now.

Four things have to hold, and each one failed in that incident:

  1. a walk short of the repository's real total is NOT complete, whatever the
     Link header said;
  2. a short walk never overwrites a manifest that holds more;
  3. a manifest that is WRONG about its own completeness cannot defend its hole
     forever — a bigger walk replaces it;
  4. a page that once had a successor keeps it, so one bad response does not
     write next=None into the cache and break every later cycle too.

No network. The pages come from a stub.

    python3 tests/check_walk_guard.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp(prefix="walk-guard-")
# Set before the import: the state root is read at module scope, and a test that
# mined into the operator's real state directory would be a test that broke the
# thing it was checking.
os.environ["FIX_OBSERVATORY_STATE"] = TMP
os.environ["FIX_OBSERVATORY_WALK_ATTEMPTS"] = "1"
# The stub project carries no token, and an untokened cycle is capped at three
# pages — which would make every walk here a short one for the wrong reason.
os.environ["FIX_OBSERVATORY_MAX_PAGES"] = "200"
sys.path.insert(0, str(ROOT))
import observatory as obs  # noqa: E402

REAL_API_PAGE = obs.api_page
# The miner narrates every cycle, and this file runs three of them in the middle
# of bin/verify's output. What each cycle decided is asserted against the
# manifest it did or did not write, so the narration is noise here.
obs.log = lambda *a, **k: None

fails = []


def check(label, cond, detail=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ")
          + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(label)


def artifact(n):
    return {"number": n, "kind": "issue", "title": f"#{n}", "author": "a",
            "opened_at": "2026-01-01T00:00:00Z", "closed_at": None,
            "closed": False, "merged": False, "state_reason": None,
            "labels": [], "attribution": "none",
            "smell": {"score": 0, "signals": []}, "marker": None,
            "comments": 0, "url": ""}


def run_mine(served_pages, expected_total, prev=None):
    """One mine against a stub that offers `served_pages` pages and then stops."""
    proj = obs.Project("stub", "o/r")
    proj.cache_loaded = True
    proj.dir.mkdir(parents=True, exist_ok=True)
    if prev is not None:
        proj.manifest_path.write_text(json.dumps(prev))
    elif proj.manifest_path.exists():
        proj.manifest_path.unlink()

    def fake_page(path, row_fn=None, p=None):
        if path.startswith("/repos/o/r/issues?"):
            page = int(path.rsplit("cursor=", 1)[-1]) if "cursor=" in path else 1
            rows = [artifact(page * 100 + i) for i in range(100)]
            nxt = (f"/repos/o/r/issues?cursor={page + 1}"
                   if page < served_pages else None)
            return rows, nxt
        return [], None

    obs.api_page = fake_page
    obs.artifact_total = lambda repo, p=None: (expected_total, False)
    obs.api = lambda path, p=None: {"open_issues_count": 1,
                                    "created_at": "2025-06-01T00:00:00Z"}
    obs.project = lambda slug=None: proj
    proj.save_cache = lambda: None
    obs.mine_once(proj)
    if not proj.manifest_path.exists():
        return None
    return json.loads(proj.manifest_path.read_text())


print("\n\033[1mwalk guard\033[0m")

# 1. A truncated walk is not complete, however the stream ended.
m = run_mine(4, 9972)
cov = (m or {}).get("coverage", {})
check("a walk 400 of 9,972 long is recorded as incomplete",
      m is not None and cov.get("complete") is False,
      f"complete={cov.get('complete')}")
check("the shortfall is named in the manifest's error",
      bool(m and m.get("error") and "truncated" in m["error"]),
      repr((m or {}).get("error")))
check("the real total is carried, so the page can show a denominator",
      cov.get("repo_artifact_total") == 9972,
      repr(cov.get("repo_artifact_total")))

# 2. A short walk never overwrites a bigger manifest.
prev = {"repo": "o/r", "artifacts": [artifact(i) for i in range(9963)],
        "coverage": {"complete": True, "fetched_count": 9963}}
m = run_mine(4, 9972, prev=prev)
check("a 400-artifact cycle leaves a 9,963-artifact manifest alone",
      m is not None and len(m["artifacts"]) == 9963,
      f"{len(m['artifacts']) if m else None} artifacts on disk")

# 3. A manifest that is wrong about its own completeness cannot hold the hole.
poisoned = {"repo": "o/r", "artifacts": [artifact(i) for i in range(400)],
            "coverage": {"complete": True, "fetched_count": 400}}
m = run_mine(30, 9972, prev=poisoned)
check("a bigger walk replaces a manifest that wrongly claimed completeness",
      m is not None and len(m["artifacts"]) == 3000,
      f"{len(m['artifacts']) if m else None} artifacts on disk")

# 4. A page that once had a successor keeps it. The real api_page, not the stub
# the mine tests installed over it.
obs.api_page = REAL_API_PAGE


class FakeRes:
    headers = {"Link": "", "ETag": "e2"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


proj = obs.Project("stub2", "o/r")
proj.cache = {"/p": {"etag": "e", "body": [1, 2], "next": "/p2"}}
proj.cache_loaded = True
obs.urlopen = lambda *a, **k: FakeRes()
obs.json.load = lambda f: []
body, nxt = obs.api_page("/p", None, proj)
check("a response that forgets its next link does not erase the known one",
      nxt == "/p2" and proj.cache["/p"]["next"] == "/p2",
      f"next={nxt!r} cached={proj.cache['/p'].get('next')!r}")

print()
if fails:
    print(f"\033[31m{len(fails)} walk-guard check(s) failed\033[0m")
    sys.exit(1)
print("\033[32mwalk guard holds\033[0m")
