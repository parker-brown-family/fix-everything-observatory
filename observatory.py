#!/usr/bin/env python3
"""Fix-Everything Observatory — miner + server for the Omarchy repair-swarm visualizer.

Mines omacom/omarchy issues/PRs, repo-wide comments, and repo-wide issue events;
scores each artifact for agent smell; writes data/manifest.{json,js}; serves
app/swarm.html on 127.0.0.1:4517.

Doctrine:
- The omarchy-fix-event:v1 marker (contract/omarchy-fix-event-v1.md) is the only
  definitive attribution; smell signals are named, scored heuristics.
- Unknown is never zero: coverage gaps, rate budget, and horizon are recorded.
- classify() always returns an explicit attribution, so every artifact this
  miner writes carries one. The page still keeps a fifth value, 'unmeasured',
  for a manifest that does not — it renders as a hollow mote and reaches an
  allocated agent's prompt spelled out, because a hole is not a clean score.
- All requests are conditional (ETags); 304s are free against the rate limit.

Stdlib only. With GITHUB_TOKEN / GH_TOKEN every stream is walked to its end;
without one the 60/hour ceiling allows only the newest few pages, and the
manifest says so rather than letting the shortfall read as an empty repo.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def _state_dir() -> Path:
    """Where the mined history lives — deliberately not inside the install.

    ROOT is the program: app/, seed/, and read-only the moment this is anything
    but a git clone. What the miner writes has to outlive an upgrade and a
    reinstall, so it goes where the XDG base-directory spec puts state a user
    never chose but would miss. FIX_OBSERVATORY_STATE overrides it, which is
    also how a second instance gets a history of its own.
    """
    override = os.environ.get("FIX_OBSERVATORY_STATE")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")
    return Path(base).expanduser().resolve() / "fix-everything-observatory"


DATA = _state_dir()
CACHE_PATH = DATA / "http-cache.json"
# Where it used to live, and still does for anyone upgrading in place.
LEGACY_DATA = ROOT / "data"
# A fresh clone has no manifest, and building one is ~590 conditional round trips
# and thirteen minutes. Rather than show an empty instrument for that whole time,
# we commit one mined manifest, gzipped, and serve it until the live one lands.
# It is a picture of a real past, not a placeholder: its own fetched_at travels
# with it, the page labels it, and the coverage block is the one that was true
# when it was mined.
SEED_DIR = ROOT / "seed"
SEED_JS_GZ = SEED_DIR / "manifest.js.gz"
SEED_META = SEED_DIR / "manifest.meta.json"
REPO = os.environ.get("FIX_OBSERVATORY_REPO", "omacom/omarchy")
PORT = int(os.environ.get("FIX_OBSERVATORY_PORT", "4517"))
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
# Authenticated we get 5,000 requests an hour, which is enough to walk every
# stream to its end (~600 pages for omarchy) — so we do, and order ascending
# because then the cursors and the ETags of everything but the last page are
# stable and later cycles cost nothing. Unauthenticated, 60/hour makes that
# impossible; we take the NEWEST pages instead and record the truncation.
COMPLETE = bool(TOKEN)
ORDER = "asc" if COMPLETE else "desc"
MAX_PAGES = int(os.environ.get("FIX_OBSERVATORY_MAX_PAGES", "1500" if TOKEN else "3"))
# Every comment ships as a tick so the event lane is honest across the whole
# span; only the newest carry their text, because 20k snippets is ~7MB the
# browser would re-parse on every load.
SNIPPET_KEEP = int(os.environ.get("FIX_OBSERVATORY_SNIPPETS", "1500"))
# GitHub stops paginating /issues/events at 300 pages and simply withholds the
# next link. Walking to "no next link" there reaches the CAP, not the end of the
# stream, and the difference is measurable: omarchy's events then begin in
# October 2025 for a repo whose issues begin in June. Reaching a documented
# ceiling is not the same finding as exhausting a stream, so we do not record it
# as one.
EVENT_PAGE_CAP = 300
# An exhaustive cycle is ~600 conditional round trips. They cost nothing against
# the rate limit (a 304 is free) but they cost wall clock, so it beats slower.
INTERVAL = int(os.environ.get("FIX_OBSERVATORY_INTERVAL", "900" if TOKEN else "300"))
# One-click agent allocation, the omarchy error-notification pattern pointed at a
# ticket: the page POSTs an issue number, the server writes a context-rich prompt
# and opens a terminal running `claude` primed on it. Local instances only — the
# server binds 127.0.0.1, and a hosted copy of the page never renders the button.
#
# OFF unless the person running the server turned it on: a marketplace install
# must not ship a process-spawning endpoint armed, however local. The bar
# widget's settings toggle sets this flag on the launch it makes; /api/caps
# tells the page which posture this server was born with, so the button only
# renders against a server that would honour it. The flag is read once at
# start on purpose — an armed/disarmed state that could be flipped over an
# unauthenticated local socket would not be a posture, just a request away.
ALLOW_AGENTS = os.environ.get("FIX_OBSERVATORY_ALLOW_AGENTS") == "1"
AGENT_CMD = os.environ.get("FIX_OBSERVATORY_AGENT_CMD")   # shell template; {prompt_file}
AGENT_CWD = os.environ.get("FIX_OBSERVATORY_AGENT_CWD", str(Path.home()))
MIN_BUDGET = 8  # skip a cycle rather than spend the last requests

MARKER_RE = re.compile(r"<!--\s*omarchy-fix-event:v(\d+)\s*(.*?)-->", re.S)
KV_RE = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*(.*?)\s*$")
ISSUE_URL_RE = re.compile(r"/issues/(\d+)$")

# ---- agent-smell signals: (name, weight, predicate(title, body)) -----------
AI_TRAILER_RE = re.compile(
    r"generated with (claude|github copilot|copilot|cursor|codex|gemini|aider)"
    r"|co-authored-by:.*?(claude|copilot|codex|gemini|aider|\[bot\]|noreply@anthropic)"
    r"|\U0001F916 generated"
    r"|generated by (an? )?(ai|llm|agent)", re.I)
AGENT_PHRASE_RE = re.compile(
    r"this (pr|pull request|issue|patch) (was )?(created|opened|generated|submitted)"
    r" (automatically|by an? (ai|agent|bot|assistant))"
    r"|automated (fix|patch|report)"
    r"|one[- ]click (fix|repair|report)", re.I)
CLAUDE_TEMPLATE_RE = re.compile(r"##\s*summary[\s\S]{0,600}##\s*test plan", re.I)
CONV_TITLE_RE = re.compile(r"^(fix|feat|chore|refactor|docs|ci|build|perf|style)[(:!]", re.I)
ERROR_FP_RE = re.compile(
    r"```[\s\S]{0,80}?(traceback \(most recent call last\)|panicked at|segmentation fault"
    r"|core dumped|stack trace|assertion failed)", re.I)
FIXES_RE = re.compile(r"\b(fixes|closes|resolves)\s+#\d+", re.I)
EMOJI_TITLE_RE = re.compile(r"^[☀-➿\U0001F300-\U0001FAFF]")


def is_bot(user) -> bool:
    user = user or {}
    return user.get("type") == "Bot" or (user.get("login") or "").endswith("[bot]")


def smell_of(row) -> dict:
    title = row.get("title") or ""
    body = row.get("body") or ""
    signals = []
    if is_bot(row.get("user")):
        signals.append(("bot-author", 2))
    if AI_TRAILER_RE.search(body):
        signals.append(("ai-trailer", 2))
    if AGENT_PHRASE_RE.search(body) or AGENT_PHRASE_RE.search(title):
        signals.append(("agent-phrase", 2))
    if CLAUDE_TEMPLATE_RE.search(body):
        signals.append(("claude-template", 2))
    if CONV_TITLE_RE.search(title) and len(title) > 40:
        signals.append(("conventional-title", 1))
    if ERROR_FP_RE.search(body) and FIXES_RE.search(body):
        signals.append(("error-fingerprint", 1))
    if EMOJI_TITLE_RE.match(title.strip()):
        signals.append(("emoji-title", 1))
    return {"score": sum(w for _, w in signals), "signals": [n for n, _ in signals]}


def parse_marker(body):
    hit = MARKER_RE.search(body or "")
    if not hit:
        return None
    fields = {"version": int(hit.group(1))}
    for line in hit.group(2).splitlines():
        m = KV_RE.match(line.strip())
        if m:
            v = m.group(2).strip()
            fields[m.group(1)] = None if v.lower() in ("null", "") else v
    return fields


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}", flush=True)


# ---- conditional HTTP with a tiny on-disk cache -----------------------------
_cache: dict = {}
RATE: dict = {}


# Cached bodies are DISTILLED rows, not GitHub's. Raw, the ~600 pages of a whole
# repo are ~150MB rewritten every cycle; the fields we keep are ~14MB. Bump this
# whenever a row shape changes, or a 304 will serve a body of the old shape.
CACHE_VERSION = 2


def load_cache() -> None:
    global _cache
    try:
        blob = json.loads(CACHE_PATH.read_text())
        _cache = blob["entries"] if blob.get("v") == CACHE_VERSION else {}
    except Exception:
        _cache = {}


def save_cache() -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({"v": CACHE_VERSION, "entries": _cache}))
    except Exception as exc:
        log(f"cache save failed: {exc}")


def adopt_legacy_data() -> None:
    """Carry a pre-0.2 in-tree data/ across to the state directory, once.

    Until 0.2 everything the miner wrote sat beside the program, so replacing
    the program replaced the history with it. Anyone who already has one has
    spent thirteen minutes earning it and should not have to again. Copy rather
    than move, and only into a state directory that does not yet exist: if any
    of this goes wrong the old directory is untouched and the worst case is a
    re-mine rather than a loss. Only data/ travels — seed/ is part of the
    program, and a copy of it in the state directory would outlive the install
    that owns it and go on being served after an upgrade replaced it.
    """
    # Guarded on the manifest, not on the directory: the launcher creates the
    # state directory before this ever runs, so "does it exist" is always true
    # and would skip every migration there is.
    if (DATA / "manifest.json").exists() or not LEGACY_DATA.is_dir():
        return
    if not (LEGACY_DATA / "manifest.json").is_file():
        return
    carried = 0
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        for src in sorted(LEGACY_DATA.iterdir()):
            if src.is_file() and not (DATA / src.name).exists():
                shutil.copy2(src, DATA / src.name)
                carried += 1
    except Exception as exc:
        log(f"could not carry the mined history across to {DATA}: {exc}")
        return
    if carried:
        log(f"carried {carried} file(s) of mined history from {LEGACY_DATA} "
            f"to {DATA} — the old copy is left where it is")


# ---- the committed seed ------------------------------------------------------
def seed_meta() -> dict | None:
    """What the committed seed holds, or None if there isn't a usable one.

    Read from a tiny sidecar so nothing has to decompress 11MB to answer
    "which repo is this a picture of?" — and the answer matters: a seed of
    omarchy served into an observatory pointed at some other repo would be a
    confident, wrong instrument.
    """
    try:
        meta = json.loads(SEED_META.read_text())
    except Exception:
        return None
    if not SEED_JS_GZ.exists() or meta.get("repo") != REPO:
        return None
    return meta


def write_seed() -> str:
    """Freeze the manifest on disk into the committed seed.

    A maintainer verb, not a user one: it writes into the program's own
    directory, which an installed copy has no business being able to do. Refuse
    early and say which it is, rather than failing on the write with a
    permission error that reads like a bug.
    """
    if not os.access(SEED_DIR if SEED_DIR.is_dir() else ROOT, os.W_OK):
        raise SystemExit(
            f"--seed freezes a new seed into {SEED_DIR}, and this copy is "
            f"installed read-only. Run it in a working tree.")
    manifest = json.loads((DATA / "manifest.json").read_text())
    manifest["seed"] = True
    cov = manifest.get("coverage") or {}
    SEED_DIR.mkdir(exist_ok=True)
    body = ("window.SWARM_DATA = " + json.dumps(manifest, indent=1) + ";\n").encode()
    # mtime=0 so regenerating an unchanged manifest produces identical bytes and
    # git records no new 1MB blob.
    with gzip.GzipFile(filename="", mode="wb", fileobj=SEED_JS_GZ.open("wb"),
                       compresslevel=9, mtime=0) as fh:
        fh.write(body)
    meta = {
        "repo": manifest.get("repo"),
        "fetched_at": manifest.get("fetched_at"),
        "complete": bool(cov.get("complete")),
        "artifacts": len(manifest.get("artifacts") or []),
        "comments": len(manifest.get("comments") or []),
        "events": len(manifest.get("events") or []),
        "bytes": SEED_JS_GZ.stat().st_size,
    }
    SEED_META.write_text(json.dumps(meta, indent=1) + "\n")
    return (f"seed written: {meta['artifacts']} artifacts / {meta['comments']} comments "
            f"/ {meta['events']} events, mined {meta['fetched_at']}, "
            f"{meta['bytes'] / 1048576:.1f}MB gzipped → {SEED_JS_GZ}")


def _note_rate(headers) -> None:
    global RATE
    rem, lim, res = (headers.get("X-RateLimit-Remaining"),
                     headers.get("X-RateLimit-Limit"),
                     headers.get("X-RateLimit-Reset"))
    if rem is not None:
        RATE = {"remaining": int(rem), "limit": int(lim or 0),
                "reset": int(res or 0)}


LINK_NEXT_RE = re.compile(r'<https://api\.github\.com([^>]+)>;\s*rel="next"')


def api_page(path: str, row_fn=None):
    """Conditional GET; returns (body, next_path or None). 304 serves the cache.

    The next page comes from the server's own Link header, not from an
    incremented page number: these endpoints have moved to opaque cursors, and
    following the link is the only way to reach the end of one.

    `row_fn` distils each row before it is cached — a row that returns None is
    dropped. Nothing downstream ever sees GitHub's full objects, which is what
    keeps a whole-repo cache in megabytes rather than hundreds of them.
    """
    headers = {
        "User-Agent": "fix-everything-observatory/2.0 (+https://wecanfixeverything.com)",
        "Accept": "application/vnd.github+json",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    ent = _cache.get(path)
    if ent and ent.get("etag"):
        headers["If-None-Match"] = ent["etag"]
    try:
        with urlopen(Request("https://api.github.com" + path, headers=headers),
                     timeout=30) as res:
            _note_rate(res.headers)
            raw = json.load(res)
            body = raw if row_fn is None else [
                x for x in (row_fn(r) for r in raw) if x is not None]
            m = LINK_NEXT_RE.search(res.headers.get("Link") or "")
            nxt = m.group(1) if m else None
            _cache[path] = {"etag": res.headers.get("ETag"), "body": body,
                            "next": nxt}
            return body, nxt
    except HTTPError as e:
        if e.code == 304 and ent:
            _note_rate(e.headers)
            m = LINK_NEXT_RE.search(e.headers.get("Link") or "")
            return ent["body"], (m.group(1) if m else ent.get("next"))
        raise


def api(path: str):
    """One object, no pagination."""
    return api_page(path)[0]


def budget_low() -> bool:
    if not RATE:
        return False
    if RATE.get("remaining", 999) >= MIN_BUDGET:
        return False
    return RATE.get("reset", 0) > time.time()


# ---- mining ------------------------------------------------------------------
def fetch_all(path: str, row_fn=None, cap: int = MAX_PAGES):
    """Walk a list endpoint to its end, or until `cap` pages / the rate budget.

    Returns (rows, complete, err, pages). `complete` is true ONLY when the
    server offered no next page. A cap, an error or a budget stop leaves it
    false, because a truncated stream and an exhausted one are not the same
    finding, and every statistic downstream depends on telling them apart.
    """
    rows, complete, err, pages = [], False, None, 0
    while path and pages < cap:
        if pages and budget_low():
            err = err or f"rate budget spent after {pages} pages"
            break
        try:
            batch, nxt = api_page(path, row_fn)
        except (HTTPError, URLError, OSError) as exc:
            err = f"{path}: {exc}"
            break
        pages += 1
        rows.extend(batch or [])
        # The end of a stream is the server withholding a next link, and nothing
        # else. An empty page is NOT the end: row_fn drops what we do not keep,
        # and a page of events that are all "subscribed" distils to nothing while
        # three hundred pages still wait behind it. That mistake cost the event
        # stream 293 of its 300 pages and reported complete=True over the hole.
        if not nxt:
            complete = True
            break
        path = nxt
    return rows, complete, err, pages


def classify(marker, smell) -> str:
    if marker:
        return "marker"
    if smell["score"] >= 2:
        return "smell"
    if smell["score"] == 1:
        return "hint"
    return "none"


def issue_number_of(comment) -> int | None:
    m = ISSUE_URL_RE.search(comment.get("issue_url") or "")
    return int(m.group(1)) if m else None


def clean_snippet(text: str, n: int = 220) -> str:
    text = MARKER_RE.sub("", text or "")
    text = re.sub(r"```[\s\S]*?```", "[code]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


KEEP_EVENTS = {"closed", "reopened", "merged", "labeled", "referenced",
               "ready_for_review", "review_requested"}


def issue_row(r):
    pr = r.get("pull_request")
    marker = parse_marker(r.get("body"))
    smell = smell_of(r)
    user = r.get("user") or {}
    return {
        "kind": "pr" if pr is not None else "issue",
        "number": r.get("number"),
        "title": r.get("title"),
        "url": r.get("html_url"),
        "author": user.get("login"),
        "author_is_bot": is_bot(user),
        "opened_at": r.get("created_at"),
        "closed_at": r.get("closed_at"),          # null while open — never zero
        "merged_at": (pr or {}).get("merged_at"),  # null = unmerged OR not a PR
        "state": r.get("state"),
        "state_reason": r.get("state_reason"),
        "labels": [l.get("name") for l in r.get("labels") or []],
        "comments": r.get("comments"),
        "attribution": classify(marker, smell),
        "smell": smell,
        "marker": marker,
    }


def comment_row(c):
    n = issue_number_of(c)
    if n is None:
        return None
    cu = c.get("user") or {}
    return {
        "id": c.get("id"), "number": n,
        "author": cu.get("login"), "author_is_bot": is_bot(cu),
        "created_at": c.get("created_at"),
        "snippet": clean_snippet(c.get("body")),
        "url": c.get("html_url"),
    }


def event_row(e):
    if e.get("event") not in KEEP_EVENTS:
        return None
    issue = e.get("issue") or {}
    if issue.get("number") is None:
        return None
    return {
        "id": e.get("id"), "type": e.get("event"),
        "number": issue.get("number"),
        "actor": (e.get("actor") or {}).get("login"),
        "created_at": e.get("created_at"),
        "label": (e.get("label") or {}).get("name"),
    }


def mine_once() -> None:
    if budget_low():
        reset = datetime.fromtimestamp(RATE.get("reset", 0), timezone.utc)
        log(f"rate budget low ({RATE.get('remaining')}) — cycle skipped, "
            f"resets {reset.isoformat(timespec='minutes')}")
        return

    arts, issues_complete, err, issue_pages = fetch_all(
        f"/repos/{REPO}/issues?state=all&sort=created&direction={ORDER}"
        "&per_page=100", issue_row)
    comments, comments_complete, c_err, comment_pages = fetch_all(
        f"/repos/{REPO}/issues/comments?sort=created&direction={ORDER}"
        "&per_page=100", comment_row)
    events, events_complete, e_err, event_pages = fetch_all(
        f"/repos/{REPO}/issues/events?per_page=100", event_row)
    err = err or c_err or e_err
    arts = [a for a in arts if a["number"] is not None]
    events_capped = event_pages >= EVENT_PAGE_CAP
    if events_capped:
        events_complete = False

    meta = None
    try:
        meta = api(f"/repos/{REPO}")
    except (HTTPError, URLError, OSError) as exc:
        err = err or f"repo meta: {exc}"

    comments.sort(key=lambda c: c["created_at"] or "")
    snippets_from = comments[0]["created_at"] if comments else None
    if len(comments) > SNIPPET_KEEP:
        snippets_from = comments[-SNIPPET_KEEP]["created_at"]
        for c in comments[:-SNIPPET_KEEP]:
            c["snippet"] = None      # never fetched-and-empty; not carried
            c["url"] = None

    events.sort(key=lambda e: e["created_at"] or "")

    manifest_path = DATA / "manifest.json"
    if not arts and err and manifest_path.exists():
        log(f"mine failed ({err}) — keeping previous manifest")
        save_cache()
        return

    # A slice must never overwrite a walk. An untokened cycle sees 300 of 8,876
    # artifacts and would otherwise replace fifteen months of history with two
    # days of it — a strictly worse manifest that reads as authoritative, and
    # whose "born, prior 7d" is a zero nobody measured. Observed exactly once,
    # by starting the server without passing the token through.
    if not issues_complete and manifest_path.exists():
        try:
            prev = json.loads(manifest_path.read_text())
        except Exception:
            prev = None
        if (prev and prev.get("repo") == REPO
                and (prev.get("coverage") or {}).get("complete")):
            log(f"this cycle is a slice ({len(arts)} artifacts) and the manifest "
                f"on disk was walked to the end — keeping the complete one. "
                f"A token is what raises the horizon.")
            save_cache()
            return

    # The same rule, against the committed seed. Without this, an untokened first
    # run writes 300 artifacts over a served seed of 8,887 and the swarm SHRINKS
    # on its first successful mine — fresher by two days, blind by fifteen months.
    # Stale-and-whole beats fresh-and-truncated for an instrument about long arcs,
    # and the page dates the seed so nobody mistakes it for now.
    if not issues_complete and not manifest_path.exists():
        sm = seed_meta()
        if sm and sm.get("complete"):
            log(f"this cycle is a slice ({len(arts)} artifacts) and the committed "
                f"seed was walked to the end — serving the seed, writing nothing. "
                f"A token is what raises the horizon.")
            save_cache()
            return

    opened = [a["opened_at"] for a in arts if a["opened_at"]]
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "schema": "fix-everything-manifest:v2",
        "repo": REPO,
        "fetched_at": now_iso,
        "error": err,
        "coverage": {
            "per_page": 100, "order": ORDER,
            "issue_pages": issue_pages,
            "comment_pages": comment_pages,
            "event_pages": event_pages,
            "complete": issues_complete,
            "fetched_count": len(arts),
            "oldest_fetched": min(opened) if opened else None,
            "comments_complete": comments_complete,
            "comments_count": len(comments),
            "oldest_comment": comments[0]["created_at"] if comments else None,
            "snippets_from": snippets_from,
            "events_complete": events_complete,
            "events_capped": events_capped,
            "events_count": len(events),
            "oldest_event": events[0]["created_at"] if events else None,
            "repo_open_issues": meta.get("open_issues_count") if meta else None,
            "repo_created_at": meta.get("created_at") if meta else None,
            "authenticated": bool(TOKEN),
            "api": ({"remaining": RATE.get("remaining"),
                     "limit": RATE.get("limit"),
                     "reset_at": datetime.fromtimestamp(
                         RATE["reset"], timezone.utc).isoformat(timespec="minutes")
                     if RATE.get("reset") else None} if RATE else None),
        },
        "artifacts": arts,
        "comments": comments,
        "events": events,
    }

    DATA.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest, indent=1)
    manifest_path.write_text(body + "\n")
    (DATA / "manifest.js").write_text("window.SWARM_DATA = " + body + ";\n")
    save_cache()
    counts = {}
    for a in arts:
        counts[a["attribution"]] = counts.get(a["attribution"], 0) + 1
    log(f"mined {len(arts)} artifacts {counts} "
        f"comments={len(comments)} events={len(events)} "
        f"pages={issue_pages}/{comment_pages}/{event_pages} "
        f"complete={issues_complete}/{comments_complete}/{events_complete} "
        f"api_remaining={RATE.get('remaining', '?')} err={err}")


# ---- agent allocation ----------------------------------------------------------
def find_terminal():
    for t in ([os.environ.get("TERMINAL")] if os.environ.get("TERMINAL") else []) + [
            "alacritty", "ghostty", "kitty", "foot", "wezterm", "xterm"]:
        if t and shutil.which(t):
            return t
    return None


# The prompt is the entire briefing an allocated agent ever gets, so it carries
# four things the ticket itself does not. What KIND of job this is: a bug report
# is diagnosed, a proposed change is REVIEWED, and telling a reviewer to "state
# what the failure actually is" invents a failure for a PR that is working as
# intended. Where the deliverable goes: a report that ends in the agent's
# scrollback is a report nobody read. What machine it is standing on: this box
# is a live Omarchy install, which is both the honest reproduction surface and
# the thing it can break. And what our own attribution field means, which is
# private vocabulary a fresh agent has never seen.
ATTRIBUTION_GLOSS = {
    "marker": "carries the omarchy-fix-event:v1 marker — definitively autospawned",
    "smell": "scored >= 2 on our named agent-smell signals — probably agent-written",
    "hint": "one weak agent-smell signal — suggestive, not evidence",
    "none": "no agent signal in the title or body — human, as far as we looked",
}


def attribution_phrase(art) -> str:
    """Absent is not "none".

    An artifact whose attribution was never recorded is UNMEASURED, and the
    prompt has to say so: "none" tells the agent we scored this ticket and it
    came up clean, which is a different claim from never having scored it.
    """
    value = art.get("attribution")
    if not value:
        return "unmeasured — never scored, which is NOT the same as scoring clean"
    gloss = ATTRIBUTION_GLOSS.get(value, "unrecognised class; treat as unmeasured")
    return f"{value} — {gloss}"


ISSUE_JOB = [
    "2. Orient: find the code, config, or subsystem this points at, and state",
    "   what the failure actually is in your own words.",
    "3. If it can be reproduced safely on this machine, try; otherwise say",
    "   exactly what a reproduction would need.",
    "4. Deliver: a diagnosis hypothesis, the check that would confirm or refute",
    "   it, and concrete suggested next steps (or a fix sketch).",
]

PR_JOB = [
    "2. Read the change itself:  gh pr diff {n} --repo {repo}",
    "3. Assess the CLAIM, not a failure — this is a proposed change, and there",
    "   may be nothing wrong with it. Does the diff do what its description",
    "   says? Is that the right thing to do here? Name what it breaks, what it",
    "   leaves unhandled, and what it duplicates.",
    "4. Exercise it only through steps you can revert — read the files it",
    "   touches, check it out in a scratch clone. Say plainly what you did NOT",
    "   run, and why.",
    "5. Deliver a verdict — MERGE / CHANGES REQUESTED / DECLINE — with specific",
    "   reasons, per hunk where it matters.",
]


def report_path(number) -> Path:
    return DATA / f"agent-report-{number}.md"


def agent_prompt(art, comments) -> str:
    kind = art.get("kind") or "issue"
    n = art.get("number")
    gh_verb = "pr" if kind == "pr" else "issue"
    recent = [c for c in comments if c.get("number") == n and c.get("snippet")][-3:]
    lines = [
        "You are a disposable repair agent, allocated with one click from the",
        "Fix-Everything Observatory for this ticket:",
        "",
        f"  {REPO}#{n} — {art.get('title') or '(untitled)'}",
        f"  {art.get('url') or ''}",
        f"  {kind} · opened {art.get('opened_at')} by @{art.get('author')}",
        f"  attribution: {attribution_phrase(art)}",
    ]
    if art.get("labels"):
        lines.append("  labels: " + ", ".join(art["labels"]))
    if recent:
        lines += [""] + ["Recent comments:"] + [
            f"  - @{c.get('author')}: \"{c.get('snippet')}\"" for c in recent]
    job = PR_JOB if kind == "pr" else ISSUE_JOB
    lines += [
        "",
        "Your job, in order:",
        f"1. Read the whole thread:  gh {gh_verb} view {n} --repo {REPO} --comments",
    ] + [step.format(n=n, repo=REPO) for step in job] + [
        "",
        "Write the deliverable here — markdown, and it IS the report.",
        "Scrollback is not: this terminal is disposable and nobody will",
        "scroll it.",
        "",
        f"  {report_path(n)}",
        "",
        "Say what you checked, what you could NOT check, and what you are",
        "only guessing. Unknown is not zero here either.",
        "",
        "This machine is a LIVE OMARCHY INSTALL — the same system the ticket is",
        "about. That makes it the honest reproduction surface and the hazard at",
        "once. Read anything; run nothing that installs, overwrites, or updates",
        "in order to test a theory. Prefer a copy under /tmp to touching",
        "~/.config or ~/.local/share/omarchy, and never run omarchy-update.",
        "",
        "Do NOT post to GitHub or take any public action unless explicitly asked.",
        "",
    ]
    return "\n".join(lines)


# What the terminal runs when we spawn `claude` ourselves. It holds the window
# open on ANY nonzero exit and says what the failure means, because the button
# has already told the user "AGENT SPAWNED" by the time this fires. The one
# that bit us: Claude Code v2.1.251 could not resolve the configured model
# alias and died with "There's an issue with the selected model (default)" —
# an agent dead on arrival behind a button that looked like it worked. We
# cannot preflight that (proving the model resolves costs a real session), so
# we name the fix where the failure actually surfaces.
AGENT_SHELL = (
    'claude "$(cat {prompt})"; rc=$?; [ "$rc" -eq 0 ] && exit 0; echo; '
    'echo "[fix-everything-observatory] claude exited $rc — the agent never ran."; '
    'echo "  If it named a model it does not recognise, your Claude Code is too'
    ' old for your configured model. Fix:  mise upgrade claude"; '
    'echo "  The prompt is kept at {prompt} — nothing was lost."; '
    'echo; echo "[enter closes this window]"; read -r'
)
PREFLIGHT_TIMEOUT = 6


def mise_outdated(tool: str):
    """(installed, latest) when mise says the tool is behind — else None.

    None means UNKNOWN, never "up to date": mise may be absent, may not manage
    this tool, or may fail. `mise outdated` lists only what IS behind, so a line
    for the tool is the finding and no line is silence, not a clean bill.
    """
    if not shutil.which("mise"):
        return None
    try:
        p = subprocess.run(["mise", "outdated", tool], capture_output=True,
                           text=True, timeout=PREFLIGHT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (p.stdout or "").splitlines():
        f = line.split()
        if len(f) >= 4 and f[0] == tool:
            return f[2], f[3]
    return None


def claude_preflight():
    """Is the agent we are about to spawn runnable at all? -> (ok, note).

    Deliberately modest about what it can prove. That `claude` exists on PATH
    and answers `--version` is checkable in a few milliseconds and worth
    refusing on. That its configured model resolves is NOT checkable without
    paying for a session, so this never claims it — a note is a warning the
    page shows beside a spawn that still happens, never a silent pass.
    """
    exe = shutil.which("claude")
    if not exe:
        return False, ("no `claude` on PATH — install Claude Code, or point "
                       "FIX_OBSERVATORY_AGENT_CMD at your own agent")
    try:
        p = subprocess.run([exe, "--version"], capture_output=True, text=True,
                           timeout=PREFLIGHT_TIMEOUT, env=clean_agent_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return True, f"`claude --version` did not answer ({exc}) — spawning anyway"
    if p.returncode != 0:
        return True, (f"`claude --version` exited {p.returncode} — spawning anyway; "
                      "if the terminal dies on a model error, run `mise upgrade claude`")
    ver = (p.stdout or "").strip()
    behind = mise_outdated("claude")
    if behind:
        return True, (f"claude {behind[0]} is behind {behind[1]} — an older Claude Code "
                      "cannot resolve every configured model, and that failure lands "
                      "inside the spawned terminal. Fix: mise upgrade claude")
    return True, f"claude {ver}" if ver else None


def clean_agent_env():
    """The environment a freshly-launched claude should see — never a child of us.

    If the tracker server was itself started from inside a Claude Code session
    (running `serve` from a claude shell, say), it inherits that session's
    CLAUDE_CODE_* markers, and a naive spawn passes them down: the allocated
    agent then comes up as a CHILD session with transcript saving off and a
    pinned model it may not resolve. Stripping every CLAUDE_CODE_* var (and a
    couple of model pins) makes it a normal top-level session that reads the
    user's settings fresh — the same session they'd get typing `claude`.
    """
    drop = ("CLAUDE_CODE_", "CLAUDECODE", "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL")
    return {k: v for k, v in os.environ.items() if not k.startswith(drop)}


def allocate_agent(number: int):
    """Returns (error, warning). Either may be None; an error means no spawn."""
    try:
        manifest = json.loads((DATA / "manifest.json").read_text())
    except Exception as exc:
        return f"manifest unreadable: {exc}", None
    art = next((a for a in manifest.get("artifacts", [])
                if a.get("number") == number), None)
    if art is None:
        return f"#{number} is not in the manifest", None
    pf = DATA / f"agent-prompt-{number}.md"
    pf.write_text(agent_prompt(art, manifest.get("comments") or []))
    q = shlex.quote(str(pf))
    # A custom agent command is the operator's business — we preflight only the
    # `claude` we chose to run ourselves.
    note = None
    if AGENT_CMD:
        cmd = ["bash", "-lc", AGENT_CMD.format(prompt_file=q)]
    else:
        term = find_terminal()
        if not term:
            return "no terminal emulator found — set FIX_OBSERVATORY_AGENT_CMD", None
        ok, note = claude_preflight()
        if not ok:
            return note, None
        cmd = [term, "-e", "bash", "-lc", AGENT_SHELL.format(prompt=q)]
    try:
        subprocess.Popen(cmd, cwd=AGENT_CWD, start_new_session=True,
                         env=clean_agent_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return f"spawn failed: {exc}", None
    log(f"allocated agent for #{number} ({cmd[0]}"
        f"{'; ' + note if note else ''})")
    return None, note


# ---- server -------------------------------------------------------------------
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: N802 — stdlib name
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — stdlib name
        # What this server is willing to do, so the page never draws a button
        # the server would refuse. One static answer per process lifetime.
        if self.path == "/api/caps":
            self._json(200, {"allocate": ALLOW_AGENTS})
            return
        # Until the first cycle finishes, hand over the committed seed under the
        # live manifest's own name — the page asks for one thing and gets the
        # best picture that exists. Gzip goes over the wire as gzip: 11MB of JSON
        # is 1.2MB compressed, and the browser inflates it for free.
        if self.path.split("?")[0] == "/data/manifest.js" and \
                not (DATA / "manifest.js").exists() and seed_meta():
            blob = SEED_JS_GZ.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
            return
        # /data/ is a URL the page asks for, and no longer a directory beneath
        # the served root. Route it explicitly at the state directory: the
        # fall-through below resolves against ROOT, which holds the program and
        # not the history, so without this every mined manifest 404s while the
        # seed branch above stops firing the moment one exists — an instrument
        # that looks frozen rather than broken. Sits AFTER the seed branch on
        # purpose: that branch owns the case where no mined manifest exists yet.
        path = self.path.split("?")[0]
        if path.startswith("/data/"):
            name = path[len("/data/"):]
            target = DATA / name
            if "/" in name or name.startswith(".") or not target.is_file():
                self.send_error(404)
                return
            blob = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type",
                             "text/javascript" if name.endswith(".js")
                             else "application/json" if name.endswith(".json")
                             else "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802 — stdlib name
        if self.path != "/api/allocate":
            self.send_error(404)
            return
        # a custom header forces a CORS preflight, so a random web page cannot
        # fire this cross-origin; same-origin is our own app
        if self.headers.get("X-Fix-Observatory") != "1":
            self.send_error(403, "missing X-Fix-Observatory header")
            return
        if not ALLOW_AGENTS:
            self._json(403, {
                "ok": False,
                "error": "agent allocation is off for this server — enable the "
                         "widget's 'allow agent allocation' setting (or launch "
                         "with FIX_OBSERVATORY_ALLOW_AGENTS=1) and reopen"})
            return
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            number = int(json.loads(raw or b"{}").get("number"))
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_error(400, "bad body")
            return
        err, note = allocate_agent(number)
        body = json.dumps({"ok": err is None, "error": err,
                           "note": note}).encode()
        self.send_response(200 if err is None else 409)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    def miner():
        while True:
            try:
                mine_once()
            except Exception as exc:  # keep serving even if a cycle dies
                log(f"mine cycle failed: {exc}")
            time.sleep(INTERVAL)

    threading.Thread(target=miner, daemon=True).start()
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    except OSError as exc:
        log(f"port {PORT} unavailable ({exc}) — assuming an observatory already serves")
        return
    log(f"serving http://127.0.0.1:{PORT}/app/swarm.html (repo={REPO}, "
        f"poll={INTERVAL}s, "
        f"{'exhaustive' if COMPLETE else 'newest %d pages, unauthenticated' % MAX_PAGES})")
    httpd.serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="mine one pass and exit")
    ap.add_argument("--serve", action="store_true", help="serve the app + mine on an interval")
    ap.add_argument("--seed", action="store_true",
                    help="maintainer verb: freeze the mined manifest into seed/")
    args = ap.parse_args()
    if args.seed:
        print(write_seed())
        return
    adopt_legacy_data()
    load_cache()
    if args.serve:
        serve()
    else:
        mine_once()


if __name__ == "__main__":
    main()
