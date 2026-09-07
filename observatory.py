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
import hashlib
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
    miner wrote sat directly in the state directory: one manifest, one cache,
    one set of agent prompts. Now that a slug owns each of those, the flat copy
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


def report_path(proj: "Project", number) -> Path:
    return proj.dir / f"agent-report-{number}.md"


def agent_prompt(proj: "Project", art, comments) -> str:
    REPO = proj.repo
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
        f"  {report_path(proj, n)}",
        "",
        "Say what you checked, what you could NOT check, and what you are",
        "only guessing. Unknown is not zero here either.",
        "",
    ] + _machine_paragraph(proj) + [
        "",
        "Do NOT post to GitHub or take any public action unless explicitly asked.",
        "",
    ]
    return "\n".join(lines)


# The reproduction surface, which stopped being one fixed thing the moment the
# observatory could be pointed at any repository on the machine. Three cases,
# and getting them wrong in either direction costs something real: telling an
# agent it is standing on a live install of the thing it is debugging, when it
# is not, invites destructive "reproduction" of a system nobody has; NOT
# telling it when it is true removes the one warning that keeps omarchy-update
# from being run to test a theory.
OMARCHY_MACHINE = [
    "This machine is a LIVE OMARCHY INSTALL — the same system the ticket is",
    "about. That makes it the honest reproduction surface and the hazard at",
    "once. Read anything; run nothing that installs, overwrites, or updates",
    "in order to test a theory. Prefer a copy under /tmp to touching",
    "~/.config or ~/.local/share/omarchy, and never run omarchy-update.",
]


def _machine_paragraph(proj: "Project") -> list:
    if proj.repo == DEFAULT_REPO and Path.home().joinpath(
            ".local/share/omarchy").exists():
        return OMARCHY_MACHINE
    if proj.path and Path(proj.path).is_dir():
        return [
            f"The repository is checked out on this machine at {proj.path} —",
            "read it, search it, run its tests. Treat the working tree as",
            "someone else's: do not commit, push, stash, switch branches, or",
            "run anything that rewrites it. If you need to build or mutate it,",
            "clone it to /tmp first and say in the report that you did.",
        ]
    return [
        "There is no local checkout of this repository on this machine, so the",
        "code is reachable only through the API and a clone you make yourself.",
        "Put any clone under /tmp. Say plainly in the report which claims you",
        "verified against real code and which came from reading the thread —",
        "they are different kinds of evidence and only one of them is strong.",
    ]


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


def allocate_agent(proj: "Project", number: int):
    """Returns (error, warning). Either may be None; an error means no spawn."""
    try:
        manifest = json.loads(proj.manifest_path.read_text())
    except Exception as exc:
        return f"manifest unreadable: {exc}", None
    art = next((a for a in manifest.get("artifacts", [])
                if a.get("number") == number), None)
    if art is None:
        return f"{proj.repo}#{number} is not in the manifest", None
    proj.dir.mkdir(parents=True, exist_ok=True)
    pf = proj.dir / f"agent-prompt-{number}.md"
    pf.write_text(agent_prompt(proj, art, manifest.get("comments") or []))
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
    # The agent starts where the code is when we know where that is. An agent
    # for a repository checked out on this machine that opens in $HOME has to
    # find its own way there, and the one thing it should not have to guess is
    # which of several similarly-named directories the ticket is about.
    cwd = proj.path if (proj.path and Path(proj.path).is_dir()) else AGENT_CWD
    try:
        subprocess.Popen(cmd, cwd=cwd, start_new_session=True,
                         env=clean_agent_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return f"spawn failed: {exc}", None
    log(f"allocated agent for {proj.repo}#{number} ({cmd[0]} in {cwd}"
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

    def do_GET(self):  # noqa: N802 — stdlib name
        path = self.path.split("?")[0]
        q = self._query()

        # What this server is willing to do, so the page never draws a button
        # the server would refuse. One static answer per process lifetime.
        if path == "/api/caps":
            self._json(200, {"allocate": ALLOW_AGENTS, "projects": True,
                             "induct": True})
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
        if path == "/data/manifest.js" or path == "/data/manifest.json":
            proj = project(q.get("project"))
            name = path[len("/data/"):]
            target = proj.manifest_js if name.endswith(".js") else proj.manifest_path
            # Until the first cycle finishes, hand the committed seed over
            # under the live manifest's own name — the page asks for one thing
            # and gets the best picture that exists. Only the repository the
            # seed is actually of: an inducted project served omarchy's seed
            # would be a confident, wrong instrument. Gzip goes over the wire
            # as gzip: 11MB of JSON is 1.2MB compressed, inflated for free.
            if (not target.exists() and name.endswith(".js")
                    and proj.slug == default_slug() and seed_meta()):
                blob = SEED_JS_GZ.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)
                return
            if not target.is_file():
                # Not an error, and not an empty repository either. A project
                # inducted a minute ago has no manifest yet; saying so lets the
                # page draw "mining" rather than a swarm of nothing.
                self._json(404, {"error": "no manifest yet",
                                 "slug": proj.slug, "mining": proj.mining})
                return
            blob = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript"
                             if name.endswith(".js") else "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
            return
        if path.startswith("/data/"):
            self.send_error(404)
            return

        # ---- static, and ONLY the app
        # The handler is rooted at the install, which holds the whole git
        # checkout: .git/config, the handoffs, the source of this file. None of
        # that has ever been something the page asks for, and a directory
        # served because one file in it was wanted is how the rest of it
        # becomes someone's finding later. Measured on this machine, where the
        # plugin directory is a symlink to a working tree, so the exposure
        # reached harvested agent sessions rather than just a public clone.
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/app/swarm.html")
            self.end_headers()
            return
        if not path.startswith("/app/") or ".." in path:
            self.send_error(404)
            return
        super().do_GET()

    # ---- writes ---------------------------------------------------------------
    # Every one of these carries the same custom-header requirement the
    # allocation endpoint has had from the start: a custom header forces a CORS
    # preflight, so a random page in another tab cannot fire them cross-origin,
    # while our own same-origin app sends it without ceremony.
    def do_POST(self):  # noqa: N802 — stdlib name
        path = self.path.split("?")[0]
        if self.headers.get("X-Fix-Observatory") != "1":
            self.send_error(403, "missing X-Fix-Observatory header")
            return
        body = self._body()

        if path == "/api/allocate":
            if not ALLOW_AGENTS:
                self._json(403, {
                    "ok": False,
                    "error": "agent allocation is off for this server — enable "
                             "the widget's 'allow agent allocation' setting (or "
                             "launch with FIX_OBSERVATORY_ALLOW_AGENTS=1) and "
                             "reopen"})
                return
            try:
                number = int(body.get("number"))
            except (ValueError, TypeError):
                self._json(400, {"ok": False, "error": "bad body"})
                return
            err, note = allocate_agent(project(body.get("project")), number)
            self._json(200 if err is None else 409,
                       {"ok": err is None, "error": err, "note": note})
            return

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
