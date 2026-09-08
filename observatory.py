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
  for a manifest that does not — it renders as a hollow mote and counts as
  never scored, because a hole is not a clean score.
- All requests are conditional (ETags); 304s are free against the rate limit.

Stdlib only. With GITHUB_TOKEN / GH_TOKEN every stream is walked to its end;
without one the 60/hour ceiling allows only the newest few pages, and the
manifest says so rather than letting the shortfall read as an empty repo.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import hashlib
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import induction

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


STATE = _state_dir()
# One observatory, many repositories. Each project's mined history lives under
# its own slug beneath projects/, and the registry beside them is the list of
# what this instrument watches — the thing the bar glyph's search widget reads
# and the induction panel writes.
PROJECTS_DIR = STATE / "projects"
REGISTRY_PATH = STATE / "projects.json"
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
DEFAULT_REPO = os.environ.get("FIX_OBSERVATORY_REPO", "omacom/omarchy")
PORT = int(os.environ.get("FIX_OBSERVATORY_PORT", "4517"))
# The fallback token. A project cloned locally resolves its OWN token from its
# own directory (this machine routes gh through a per-repository account
# wrapper, so the same command in two directories honestly returns two
# different tokens); this one is what a project with no local clone gets, and
# what everything falls back to when gh cannot answer.
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
# Authenticated we get 5,000 requests an hour, which is enough to walk every
# stream to its end (~600 pages for omarchy) — so we do, and order ascending
# because then the cursors and the ETags of everything but the last page are
# stable and later cycles cost nothing. Unauthenticated, 60/hour makes that
# impossible; we take the NEWEST pages instead and record the truncation.
# Per project, because the token is per project: a repository with a local
# clone resolves its own, and two projects on one machine can legitimately be
# reachable by different accounts.
MAX_PAGES_ENV = os.environ.get("FIX_OBSERVATORY_MAX_PAGES")


def page_cap(token) -> int:
    if MAX_PAGES_ENV:
        return int(MAX_PAGES_ENV)
    return 1500 if token else 3


def order_for(token) -> str:
    return "asc" if token else "desc"
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
# The rate budget is genuinely global — it belongs to a token, not to a
# project — so it stays a module global while everything else moved onto the
# project. Keyed by token fingerprint, because two projects reachable by two
# different accounts have two independent budgets, and sharing one number
# between them would make each one lie about the other's headroom.
RATE: dict = {}
RATE_BY_KEY: dict = {}


# Cached bodies are DISTILLED rows, not GitHub's. Raw, the ~600 pages of a whole
# repo are ~150MB rewritten every cycle; the fields we keep are ~14MB. Bump this
# whenever a row shape changes, or a 304 will serve a body of the old shape.
CACHE_VERSION = 2


# ---- a project ---------------------------------------------------------------
class Project:
    """One repository this observatory watches, and everything it owns.

    Everything that used to be a module global — the repo slug, the state
    directory, the HTTP cache, the token, the page cap — hangs off one of
    these, because the instrument now watches more than one thing at a time
    and each of those answers differently per repository. The token especially:
    this machine routes `gh` through a wrapper that picks the account from the
    repository being acted on, so a project with a local clone resolves its own
    and two projects can honestly be reachable by two different accounts.
    """

    def __init__(self, slug: str, repo: str, path: str | None = None,
                 label: str | None = None, builtin: bool = False,
                 added_at: str | None = None):
        self.slug = slug
        self.repo = repo               # owner/name
        self.path = path               # the local clone, if there is one
        self.label = label or repo
        self.builtin = builtin
        self.added_at = added_at
        self.cache: dict = {}
        self.cache_loaded = False
        self._token: str | None = None
        self._token_source: str = "not looked for"
        self._token_at: float = 0.0
        self.last_error: str | None = None
        self.mining = False

    # -- where its things live
    @property
    def dir(self) -> Path:
        return PROJECTS_DIR / self.slug

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def manifest_js(self) -> Path:
        return self.dir / "manifest.js"

    @property
    def cache_path(self) -> Path:
        return self.dir / "http-cache.json"

    # -- the token, resolved where the repository actually is
    def token(self) -> str:
        """This project's token, re-resolved at most once an hour.

        A local clone is asked first and the environment second, which is the
        opposite of the obvious order and is the whole point: the launcher
        exports one token borrowed from `gh` in the plugin's own directory, and
        preferring it would hand every project the account that happened to own
        the directory the server started in.
        """
        now = time.time()
        if self._token is not None and now - self._token_at < 3600:
            return self._token
        tok, source = None, "not looked for"
        if self.path and Path(self.path).is_dir():
            tok, source = induction.gh_token_for(self.path)
        if not tok and TOKEN:
            tok, source = TOKEN, "environment (GITHUB_TOKEN/GH_TOKEN)"
        self._token, self._token_source = tok or "", source
        self._token_at = now
        return self._token

    @property
    def token_source(self) -> str:
        return self._token_source

    # -- the cache
    def load_cache(self) -> None:
        if self.cache_loaded:
            return
        self.cache_loaded = True
        try:
            blob = json.loads(self.cache_path.read_text())
            self.cache = blob["entries"] if blob.get("v") == CACHE_VERSION else {}
        except Exception:
            self.cache = {}

    def save_cache(self) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"v": CACHE_VERSION, "entries": self.cache}))
        except Exception as exc:
            log(f"[{self.slug}] cache save failed: {exc}")

    # -- what the page and the bar widget need to know about it
    def summary(self) -> dict:
        """Never invents a number it did not read.

        A project whose manifest has not landed yet reports null artifacts, not
        zero: "we have not mined this" and "this repository is empty" are
        different facts, and the search widget draws them differently.
        """
        out = {
            "slug": self.slug, "repo": self.repo, "label": self.label,
            "path": self.path, "builtin": self.builtin,
            "added_at": self.added_at, "mining": self.mining,
            "error": self.last_error,
            "artifacts": None, "comments": None, "events": None,
            "fetched_at": None, "complete": None, "authenticated": None,
            "seeded": False,
        }
        try:
            m = json.loads(self.manifest_path.read_text())
        except Exception:
            sm = seed_meta() if self.slug == default_slug() else None
            if sm:
                out.update(artifacts=sm.get("artifacts"),
                           comments=sm.get("comments"),
                           events=sm.get("events"),
                           fetched_at=sm.get("fetched_at"),
                           complete=sm.get("complete"), seeded=True)
            return out
        cov = m.get("coverage") or {}
        out.update(artifacts=len(m.get("artifacts") or []),
                   comments=len(m.get("comments") or []),
                   events=len(m.get("events") or []),
                   fetched_at=m.get("fetched_at"),
                   complete=cov.get("complete"),
                   authenticated=cov.get("authenticated"))
        return out


# ---- the registry ------------------------------------------------------------
# Everything the observatory watches, plus the roots it looks in for more. Held
# in memory behind one lock and written through on every change: two browser
# tabs and a bar widget all poke at this, and a half-written registry is a
# search widget that shows nothing with no error to explain it.
REGISTRY_LOCK = threading.RLock()
REGISTRY: dict = {"version": 1, "roots": [], "active": None, "projects": {}}
PROJECTS: dict[str, Project] = {}
# Slugs waiting for their first mine, drained ahead of the schedule so an
# induction produces a swarm now rather than at the top of the next cycle.
MINE_QUEUE: list[str] = []


def default_slug() -> str:
    owner, _, name = DEFAULT_REPO.partition("/")
    return induction.slug_for(owner, name or DEFAULT_REPO)


def load_registry() -> None:
    global REGISTRY
    with REGISTRY_LOCK:
        try:
            blob = json.loads(REGISTRY_PATH.read_text())
        except Exception:
            blob = {}
        REGISTRY = {
            "version": 1,
            "roots": blob.get("roots") or induction.default_roots(),
            "active": blob.get("active"),
            "projects": blob.get("projects") or {},
        }
        # The repository this program was built to watch is always present and
        # cannot be forgotten. It is what the committed seed is a picture of,
        # and an observatory whose list can be emptied to nothing is an
        # observatory that opens on an empty screen with no way back.
        ds = default_slug()
        REGISTRY["projects"].setdefault(ds, {
            "repo": DEFAULT_REPO, "path": None, "label": DEFAULT_REPO,
            "builtin": True, "added_at": None,
        })
        REGISTRY["projects"][ds]["builtin"] = True
        if REGISTRY["active"] not in REGISTRY["projects"]:
            REGISTRY["active"] = ds
        PROJECTS.clear()
        for slug, rec in REGISTRY["projects"].items():
            PROJECTS[slug] = Project(
                slug, rec.get("repo") or "", rec.get("path"),
                rec.get("label"), bool(rec.get("builtin")), rec.get("added_at"))


def save_registry() -> None:
    with REGISTRY_LOCK:
        try:
            STATE.mkdir(parents=True, exist_ok=True)
            tmp = REGISTRY_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(REGISTRY, indent=1) + "\n")
            tmp.replace(REGISTRY_PATH)
        except Exception as exc:
            log(f"registry save failed: {exc}")


def project(slug: str | None) -> Project:
    """The named project, or the active one. Never None.

    An unknown slug resolves to the active project rather than raising: it
    arrives from a URL a person can edit and a bar widget that may be a version
    behind, and answering with the instrument's current subject beats a stack
    trace in a script tag.
    """
    with REGISTRY_LOCK:
        if slug and slug in PROJECTS:
            return PROJECTS[slug]
        active = REGISTRY.get("active") or default_slug()
        if active not in PROJECTS:
            load_registry()
            active = REGISTRY.get("active") or default_slug()
        return PROJECTS[active]


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
    # An explicit FIX_OBSERVATORY_STATE means "use this history", not "seed a
    # new one from the tree". Without this an override pointed at an empty
    # directory — the way a cold-start test is made honest — still gets the
    # working tree's manifest imported into it, and the test passes for exactly
    # the reason it was written to rule out.
    if os.environ.get("FIX_OBSERVATORY_STATE"):
        return
    # Guarded on the manifest, not on the directory: the launcher creates the
    # state directory before this ever runs, so "does it exist" is always true
    # and would skip every migration there is.
    dest = PROJECTS.get(default_slug())
    if dest is None:
        return
    if dest.manifest_path.exists() or not LEGACY_DATA.is_dir():
        return
    if not (LEGACY_DATA / "manifest.json").is_file():
        return
    carried = 0
    try:
        dest.dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(LEGACY_DATA.iterdir()):
            if not src.is_file() or src.suffix == ".log":
                continue        # logs describe a past run, not a history
            if not (dest.dir / src.name).exists():
                shutil.copy2(src, dest.dir / src.name)
                carried += 1
    except Exception as exc:
        log(f"could not carry the mined history across to {dest.dir}: {exc}")
        return
    if carried:
        log(f"carried {carried} file(s) of mined history from {LEGACY_DATA} "
            f"to {dest.dir} — the old copy is left where it is")


def adopt_flat_state() -> None:
    """Carry a pre-0.3 single-project state directory into projects/<slug>/.

    Until the observatory could watch more than one repository, everything the
    miner wrote sat directly in the state directory: one manifest and one
    cache. Now that a slug owns each of those, the flat copy
    has to move under the slug the built-in repository resolves to, or the
    first start after an upgrade shows an empty instrument and quietly begins
    a thirteen-minute re-mine of history that is already on the disk.

    Copies rather than moves, and only into a project directory that does not
    yet exist. Another observatory process may still be reading the flat files
    (this machine routinely has several), and the cost of leaving them is disk
    the user can delete, while the cost of moving them out from under a running
    server is an instrument that goes blank mid-session.
    """
    dest = PROJECTS.get(default_slug())
    if dest is None or dest.manifest_path.exists():
        return
    if not (STATE / "manifest.json").is_file():
        return
    carried = 0
    try:
        dest.dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(STATE.iterdir()):
            if not src.is_file():
                continue
            if src.name == "projects.json" or src.suffix == ".log":
                continue
            if not (dest.dir / src.name).exists():
                shutil.copy2(src, dest.dir / src.name)
                carried += 1
    except Exception as exc:
        log(f"could not carry the flat state into {dest.dir}: {exc}")
        return
    if carried:
        log(f"carried {carried} file(s) from the single-project layout into "
            f"{dest.dir} — the flat copy is left where it is, and can be "
            f"deleted once this release has settled")


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
    if not SEED_JS_GZ.exists() or meta.get("repo") != DEFAULT_REPO:
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
    manifest = json.loads(PROJECTS[default_slug()].manifest_path.read_text())
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


def budget_key(token) -> str:
    """Which budget a token spends from.

    A fingerprint rather than the token, so a rate table that ends up in a log
    line or a debugger never carries a credential. The empty string is the
    unauthenticated budget, which is per-IP and therefore genuinely shared.
    """
    if not token:
        return "anonymous"
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def _note_rate(headers, key: str = "anonymous") -> None:
    rem, lim, res = (headers.get("X-RateLimit-Remaining"),
                     headers.get("X-RateLimit-Limit"),
                     headers.get("X-RateLimit-Reset"))
    if rem is not None:
        entry = {"remaining": int(rem), "limit": int(lim or 0),
                 "reset": int(res or 0)}
        RATE_BY_KEY[key] = entry
        # RATE stays as the most recently observed budget so the log line and
        # the manifest's coverage block keep reading as they did. Which budget
        # it is is recorded alongside, because on a machine with two accounts
        # "1,482 remaining" without saying whose is not a fact anyone can use.
        RATE.clear()
        RATE.update(entry)
        RATE["key"] = key


LINK_NEXT_RE = re.compile(r'<https://api\.github\.com([^>]+)>;\s*rel="next"')


def api_page(path: str, row_fn=None, proj: "Project | None" = None):
    """Conditional GET; returns (body, next_path or None). 304 serves the cache.

    The next page comes from the server's own Link header, not from an
    incremented page number: these endpoints have moved to opaque cursors, and
    following the link is the only way to reach the end of one.

    `row_fn` distils each row before it is cached — a row that returns None is
    dropped. Nothing downstream ever sees GitHub's full objects, which is what
    keeps a whole-repo cache in megabytes rather than hundreds of them.

    The cache and the token both come off the project, so two repositories
    reachable by two different accounts never share either.
    """
    proj = proj or project(None)
    token = proj.token()
    headers = {
        "User-Agent": "fix-everything-observatory/2.0 (+https://wecanfixeverything.com)",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    key = budget_key(token)
    ent = proj.cache.get(path)
    if ent and ent.get("etag"):
        headers["If-None-Match"] = ent["etag"]
    try:
        with urlopen(Request("https://api.github.com" + path, headers=headers),
                     timeout=30) as res:
            _note_rate(res.headers, key)
            raw = json.load(res)
            body = raw if row_fn is None else [
                x for x in (row_fn(r) for r in raw) if x is not None]
            m = LINK_NEXT_RE.search(res.headers.get("Link") or "")
            nxt = m.group(1) if m else None
            proj.cache[path] = {"etag": res.headers.get("ETag"), "body": body,
                                "next": nxt}
            return body, nxt
    except HTTPError as e:
        if e.code == 304 and ent:
            _note_rate(e.headers, key)
            m = LINK_NEXT_RE.search(e.headers.get("Link") or "")
            return ent["body"], (m.group(1) if m else ent.get("next"))
        raise


def api(path: str, proj: "Project | None" = None):
    """One object, no pagination."""
    return api_page(path, None, proj)[0]


def budget_low(key: str = "anonymous") -> bool:
    rate = RATE_BY_KEY.get(key)
    if not rate:
        return False
    if rate.get("remaining", 999) >= MIN_BUDGET:
        return False
    return rate.get("reset", 0) > time.time()


# ---- mining ------------------------------------------------------------------
def fetch_all(path: str, row_fn=None, cap: int = 1500, proj: "Project | None" = None):
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


def mine_once(proj: "Project | None" = None) -> None:
    proj = proj or project(None)
    proj.load_cache()
    token = proj.token()
    key = budget_key(token)
    cap = page_cap(token)
    order = order_for(token)
    REPO = proj.repo

    if budget_low(key):
        rate = RATE_BY_KEY.get(key, {})
        reset = datetime.fromtimestamp(rate.get("reset", 0), timezone.utc)
        log(f"[{proj.slug}] rate budget low ({rate.get('remaining')}) — cycle "
            f"skipped, resets {reset.isoformat(timespec='minutes')}")
        return

    arts, issues_complete, err, issue_pages = fetch_all(
        f"/repos/{REPO}/issues?state=all&sort=created&direction={order}"
        "&per_page=100", issue_row, cap, proj)
    comments, comments_complete, c_err, comment_pages = fetch_all(
        f"/repos/{REPO}/issues/comments?sort=created&direction={order}"
        "&per_page=100", comment_row, cap, proj)
    events, events_complete, e_err, event_pages = fetch_all(
        f"/repos/{REPO}/issues/events?per_page=100", event_row, cap, proj)
    err = err or c_err or e_err
    arts = [a for a in arts if a["number"] is not None]
    events_capped = event_pages >= EVENT_PAGE_CAP
    if events_capped:
        events_complete = False

    meta = None
    try:
        meta = api(f"/repos/{REPO}", proj)
    except (HTTPError, URLError, OSError) as exc:
        err = err or f"repo meta: {exc}"
    proj.last_error = err

    comments.sort(key=lambda c: c["created_at"] or "")
    snippets_from = comments[0]["created_at"] if comments else None
    if len(comments) > SNIPPET_KEEP:
        snippets_from = comments[-SNIPPET_KEEP]["created_at"]
        for c in comments[:-SNIPPET_KEEP]:
            c["snippet"] = None      # never fetched-and-empty; not carried
            c["url"] = None

    events.sort(key=lambda e: e["created_at"] or "")

    manifest_path = proj.manifest_path
    # The seed is a picture of ONE repository — the one this program was built
    # to watch. An inducted project has no seed of its own, so the two guards
    # below that fall back to it must not fire for anybody else, or a newly
    # inducted repository would be protected from its own first mine by a
    # manifest of somebody else's history.
    seed = seed_meta() if proj.slug == default_slug() else None
    # A cycle that fetched NOTHING is a failed cycle, not a small slice, and the
    # log has to say which. Before the seed existed this branch could only fire
    # against a manifest on disk, so a failed first cycle fell through to the
    # slice guard below and was reported as "a slice (0 artifacts)" — which reads
    # as a measurement rather than as an error with a cause. Same rule as the
    # manifest itself: 300 of 8,892 and nothing at all are different findings.
    if not arts and err and (manifest_path.exists() or seed):
        held = "previous manifest" if manifest_path.exists() else "committed seed"
        log(f"[{proj.slug}] mine failed ({err}) — keeping the {held}")
        proj.save_cache()
        return
    if not arts and err:
        log(f"[{proj.slug}] mine failed ({err}) — nothing on disk to keep, and "
            f"nothing written. This project has no picture yet, which is not "
            f"the same as an empty repository.")
        proj.save_cache()
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
            log(f"[{proj.slug}] this cycle is a slice ({len(arts)} artifacts) "
                f"and the manifest on disk was walked to the end — keeping the "
                f"complete one. A token is what raises the horizon.")
            proj.save_cache()
            return

    # The same rule, against the committed seed. Without this, an untokened first
    # run writes 300 artifacts over a served seed of 8,887 and the swarm SHRINKS
    # on its first successful mine — fresher by two days, blind by fifteen months.
    # Stale-and-whole beats fresh-and-truncated for an instrument about long arcs,
    # and the page dates the seed so nobody mistakes it for now.
    if not issues_complete and not manifest_path.exists():
        if seed and seed.get("complete"):
            log(f"[{proj.slug}] this cycle is a slice ({len(arts)} artifacts) and "
                f"the committed seed was walked to the end — serving the seed, "
                f"writing nothing. A token is what raises the horizon.")
            proj.save_cache()
            return

    opened = [a["opened_at"] for a in arts if a["opened_at"]]
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "schema": "fix-everything-manifest:v2",
        "repo": REPO,
        "fetched_at": now_iso,
        "error": err,
        "slug": proj.slug,
        "coverage": {
            "per_page": 100, "order": order,
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
            "authenticated": bool(token),
            "token_source": proj.token_source,
            "api": ({"remaining": rate.get("remaining"),
                     "limit": rate.get("limit"),
                     "reset_at": datetime.fromtimestamp(
                         rate["reset"], timezone.utc).isoformat(timespec="minutes")
                     if rate.get("reset") else None}
                    if (rate := RATE_BY_KEY.get(key)) else None),
        },
        "artifacts": arts,
        "comments": comments,
        "events": events,
    }

    proj.dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest, indent=1)
    manifest_path.write_text(body + "\n")
    proj.manifest_js.write_text("window.SWARM_DATA = " + body + ";\n")
    proj.save_cache()
    counts = {}
    for a in arts:
        counts[a["attribution"]] = counts.get(a["attribution"], 0) + 1
    log(f"[{proj.slug}] mined {len(arts)} artifacts {counts} "
        f"comments={len(comments)} events={len(events)} "
        f"pages={issue_pages}/{comment_pages}/{event_pages} "
        f"complete={issues_complete}/{comments_complete}/{events_complete} "
        f"api_remaining={(RATE_BY_KEY.get(key) or {}).get('remaining', '?')} "
        f"err={err}")


# ---- the machine's own theme ---------------------------------------------------
# Omarchy keeps the theme a machine is currently wearing at a fixed path, and
# every theme — the twenty stock ones and any hand-rolled one — carries the same
# colors.toml. This program is an Omarchy instrument sitting on an Omarchy
# desktop, so it wears what the desktop wears rather than a palette of its own.
#
# It is READ ONLY and it is one known file. Nothing here takes a path from a
# request, and no request can name a theme: there is exactly one current theme
# and this reads it or reports that it could not.
OMARCHY_THEME = (Path(os.environ.get("XDG_STATE_HOME")
                      or Path.home() / ".local/state")
                 / "omarchy/current/theme")

# The keys the page actually paints with. A theme that omits one is not a theme
# with a black one — the key is left OUT of the answer entirely and the page
# keeps its own built-in value for it. A palette half-applied over a default is
# how you get unreadable text nobody can explain.
THEME_KEYS = (
    "background", "dark_background", "darker_background", "lighter_background",
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "accent", "selection", "muted",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan",
    "bright_blue", "bright_magenta",
)
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
TOML_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\"']([^\"']*)[\"']")


def read_theme():
    """The current Omarchy theme's name, mode and colours, or a stated absence.

    `name: None` means no theme was found — not "the default theme", and not a
    palette of empty strings. The page tells those apart: it keeps its own
    colours and says nothing, rather than painting something invented.
    """
    root = OMARCHY_THEME
    out = {"name": None, "mode": None, "colors": {}}
    try:
        name = (root.parent / "theme.name").read_text(encoding="utf-8").strip()
        out["name"] = name or None
    except OSError:
        pass
    try:
        text = (root / "colors.toml").read_text(encoding="utf-8")
    except OSError:
        return out
    # A top-level key=value scan, stopping at the first [table]: the colours are
    # all top level, and a table's keys would collide with them by short name.
    colors, mode = {}, None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        m = TOML_LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "mode":
            mode = val if val in ("dark", "light") else None
        elif key in THEME_KEYS and HEX.match(val):
            colors[key] = val
    out["mode"] = mode
    out["colors"] = colors
    return out


# ---- server -------------------------------------------------------------------
# Which API routes read and which write. Only used to answer HEAD with an
# honest Allow header, but keeping the two lists named is what stops a route
# being added to one half and silently inheriting the other half's manners.
READ_ROUTES = frozenset({"/api/caps", "/api/projects", "/api/scan",
                         "/api/preflight", "/api/complete", "/api/theme"})
WRITE_ROUTES = frozenset({"/api/induct", "/api/forget",
                          "/api/active", "/api/roots", "/api/mine"})


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: N802 — stdlib name
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        # Enforced by the browser on no-cors loads — the shape a
        # cross-origin <script src> or <img> uses. Without it the mined
        # manifest is readable by any page the operator has open.
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _json(self, code: int, payload: dict, body: bool = True) -> None:
        blob = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        if body:                     # a HEAD gets the headers and nothing else
            self.wfile.write(blob)

    def _query(self) -> dict:
        from urllib.parse import parse_qs, urlparse
        return {k: v[0] for k, v in
                parse_qs(urlparse(self.path).query).items()}

    def _body(self) -> dict:
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            out = json.loads(raw or b"{}")
            return out if isinstance(out, dict) else {}
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}

    # ---- the two gates every request passes ------------------------------
    # Binding to 127.0.0.1 decides which INTERFACE accepts a connection. It
    # does not decide which NAME may address it, and a browser routes by
    # name: a page on evil.tld whose DNS answers 127.0.0.1 on its second
    # lookup is same-origin with us by the browser's rules, and every
    # custom-header check downstream is then satisfied by its own fetch.
    # So the Host header is checked before anything is routed.
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip()
        allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}",
                   f"[::1]:{PORT}", "127.0.0.1", "localhost"}
        if host in allowed:
            return True
        self.send_error(403, "unexpected Host header")
        return False

    # A GET is not automatically safe. These three read the filesystem,
    # spend the operator's GitHub rate budget, or start `gh` — side effects
    # a bare <img> or a no-cors fetch from any open tab could otherwise
    # trigger, because neither can set a custom header and neither has to.
    # /api/caps and /api/projects stay open: the bar widget reads them and
    # they do nothing but answer.
    GUARDED_GETS = frozenset({"/api/preflight", "/api/scan", "/api/complete"})

    def do_GET(self):  # noqa: N802 — stdlib name
        if not self._host_ok():
            return
        path = self.path.split("?")[0]
        # Belt to CORP's braces: a browser that loads this from another
        # site labels the request cross-site, and nothing we serve is
        # meant to be read by one. Absent header = a non-browser client
        # (curl, the bar widget), which is allowed through.
        if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
            self.send_error(403, "cross-site request")
            return
        q = self._query()
        if path in self.GUARDED_GETS and \
                self.headers.get("X-Fix-Observatory") != "1":
            self.send_error(403, "missing X-Fix-Observatory header")
            return

        # What this server is willing to do. No verb in THIS module starts a
        # process — the allocation endpoint that did was removed in 0.2.0 —
        # but do not read that as "spawns nothing": /api/preflight reaches
        # induction, which runs `gh` with fixed argv. What is true, and what
        # bin/verify actually asserts, is narrower and worth stating plainly:
        # no mined GitHub text reaches any argv, ever.
        # One static answer per process lifetime.
        if path == "/api/caps":
            self._json(200, {"projects": True, "induct": True})
            return

        # ---- what the desktop is wearing. Re-read per request rather than
        # cached: a theme switch is a file change with no event to listen for,
        # and the page asks for this on the same slow timer it refreshes
        # everything else on.
        if path == "/api/theme":
            self._json(200, read_theme())
            return

        # ---- the observatory directory: what is watched, and what could be
        if path == "/api/projects":
            with REGISTRY_LOCK:
                self._json(200, {
                    "active": REGISTRY.get("active"),
                    "roots": list(REGISTRY.get("roots") or []),
                    "projects": [PROJECTS[s].summary()
                                 for s in sorted(PROJECTS)],
                })
            return

        if path == "/api/scan":
            self._json(200, scan(refresh=q.get("refresh") == "1"))
            return

        if path == "/api/preflight":
            target = q.get("path")
            if not target:
                self._json(400, {"error": "path is required"})
                return
            with REGISTRY_LOCK:
                known = set(PROJECTS)
            self._json(200, induction.preflight(
                target, known_slugs=known, state_dir=STATE,
                deep=q.get("deep", "1") == "1"))
            return

        if path == "/api/complete":
            self._json(200, induction.complete_dir(q.get("path", "")))
            return

        # ---- the manifest, per project
        # `?project=` names which; absent means the active one. The page has
        # one data path and always has — the slug rides as a parameter rather
        # than as a second URL shape, so a page from an older install still
        # asks a question this server can answer.
        if path.startswith("/data/"):
            self._serve_manifest(path, q, body=True)
            return

        # Anything left is a file request, and send_head below decides whether
        # it may be answered — for every verb, not just this one.
        super().do_GET()

    def do_HEAD(self):  # noqa: N802 — stdlib name
        """The same answers as GET, minus the bodies.

        Written out rather than inherited because inheriting it is precisely
        what went wrong: the base class's do_HEAD knew nothing about this
        server's routes, so every one of them answered from the filesystem
        instead. The API routes are GET-only and say so with a 405 — a verb
        this server does not serve is a different fact from a path it does not
        have, and answering 404 to both is how "GET is closed" got read as
        "closed", which it was not.
        """
        path = self.path.split("?")[0]
        if path.startswith("/data/"):
            self._serve_manifest(path, self._query(), body=False)
            return
        if path in READ_ROUTES or path in WRITE_ROUTES:
            self.send_response(405)
            self.send_header("Allow", "GET" if path in READ_ROUTES else "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path.startswith("/api/"):
            # A route that is in neither set does not exist, and 405 would
            # claim it does. Same rule as everywhere else here: do not answer
            # with a fact nobody measured.
            self.send_error(404)
            return
        super().do_HEAD()

    # ---- the manifest, per project ------------------------------------------
    # `?project=` names which; absent means the active one. The page has one
    # data path and always has — the slug rides as a parameter rather than as a
    # second URL shape, so a page from an older install still asks a question
    # this server can answer.
    def _serve_manifest(self, path: str, q: dict, body: bool) -> None:
        name = path[len("/data/"):]
        if name not in ("manifest.js", "manifest.json"):
            self.send_error(404)
            return
        proj = project(q.get("project"))
        target = proj.manifest_js if name.endswith(".js") else proj.manifest_path
        # Until the first cycle finishes, hand the committed seed over under
        # the live manifest's own name — the page asks for one thing and gets
        # the best picture that exists. Only the repository the seed is
        # actually of: an inducted project served omarchy's seed would be a
        # confident, wrong instrument. Gzip goes over the wire as gzip: 11MB of
        # JSON is 1.2MB compressed, and the browser inflates it for free.
        if (not target.exists() and name.endswith(".js")
                and proj.slug == default_slug() and seed_meta()):
            blob = SEED_JS_GZ.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            if body:
                self.wfile.write(blob)
            return
        if not target.is_file():
            # Not an error, and not an empty repository either. A project
            # inducted a minute ago has no manifest yet; saying so lets the
            # page draw "mining" rather than a swarm of nothing.
            self._json(404, {"error": "no manifest yet", "slug": proj.slug,
                             "mining": proj.mining}, body=body)
            return
        blob = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript"
                         if name.endswith(".js") else "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        if body:
            self.wfile.write(blob)

    # ---- the one gate on the filesystem ---------------------------------------
    # Every filesystem answer this server gives passes through send_head:
    # SimpleHTTPRequestHandler routes both GET and HEAD through it, and a verb
    # added later would too. Guarding do_GET was the first shape of this fix and
    # it was wrong in a way that is worth writing down, because it is the same
    # shape as every other bug in this file's history — a check that passes for
    # the wrong reason. do_HEAD is its own method on the base class, so it never
    # ran the do_GET allowlist at all: HEAD / answered 200 with a
    # Content-Length of 1092 for the directory listing, and HEAD on
    # /.git/config, /handoffs/, /observatory.py and /induction.py answered 200
    # with each file's exact size. No body, so nothing was readable — but
    # existence and size are still more than a port serving one page has any
    # business saying, and "GET returns 404" had been read as "unreachable".
    #
    # The gate therefore sits at the shared resolution rather than at each
    # verb. The rule to keep: guard where the path becomes a file, never where
    # a method becomes a response.
    def send_head(self):  # noqa: N802 — stdlib name
        path = self.path.split("?")[0]
        # The install holds the whole git checkout — .git/config, the handoffs,
        # the source of this file. None of it has ever been something the page
        # asks for, and on this machine the plugin directory is a symlink to a
        # working tree, so serving it reached harvested agent sessions rather
        # than just a public clone.
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/app/swarm.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if not path.startswith("/app/") or ".." in path:
            self.send_error(404)
            return None
        return super().send_head()

    # ---- writes ---------------------------------------------------------------
    # Every one of these carries a custom-header requirement, and so do the
    # three GETs with side effects: a custom header forces a CORS preflight,
    # so a random page in another tab cannot fire them cross-origin, while
    # our own same-origin app sends it without ceremony. The header is the
    # second leg; _host_ok is the first, and neither is sufficient alone.
    def do_POST(self):  # noqa: N802 — stdlib name
        if not self._host_ok():
            return
        path = self.path.split("?")[0]
        if self.headers.get("X-Fix-Observatory") != "1":
            self.send_error(403, "missing X-Fix-Observatory header")
            return
        body = self._body()

        if path == "/api/induct":
            self._json(*induct(body.get("path") or ""))
            return

        if path == "/api/forget":
            self._json(*forget(body.get("slug") or ""))
            return

        if path == "/api/active":
            slug = body.get("slug") or ""
            with REGISTRY_LOCK:
                if slug not in PROJECTS:
                    self._json(404, {"ok": False, "error": f"no project {slug}"})
                    return
                REGISTRY["active"] = slug
            save_registry()
            self._json(200, {"ok": True, "active": slug})
            return

        if path == "/api/roots":
            self._json(*edit_roots(body))
            return

        if path == "/api/mine":
            proj = project(body.get("slug"))
            enqueue_mine(proj.slug)
            self._json(200, {"ok": True, "slug": proj.slug})
            return

        self.send_error(404)


# ---- the verbs behind those routes -------------------------------------------
SCAN_LOCK = threading.Lock()
SCAN_CACHE: dict = {}
SCAN_TTL = 300


def scan(refresh: bool = False) -> dict:
    """Discovered repositories, memoised for five minutes.

    A walk of $HOME is cheap but not free, and the search widget re-asks on
    every keystroke-driven open. The cached answer carries its own
    `scanned_at`, so the page can say how old the list is instead of implying
    it is live.
    """
    with SCAN_LOCK:
        fresh = (SCAN_CACHE.get("scanned_at", 0) + SCAN_TTL) > time.time()
        if SCAN_CACHE and fresh and not refresh:
            return SCAN_CACHE
        with REGISTRY_LOCK:
            roots = list(REGISTRY.get("roots") or [])
            known = {p.repo for p in PROJECTS.values()}
        out = induction.scan_roots(roots)
        for r in out["repos"]:
            r["watched"] = bool(r.get("nwo")) and r["nwo"] in known
        SCAN_CACHE.clear()
        SCAN_CACHE.update(out)
        return SCAN_CACHE


def enqueue_mine(slug: str) -> None:
    with REGISTRY_LOCK:
        if slug not in MINE_QUEUE:
            MINE_QUEUE.append(slug)


def induct(path: str):
    """Add a repository to the observatory. Returns (status, payload).

    Runs the full battery first and refuses on a blocked verdict, with the
    report attached — the page shows exactly which check said no. A degraded
    verdict goes through: a repository that will mine slowly, or as a slice,
    is still a repository worth watching, and the manifest records the
    shortfall the way it always has.
    """
    if not path:
        return 400, {"ok": False, "error": "path is required"}
    with REGISTRY_LOCK:
        known = set(PROJECTS)
    report = induction.preflight(path, known_slugs=known, state_dir=STATE,
                                 deep=True)
    if report["blocked"] or not report.get("slug"):
        return 409, {"ok": False, "error": "preflight refused this directory",
                     "report": report}
    meta = report["meta"]
    slug = report["slug"]
    with REGISTRY_LOCK:
        REGISTRY["projects"][slug] = {
            "repo": meta["nwo"],
            "path": meta["path"],
            "label": meta["nwo"],
            "builtin": REGISTRY["projects"].get(slug, {}).get("builtin", False),
            "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        REGISTRY["active"] = slug
        PROJECTS[slug] = Project(slug, meta["nwo"], meta["path"], meta["nwo"],
                                 False, REGISTRY["projects"][slug]["added_at"])
    save_registry()
    enqueue_mine(slug)
    log(f"inducted {meta['nwo']} from {meta['path']} "
        f"(verdict {report['verdict']}) — mining now")
    return 200, {"ok": True, "slug": slug, "repo": meta["nwo"],
                 "report": report}


def forget(slug: str):
    """Drop a project from the registry. Its mined history stays on disk.

    Deleting the manifest would throw away the one expensive thing here — the
    walk that took thirteen minutes — to save a few megabytes, and re-inducting
    the same repository half an hour later would pay for it again. The
    directory is named in the answer so anyone who does want the space knows
    where to look.
    """
    with REGISTRY_LOCK:
        proj = PROJECTS.get(slug)
        if proj is None:
            return 404, {"ok": False, "error": f"no project {slug}"}
        if proj.builtin:
            return 409, {"ok": False, "error":
                         "this is the repository the observatory was built to "
                         "watch, and the committed seed is a picture of it — it "
                         "cannot be removed"}
        REGISTRY["projects"].pop(slug, None)
        PROJECTS.pop(slug, None)
        if REGISTRY.get("active") == slug:
            REGISTRY["active"] = default_slug()
    save_registry()
    return 200, {"ok": True, "slug": slug, "history_kept_at": str(proj.dir)}


def edit_roots(body: dict):
    """Add or remove a directory from the set the scan looks in."""
    add, remove = body.get("add"), body.get("remove")
    if not add and not remove:
        return 400, {"ok": False, "error": "add or remove is required"}
    with REGISTRY_LOCK:
        roots = list(REGISTRY.get("roots") or [])
        if add:
            resolved = str(Path(add).expanduser())
            if not Path(resolved).is_dir():
                return 409, {"ok": False,
                             "error": f"{resolved} is not a directory on this "
                                      "machine"}
            try:
                resolved = str(Path(resolved).resolve())
            except OSError:
                pass
            if resolved in roots:
                return 200, {"ok": True, "roots": roots,
                             "note": "already a search root"}
            roots.append(resolved)
        if remove:
            roots = [r for r in roots if r != remove]
        REGISTRY["roots"] = roots
    save_registry()
    with SCAN_LOCK:            # the old list no longer describes the new roots
        SCAN_CACHE.clear()
    return 200, {"ok": True, "roots": roots}


def due_projects() -> list:
    """Which projects this cycle mines, most deserving first.

    The queue comes first and whole: an induction that has just been confirmed
    should produce a swarm now, not at the top of the next quarter hour. After
    that the active project — the one somebody is looking at — then the
    stalest, and at most a couple more, so a machine watching a dozen
    repositories still refreshes the one on screen promptly.
    """
    with REGISTRY_LOCK:
        queued = [PROJECTS[s] for s in MINE_QUEUE if s in PROJECTS]
        MINE_QUEUE.clear()
        active = PROJECTS.get(REGISTRY.get("active") or "")
        rest = [p for p in PROJECTS.values()
                if p not in queued and p is not active]
    rest.sort(key=lambda p: p.manifest_path.stat().st_mtime
              if p.manifest_path.exists() else 0)
    out = queued + ([active] if active and active not in queued else []) + rest[:2]
    return out


def serve() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def miner():
        while True:
            for proj in due_projects():
                proj.mining = True
                try:
                    mine_once(proj)
                except Exception as exc:  # keep serving even if a cycle dies
                    proj.last_error = str(exc)
                    log(f"[{proj.slug}] mine cycle failed: {exc}")
                finally:
                    proj.mining = False
            # A queued induction should not wait out a quarter of an hour, so
            # the sleep is chopped into slices the queue can interrupt.
            for _ in range(max(1, INTERVAL // 5)):
                if MINE_QUEUE:
                    break
                time.sleep(5)

    threading.Thread(target=miner, daemon=True).start()
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    except OSError as exc:
        log(f"port {PORT} unavailable ({exc}) — assuming an observatory already serves")
        return
    # Name the state directory on every start. Since the history moved out of
    # the tree, an absent data/ no longer means an absent history: a "fresh
    # install" test on a box that has ever run this reads the real one and
    # passes for the wrong reason. Saying which history is being served is what
    # makes that visible without anyone having to remember it.
    with REGISTRY_LOCK:
        active = project(None)
        watched = len(PROJECTS)
    log(f"state {STATE}"
        f"{' (empty — the seed will be served until the first cycle lands)' if not active.manifest_path.exists() else ''}")
    log(f"serving http://127.0.0.1:{PORT}/app/swarm.html — watching {watched} "
        f"project(s), active {active.repo}, poll={INTERVAL}s")
    httpd.serve_forever()


def boot() -> None:
    """Everything a run needs on disk and in memory, in the one right order.

    The registry has to exist before the migrations, because both of them need
    to know which slug the built-in repository resolves to, and neither can ask
    a registry that has not been read.
    """
    load_registry()
    # Order is load-bearing, and the wrong way round is silent. Both migrations
    # are guarded on the destination manifest not existing, so whichever runs
    # first wins outright. The state directory is the LIVE history — the one a
    # running server has been writing to — while the in-tree data/ is a fossil
    # from before 0.2 that a working tree can carry for months. Letting the
    # fossil go first hands a stale manifest to the instrument and leaves the
    # real one sitting untouched one directory away, with nothing on screen to
    # say which of the two is being served.
    adopt_flat_state()
    adopt_legacy_data()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="mine one pass and exit")
    ap.add_argument("--serve", action="store_true", help="serve the app + mine on an interval")
    ap.add_argument("--seed", action="store_true",
                    help="maintainer verb: freeze the mined manifest into seed/")
    ap.add_argument("--project", metavar="SLUG",
                    help="which watched project to act on (default: the active one)")
    ap.add_argument("--induct", metavar="DIR",
                    help="add the repository in DIR to the observatory, after "
                         "running the full preflight against it")
    ap.add_argument("--preflight", metavar="DIR",
                    help="run the induction checks against DIR and print them, "
                         "changing nothing")
    ap.add_argument("--list", action="store_true",
                    help="list what this observatory watches")
    ap.add_argument("--scan", action="store_true",
                    help="list the repositories found under the search roots")
    args = ap.parse_args()
    boot()
    if args.seed:
        print(write_seed())
        return
    if args.preflight:
        report = induction.preflight(args.preflight, known_slugs=set(PROJECTS),
                                     state_dir=STATE, deep=True)
        print(f"{report.get('nwo') or args.preflight}: {report['verdict']}")
        for c in report["checks"]:
            mark = {"ok": "✓", "warn": "!", "fail": "✗", "unknown": "?"}[c["status"]]
            print(f"  {mark} {c['label']}: {c['detail']}")
            if c.get("fix"):
                print(f"      fix: {c['fix']}")
        return
    if args.induct:
        status, payload = induct(args.induct)
        if payload.get("ok"):
            print(f"inducted {payload['repo']} — mine it with: "
                  f"{Path(__file__).name} --once --project {payload['slug']}")
        else:
            print(payload.get("error"))
            for c in (payload.get("report") or {}).get("checks", []):
                if c["status"] == "fail":
                    print(f"  ✗ {c['label']}: {c['detail']}")
        raise SystemExit(0 if payload.get("ok") else 1)
    if args.list:
        for slug in sorted(PROJECTS):
            s = PROJECTS[slug].summary()
            n = "unmined" if s["artifacts"] is None else f"{s['artifacts']} artifacts"
            mark = "*" if slug == REGISTRY.get("active") else " "
            print(f"{mark} {slug:<38} {s['repo']:<40} {n}"
                  f"{' (seed)' if s['seeded'] else ''}")
        return
    if args.scan:
        out = scan(refresh=True)
        for r in out["repos"]:
            print(f"{'watched' if r.get('watched') else '       '} "
                  f"{(r.get('nwo') or '—'):<44} {r['path']}")
        print(f"\n{len(out['repos'])} repositories under {len(out['roots'])} "
              f"root(s), {out['dirs_visited']} directories visited"
              + (" — TRUNCATED, this is not the whole machine"
                 if out["truncated"] else ""))
        return
    if args.serve:
        serve()
    else:
        mine_once(project(args.project))


if __name__ == "__main__":
    main()
