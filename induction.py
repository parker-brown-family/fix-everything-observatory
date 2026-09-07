#!/usr/bin/env python3
"""Induction — finding repositories on this machine, and deciding whether one
can honestly be watched.

The observatory was born pointed at a single repository. This module is the
half that lets it be pointed at any of them: it walks a set of SEARCH ROOTS
looking for git work trees, reads each one's remote without spawning git, and
then — before anything is mined — runs a battery of checks against the
candidate and reports what it found.

Two rules shape everything here.

**A check that did not run is UNKNOWN, never a pass.** The battery is ordered,
and a check whose precondition failed is recorded as unknown with the name of
the check that stopped it. A directory with no remote does not quietly score
"no API access"; it scores "not reached — this is not a git work tree". The
difference decides what the person reading it should do next, and collapsing
the two would produce a confident, wrong verdict that looks exactly like a
measured one.

**The verdict never exceeds the evidence.** `ready` means every check that ran
passed. `degraded` means something will work worse than it should and says how
much worse. `blocked` means mining would produce an instrument that lies. A
battery full of unknowns is not `ready`; it is `unknown`, and the page draws it
hatched — the same mark the swarm uses for an artifact nobody scored.

Stdlib only, like the rest of the program.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---- search roots ------------------------------------------------------------
# Where a first run looks before anyone has told it anything. Every one of these
# is checked for existence — a default that names a directory this machine does
# not have is noise in the settings panel, not a default.
ROOT_CANDIDATES = ("Work", "src", "code", "dev", "projects", "Projects",
                   "repos", "git", "BROWN-FAMILY-SPORTS")

# Directories a scan never descends into. Two kinds: package caches, which
# contain thousands of vendored git checkouts nobody thinks of as their
# projects, and directories whose contents are enormous and never source.
SKIP_DIRS = frozenset({
    "node_modules", ".cache", ".venv", "venv", "__pycache__", ".mypy_cache",
    "target", "dist", "build", ".next", ".gradle", ".cargo", ".rustup",
    "vendor", "Library", "snap", ".local", ".steam", ".wine", "site-packages",
    "bower_components", ".terraform", ".tox", ".pnpm-store", "go",
})

# A scan of $HOME can otherwise walk for minutes. Both ceilings are recorded in
# the result when they fire, because "we stopped looking" and "there was
# nothing more to find" are different findings.
MAX_DEPTH = 5
MAX_DIRS = 120_000
MAX_HITS = 4000

SUBPROC_TIMEOUT = 6
API_TIMEOUT = 12
USER_AGENT = "fix-everything-observatory/0.2 (+https://wecanfixeverything.com)"

# git@host:owner/repo.git · ssh://git@host/owner/repo · https://host/owner/repo
REMOTE_RE = re.compile(
    r"^(?:(?P<scheme>https?|ssh|git)://)?"
    r"(?:(?P<user>[^@/]+)@)?"
    r"(?P<host>[^:/]+)"
    r"[:/]+"
    r"(?P<owner>[^/]+)/"
    r"(?P<repo>[^/]+?)(?:\.git)?/?$")

LINK_LAST_RE = re.compile(r'[?&]page=(\d+)>;\s*rel="last"')


def default_roots() -> list[str]:
    """The search roots a machine gets before anyone configures any.

    $HOME itself is included at the end deliberately: most people keep at least
    one repository loose in it, and the depth limit plus the skip list keep the
    walk cheap. It is last so the named directories win the dedupe and their
    shallower depth budget applies to their own subtrees.
    """
    home = Path.home()
    roots = [str(home / name) for name in ROOT_CANDIDATES
             if (home / name).is_dir()]
    roots.append(str(home))
    return roots


# ---- reading a work tree without spawning git --------------------------------
def git_dir_of(path: Path) -> Path | None:
    """The .git directory for a work tree, following a worktree's pointer file.

    A linked worktree has a FILE named .git holding `gitdir: /path/to/real`.
    Reading the remote out of one means following that, and a scan that only
    understands the directory form silently misses every worktree on a machine
    that uses them — which this one does.
    """
    dot = path / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            line = dot.read_text(errors="replace").strip()
        except OSError:
            return None
        if line.startswith("gitdir:"):
            target = Path(line.split(":", 1)[1].strip())
            if not target.is_absolute():
                target = (path / target).resolve()
            # A linked worktree's gitdir is <main>/.git/worktrees/<name>; the
            # config with the remotes lives two levels up.
            for cand in (target, target.parent.parent):
                if (cand / "config").is_file():
                    return cand
    return None


def read_remote(path: Path) -> tuple[str, str] | None:
    """(remote name, url) for a work tree, preferring origin. None if it has none.

    Parsed out of .git/config by hand rather than by shelling out to git: a
    scan touches hundreds of directories, and hundreds of subprocesses is the
    difference between a scan that feels instant and one that does not.
    """
    gd = git_dir_of(path)
    if gd is None:
        return None
    try:
        text = (gd / "config").read_text(errors="replace")
    except OSError:
        return None
    remotes: dict[str, str] = {}
    name = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'^\[remote\s+"([^"]+)"\]$', line)
        if m:
            name = m.group(1)
            continue
        if line.startswith("["):
            name = None
            continue
        if name and line.startswith("url"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                remotes[name] = parts[1].strip()
    if not remotes:
        return None
    if "origin" in remotes:
        return "origin", remotes["origin"]
    first = sorted(remotes)[0]
    return first, remotes[first]


def parse_remote(url: str) -> dict | None:
    """{host, owner, repo} from a remote URL, or None if it is not repo-shaped.

    The host is returned as written, SSH host aliases and all. Resolving an
    alias like `github-bfs` to github.com is ~/.ssh/config's business and is
    done by the caller, which has the alias table; guessing here would turn an
    unrecognised alias into a confident wrong host.
    """
    if not url:
        return None
    m = REMOTE_RE.match(url.strip())
    if not m:
        return None
    owner, repo = m.group("owner"), m.group("repo")
    if not owner or not repo or owner.startswith("~"):
        return None
    return {"host": m.group("host"), "owner": owner, "repo": repo}


def _ssh_alias_hosts() -> dict[str, str]:
    """Host alias → real hostname, from ~/.ssh/config.

    This machine clones through per-account aliases (`git@github-bfs:…`), so a
    remote's literal host is routinely not a hostname at all. Without this the
    forge check calls every aliased repository unsupported, which is every
    repository the user actually owns.
    """
    out: dict[str, str] = {}
    try:
        text = (Path.home() / ".ssh" / "config").read_text(errors="replace")
    except OSError:
        return out
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        key = key.strip().lower().rstrip("=")
        value = value.strip().lstrip("= ").strip()
        if key == "host":
            names = value.split()
        elif key == "hostname" and names:
            for n in names:
                out[n] = value
    return out


def resolve_host(host: str) -> str:
    """A remote's literal host, resolved through ~/.ssh/config aliases."""
    return _ssh_alias_hosts().get(host, host)


def slug_for(owner: str, repo: str) -> str:
    """The on-disk name for a project's state.

    Two underscores separate owner from repo because a single one is legal
    inside both, and a slug that cannot be split back is a slug that will one
    day be split back wrong.
    """
    safe = lambda s: re.sub(r"[^A-Za-z0-9._-]", "-", s)  # noqa: E731
    return f"{safe(owner)}__{safe(repo)}"


# ---- scanning ----------------------------------------------------------------
def scan_roots(roots, max_depth: int = MAX_DEPTH) -> dict:
    """Every git work tree under `roots`, with its remote already parsed.

    Returns {repos, dirs_visited, truncated, roots, took_ms}. `truncated` is
    the honest flag: a scan that hit either ceiling has not seen the whole
    machine, and the page says so rather than presenting a short list as a
    complete one.

    A repository is not descended into. Submodules and vendored checkouts under
    one are part of that project, not projects of their own, and including them
    turns a list a person can read into a list they cannot.
    """
    started = time.time()
    seen_paths: set[str] = set()
    repos: list[dict] = []
    visited = 0
    truncated = False

    for root in roots:
        base = Path(root).expanduser()
        try:
            base = base.resolve()
        except OSError:
            continue
        if not base.is_dir():
            continue
        stack = [(base, 0)]
        while stack:
            if visited >= MAX_DIRS or len(repos) >= MAX_HITS:
                truncated = True
                break
            here, depth = stack.pop()
            visited += 1
            key = str(here)
            if key in seen_paths:
                continue
            gd = git_dir_of(here)
            if gd is not None:
                seen_paths.add(key)
                repos.append(_repo_record(here))
                continue          # a repo owns everything beneath it
            if depth >= max_depth:
                continue
            try:
                with os.scandir(here) as it:
                    for entry in it:
                        try:
                            if not entry.is_dir(follow_symlinks=False):
                                continue
                        except OSError:
                            continue
                        name = entry.name
                        if name in SKIP_DIRS:
                            continue
                        # Hidden directories are skipped, with one exception
                        # nobody expects to need explaining: .git itself is
                        # never a candidate because its parent already was.
                        if name.startswith(".") and name != ".git":
                            continue
                        stack.append((Path(entry.path), depth + 1))
            except (OSError, PermissionError):
                continue
        if truncated:
            break

    repos.sort(key=lambda r: -(r.get("mtime") or 0))
    return {
        "repos": repos,
        "roots": [str(Path(r).expanduser()) for r in roots],
        "dirs_visited": visited,
        "truncated": truncated,
        "took_ms": int((time.time() - started) * 1000),
        "scanned_at": time.time(),
    }


def _repo_record(path: Path) -> dict:
    rec: dict = {
        "path": str(path),
        "name": path.name,
        "remote": None,
        "remote_name": None,
        "host": None,
        "owner": None,
        "repo": None,
        "slug": None,
        "mtime": None,
        "supported": False,
    }
    try:
        # The HEAD file's mtime is the last time this tree moved — a far better
        # sort key than the directory's own, which every editor touches.
        gd = git_dir_of(path)
        head = (gd / "HEAD") if gd else None
        rec["mtime"] = int(head.stat().st_mtime) if head and head.exists() else None
    except OSError:
        pass
    found = read_remote(path)
    if not found:
        return rec
    rec["remote_name"], rec["remote"] = found
    parsed = parse_remote(rec["remote"])
    if not parsed:
        return rec
    rec.update(parsed)
    rec["real_host"] = resolve_host(parsed["host"])
    rec["supported"] = rec["real_host"].lower() in ("github.com", "www.github.com")
    if rec["supported"]:
        rec["slug"] = slug_for(parsed["owner"], parsed["repo"])
        rec["nwo"] = f"{parsed['owner']}/{parsed['repo']}"
    return rec


def complete_dir(fragment: str, limit: int = 24) -> dict:
    """Directory completions for a half-typed path, for the add-a-root field.

    Deliberately its own endpoint rather than a client-side guess: only the
    machine knows what is on it, and a text box that cannot tell you whether
    the path you typed exists is a text box that will be typed into wrong.
    """
    raw = (fragment or "").strip()
    expanded = os.path.expanduser(raw) if raw else str(Path.home()) + os.sep
    if expanded.endswith(os.sep) or not raw:
        parent, stem = Path(expanded or "/"), ""
    else:
        parent, stem = Path(expanded).parent, Path(expanded).name
    out = []
    try:
        with os.scandir(parent) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if not entry.name.startswith(stem):
                    continue
                if entry.name.startswith(".") and not stem.startswith("."):
                    continue
                try:
                    if not entry.is_dir(follow_symlinks=True):
                        continue
                except OSError:
                    continue
                out.append(entry.path + os.sep)
                if len(out) >= limit:
                    break
    except (OSError, PermissionError) as exc:
        return {"parent": str(parent), "entries": [], "error": str(exc)}
    return {"parent": str(parent), "entries": out,
            "exists": Path(expanded).is_dir()}


# ---- the check battery -------------------------------------------------------
OK, WARN, FAIL, UNKNOWN = "ok", "warn", "fail", "unknown"


class Battery:
    """An ordered list of checks, where skipping is itself recorded.

    `stop` marks the battery blocked from a named check onward. Everything
    declared after that point is emitted as unknown, carrying the name of the
    check that stopped it — so the report distinguishes "we looked and it was
    fine" from "we never got far enough to look", which is the whole reason
    this class exists rather than a plain list.
    """

    def __init__(self):
        self.checks: list[dict] = []
        self.stopped_by: str | None = None

    def add(self, cid, label, status, detail, fix=None, data=None):
        if self.stopped_by and status != FAIL:
            status, detail = UNKNOWN, f"not reached — {self.stopped_by} failed first"
            fix = None
        self.checks.append({"id": cid, "label": label, "status": status,
                            "detail": detail, "fix": fix, "data": data})
        if status == FAIL and not self.stopped_by:
            self.stopped_by = label
        return status

    def skip(self, cid, label, why, informational: bool = False):
        """An unknown. `informational` marks the ones that are unknown BY
        DESIGN — facts nothing could establish before mining — as opposed to
        the ones that are unknown because a measurement failed.

        The distinction is the verdict's. A battery that came back clean except
        for a fact nobody could have known yet is ready; a battery that came
        back clean except for a check that tried and could not answer is not,
        and calling both of them the same thing would make the honest one
        useless by making every verdict `unknown`.
        """
        self.checks.append({"id": cid, "label": label, "status": UNKNOWN,
                            "detail": why, "fix": None, "data": None,
                            "informational": informational})

    def fill_unreached(self) -> None:
        """Emit every declared check that never ran, as an unknown that says so.

        Without this a blocked report is two lines long and the reader has no
        way to see that thirteen other things were never looked at — they read
        as absent rather than as unmeasured, and the battery quietly becomes a
        shorter, more confident document the worse the news is. The checks are
        re-sorted into their declared order so the report reads the same
        whichever way the run went.
        """
        have = {c["id"] for c in self.checks}
        why = (f"not reached — {self.stopped_by} failed first"
               if self.stopped_by else "not run")
        for cid, label in CHECK_ORDER:
            if cid not in have:
                self.checks.append({"id": cid, "label": label,
                                    "status": UNKNOWN, "detail": why,
                                    "fix": None, "data": None,
                                    "informational": False})
        order = {cid: i for i, (cid, _) in enumerate(CHECK_ORDER)}
        self.checks.sort(key=lambda c: order.get(c["id"], 99))

    @property
    def blocked(self) -> bool:
        return any(c["status"] == FAIL for c in self.checks)

    def verdict(self) -> str:
        if self.blocked:
            return "blocked"
        # A named defect outranks a hole: `degraded` says something IS wrong,
        # which is more actionable than saying something was not measured. The
        # tally travels beside the verdict so a report that is both never has
        # to choose between them.
        if any(c["status"] == WARN for c in self.checks):
            return "degraded"
        if any(c["status"] == UNKNOWN and not c.get("informational")
               for c in self.checks):
            return "unknown"
        return "ready"

    def tally(self) -> dict:
        out = {OK: 0, WARN: 0, FAIL: 0, UNKNOWN: 0}
        for c in self.checks:
            out[c["status"]] = out.get(c["status"], 0) + 1
        return out


def _get(path: str, token: str | None):
    """One uncached GET against the GitHub API -> (status, body, headers).

    Preflight wants a fresh answer and the status code, both of which the
    mining path's conditional-cached helper deliberately hides. Errors come
    back as a status of 0 with the exception's text, because "the network did
    not answer" is not a 404 and must not read as one.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request("https://api.github.com" + path, headers=headers),
                     timeout=API_TIMEOUT) as res:
            body = json.load(res) if res.headers.get_content_subtype() == "json" \
                else None
            return res.status, body, res.headers
    except HTTPError as e:
        try:
            body = json.load(e)
        except Exception:
            body = None
        return e.code, body, e.headers
    except (URLError, OSError, ValueError) as exc:
        return 0, {"message": str(exc)}, {}


def _count_via_link(path: str, token: str | None):
    """Total items in a paginated collection, at the cost of one request.

    Asking for a page of ONE and reading the `rel="last"` page number is the
    only way to learn a stream's length without walking it. It works for the
    comment and event streams and NOT for /issues, which has moved to opaque
    cursors and no longer offers a last link at all — measured, and the reason
    the artifact count comes from the search API instead.

    Returns (count, status). A count of None means the header was absent on a
    successful request: the stream's length is unknown, which the caller must
    keep as unknown rather than reading a one-page response as a total.
    """
    sep = "&" if "?" in path else "?"
    status, body, headers = _get(f"{path}{sep}per_page=1", token)
    if status != 200:
        return None, status
    link = (headers.get("Link") or "") if headers else ""
    m = LINK_LAST_RE.search(link)
    if m:
        return int(m.group(1)), status
    # No next link either means one page, which for per_page=1 means at most
    # one item. A next link with no last link means cursor pagination, whose
    # length nobody can know without walking it.
    if 'rel="next"' in link:
        return None, status
    return (len(body) if isinstance(body, list) else 0), status


def _search_count(nwo: str, token: str | None):
    """How many issues and pull requests a repository has, ever.

    The search index is the only endpoint that will say. /issues counts nothing
    and paginates by cursor; the repository object carries `open_issues_count`
    and nothing about what has been closed, which for a repair swarm is most of
    the history. `incomplete_results` is carried through rather than dropped —
    a partial index is a number with a caveat, not a number.
    """
    from urllib.parse import quote
    status, body, _ = _get(
        f"/search/issues?q={quote('repo:' + nwo)}&per_page=1", token)
    if status != 200 or not isinstance(body, dict):
        return None, False, status
    return body.get("total_count"), bool(body.get("incomplete_results")), status


def gh_token_for(cwd: str | None) -> tuple[str | None, str]:
    """A token for this repository, and where it came from.

    `gh auth token` is run WITH THE REPOSITORY AS ITS WORKING DIRECTORY on
    purpose. This machine routes gh through a wrapper that picks the account
    from the repo being acted on, so the same command in two directories
    honestly returns two different tokens — and running it from the server's
    own cwd would hand every project the account that happened to own the
    directory the server started in.
    """
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env, "environment (GITHUB_TOKEN/GH_TOKEN)"
    if not shutil.which("gh"):
        return None, "no gh on PATH"
    try:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True,
                           text=True, timeout=SUBPROC_TIMEOUT,
                           cwd=cwd if cwd and Path(cwd).is_dir() else None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gh auth token did not answer ({exc})"
    tok = (p.stdout or "").strip()
    if p.returncode == 0 and tok:
        return tok, f"gh auth token, resolved in {cwd or 'the server cwd'}"
    msg = (p.stderr or "").strip().splitlines()
    return None, msg[0] if msg else f"gh auth token exited {p.returncode}"


def gh_identity(cwd: str | None) -> str | None:
    if not shutil.which("gh"):
        return None
    try:
        p = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                           capture_output=True, text=True,
                           timeout=SUBPROC_TIMEOUT,
                           cwd=cwd if cwd and Path(cwd).is_dir() else None)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (p.stdout or "").strip() or None


# The battery, declared in order and in one place. Two things need it: the
# report, so a run that stopped at check three still SHOWS checks four through
# fifteen as unmeasured rather than omitting them, and the page, which draws
# the rows before any answer has come back. A check that vanishes from a report
# because it never ran is the exact collapse this file exists to prevent — the
# reader cannot tell "we looked and it was fine" from "it is not on the list".
CHECK_ORDER = [
    ("directory", "the directory exists"),
    ("git", "it is a git work tree"),
    ("remote", "it has a remote"),
    ("forge", "the remote is on GitHub"),
    ("gh-cli", "the gh CLI is available"),
    ("identity", "the account this repository resolves to"),
    ("token", "an API token is available"),
    ("access", "the API can see this repository"),
    ("issues", "the issue tracker is enabled"),
    ("activity", "the repository is live"),
    ("volume", "how much history there is"),
    ("rate", "this hour's request budget"),
    ("state", "somewhere to keep the mined history"),
    ("duplicate", "not already being watched"),
    ("marker", "does this repository use the fix-event marker"),
]


def _count_phrase(n, noun: str, plural: str | None = None) -> str:
    """"1,482 comments", "one comment", or "an unknown number of comments".

    The third case is why this exists. A stream whose length GitHub will not
    report must not print as "0 comments", which is a measurement, and must not
    be silently omitted either, which is worse — it removes the reader's chance
    to notice that a number they are about to rely on was never taken.
    """
    many = plural or (noun + "s")
    if n is None:
        return f"an unknown number of {many}"
    return f"{n:,} {noun if n == 1 else many}"


def _human_minutes(requests: int) -> str:
    # Measured against omarchy: ~590 conditional round trips in ~13 minutes,
    # so roughly 1.3s a page including GitHub's own pacing. It is an estimate
    # and is labelled as one everywhere it surfaces.
    mins = requests * 1.3 / 60
    if mins < 1:
        return "under a minute"
    if mins < 90:
        return f"about {round(mins)} minute{'s' if round(mins) != 1 else ''}"
    return f"about {mins / 60:.1f} hours"


def preflight(path: str, *, known_slugs=(), state_dir: Path | None = None,
              deep: bool = True) -> dict:
    """Everything that can be learned about a candidate before mining it.

    `deep` controls whether the three counting requests are spent. The list
    view calls this shallow for speed; the induction panel calls it deep,
    because the one number a person actually wants before saying yes is how
    long this will take.
    """
    b = Battery()
    p = Path(path).expanduser()
    meta: dict = {"path": str(p)}

    # 1 — the directory itself
    if not p.exists():
        b.add("directory", "the directory exists", FAIL,
              f"nothing at {p}", "check the path")
    elif not p.is_dir():
        b.add("directory", "the directory exists", FAIL,
              f"{p} is a file, not a directory")
    elif not os.access(p, os.R_OK | os.X_OK):
        b.add("directory", "the directory exists", FAIL,
              f"{p} is not readable by this user")
    else:
        try:
            p = p.resolve()
        except OSError:
            pass
        meta["path"] = str(p)
        b.add("directory", "the directory exists", OK, str(p))

    # 2 — is it a work tree
    gd = git_dir_of(p) if not b.blocked else None
    if not b.blocked:
        if gd is None:
            b.add("git", "it is a git work tree", FAIL,
                  "no .git here — the observatory watches repositories, not folders",
                  "point this at the repository's own directory")
        else:
            b.add("git", "it is a git work tree", OK,
                  f"git dir: {gd}")

    # 3 — a remote
    found = read_remote(p) if not b.blocked else None
    if not b.blocked:
        if not found:
            b.add("remote", "it has a remote", FAIL,
                  "this repository has no remote configured, so there is no "
                  "issue tracker to watch",
                  "git remote add origin <url>")
        else:
            meta["remote_name"], meta["remote"] = found
            b.add("remote", "it has a remote", OK,
                  f"{found[0]} → {found[1]}")

    # 4 — the forge
    parsed = parse_remote(found[1]) if found else None
    if not b.blocked:
        if not parsed:
            b.add("forge", "the remote is on GitHub", FAIL,
                  f"could not read owner/repo out of {found[1]!r}")
        else:
            real = resolve_host(parsed["host"])
            meta.update(parsed)
            meta["real_host"] = real
            meta["nwo"] = f"{parsed['owner']}/{parsed['repo']}"
            meta["slug"] = slug_for(parsed["owner"], parsed["repo"])
            if real.lower() not in ("github.com", "www.github.com"):
                b.add("forge", "the remote is on GitHub", FAIL,
                      f"host {parsed['host']}"
                      + (f" (→ {real})" if real != parsed["host"] else "")
                      + " — the miner speaks only the github.com API",
                      "GitHub Enterprise and GitLab are not supported yet")
            else:
                alias = "" if real == parsed["host"] else \
                    f"  ({parsed['host']} is an ssh alias for {real})"
                b.add("forge", "the remote is on GitHub", OK,
                      meta["nwo"] + alias, data={"nwo": meta["nwo"]})

    # 5 — the gh CLI, which is where a token comes from on this machine
    gh_exe = shutil.which("gh")
    if not b.blocked:
        if not gh_exe:
            b.add("gh-cli", "the gh CLI is available", WARN,
                  "no gh on PATH — a token can still come from GITHUB_TOKEN",
                  "https://cli.github.com")
        else:
            ver = ""
            try:
                r = subprocess.run([gh_exe, "--version"], capture_output=True,
                                   text=True, timeout=SUBPROC_TIMEOUT)
                ver = (r.stdout or "").splitlines()[0] if r.stdout else ""
            except (OSError, subprocess.TimeoutExpired, IndexError):
                ver = ""
            b.add("gh-cli", "the gh CLI is available", OK,
                  f"{ver or 'gh'} at {gh_exe}")

    # 6 — which identity this repository resolves to
    token, token_from = (None, "not looked for")
    if not b.blocked:
        token, token_from = gh_token_for(meta.get("path"))
        who = gh_identity(meta.get("path")) if gh_exe else None
        if who:
            b.add("identity", "the account this repository resolves to", OK,
                  f"@{who}  ·  resolved with the repository as the working "
                  "directory, so a per-repo account wrapper picks the right one",
                  data={"login": who})
            meta["login"] = who
        else:
            b.skip("identity", "the account this repository resolves to",
                   "gh could not name an account — the identity behind the "
                   "token below is unverified, not absent")

    # 7 — a token, and what its absence costs
    if not b.blocked:
        if token:
            b.add("token", "an API token is available", OK,
                  f"5,000 requests an hour — the whole history is reachable.  "
                  f"Source: {token_from}")
        else:
            b.add("token", "an API token is available", WARN,
                  f"none found ({token_from}). Unauthenticated GitHub allows 60 "
                  "requests an hour, which is three pages — the manifest would "
                  "be a two-day slice of the repository and would say so",
                  "gh auth login")

    # 8 — can we actually see it
    repo_meta = None
    if not b.blocked:
        status, body, _ = _get(f"/repos/{meta['nwo']}", token)
        if status == 200 and isinstance(body, dict):
            repo_meta = body
            bits = []
            if body.get("private"):
                bits.append("private")
            if body.get("fork"):
                bits.append("a fork")
            if body.get("archived"):
                bits.append("archived")
            b.add("access", "the API can see this repository", OK,
                  f"200 OK — {meta['nwo']}"
                  + (f" ({', '.join(bits)})" if bits else ""))
        elif status == 404:
            b.add("access", "the API can see this repository", FAIL,
                  "404 — either it does not exist under that name, or the token "
                  "in play cannot see it. A private repository looks exactly "
                  "like a missing one to a token without access.",
                  "gh auth login, or gh auth refresh -s repo")
        elif status in (401, 403):
            b.add("access", "the API can see this repository", FAIL,
                  f"{status} — "
                  + ((body or {}).get("message") or "refused"),
                  "check the token's scopes, or wait for the rate limit to reset")
        elif status == 0:
            b.add("access", "the API can see this repository", FAIL,
                  "the network did not answer: "
                  + ((body or {}).get("message") or "unknown"),
                  "this is not a permission problem — retry when online")
        else:
            b.add("access", "the API can see this repository", FAIL,
                  f"unexpected status {status}")

    # 9 — an issue tracker to watch
    if not b.blocked and repo_meta is not None:
        if repo_meta.get("has_issues"):
            b.add("issues", "the issue tracker is enabled", OK,
                  f"{repo_meta.get('open_issues_count', 0)} open right now "
                  "(GitHub counts open pull requests in that number)")
        else:
            b.add("issues", "the issue tracker is enabled", FAIL,
                  "issues are turned off on this repository — there is nothing "
                  "for the observatory to watch",
                  "enable Issues in the repository settings")

    # 10 — is anything still happening here
    if not b.blocked and repo_meta is not None:
        if repo_meta.get("archived"):
            b.add("activity", "the repository is live", WARN,
                  "archived — the swarm will be a complete, permanently frozen "
                  "picture. That is a legitimate thing to watch; it will simply "
                  "never move again.")
        else:
            pushed = repo_meta.get("pushed_at") or ""
            b.add("activity", "the repository is live", OK,
                  f"last push {pushed[:10] or 'unknown'}")

    # 11 — how much there is, and what it will cost
    if not b.blocked and repo_meta is not None:
        if not deep:
            b.skip("volume", "how much history there is",
                   "not measured — the full battery counts it")
        else:
            nwo = meta["nwo"]
            issues, partial, st1 = _search_count(nwo, token)
            comments, _ = _count_via_link(f"/repos/{nwo}/issues/comments", token)
            events, _ = _count_via_link(f"/repos/{nwo}/issues/events", token)
            if issues is None:
                b.skip("volume", "how much history there is",
                       f"the search index answered {st1} — the size of this "
                       "repository is unmeasured, which is not the same as small")
            else:
                # Only the streams that answered are counted. A stream whose
                # length came back unknown adds nothing to the estimate and is
                # named as unknown in the sentence, because an estimate that
                # silently treats an unmeasured stream as empty is exactly the
                # confident wrong number this whole program is built against.
                counted = [n for n in (issues, comments, events) if n is not None]
                unknown_streams = [
                    name for name, n in (("comments", comments), ("events", events))
                    if n is None]
                pages = sum(-(-n // 100) for n in counted)
                meta["estimate"] = {
                    "artifacts": issues, "comments": comments,
                    "events": events, "requests": pages,
                    "partial_index": partial,
                    "unknown_streams": unknown_streams,
                    "first_mine": _human_minutes(pages),
                }
                notes = []
                if events is not None and events >= 30000:
                    notes.append(
                        "GitHub stops serving this repository's event stream at "
                        "30,000 events, so the event lane will begin part-way "
                        "through its life — the manifest records that as a cap "
                        "reached, never as the start of the history")
                if unknown_streams:
                    notes.append(
                        "the " + " and ".join(unknown_streams) + " stream is "
                        "cursor-paginated here and its length cannot be known "
                        "without walking it, so the figure below is a floor")
                if partial:
                    notes.append("the search index reported itself incomplete, "
                                 "so the artifact count is approximate")
                status = WARN if pages > 1200 else OK
                b.add("volume", "how much history there is", status,
                      f"{_count_phrase(issues, 'issue or pull request', 'issues and pull requests')} · "
                      f"{_count_phrase(comments, 'comment')} · "
                      f"{_count_phrase(events, 'event')} → "
                      f"{'at least ' if unknown_streams else 'about '}{pages:,} "
                      f"requests, {_human_minutes(pages)} for the first mine, "
                      "then near-free forever (every later request is conditional)"
                      + ("".join("\n" + n for n in notes)),
                      data=meta["estimate"])

            # 12 — does that fit in this hour's budget
            status, body, headers = _get("/rate_limit", token)
            if status == 200 and isinstance(body, dict):
                core = ((body.get("resources") or {}).get("core")
                        or body.get("rate") or {})
                remaining = core.get("remaining")
                limit = core.get("limit")
                reset = core.get("reset")
                need = (meta.get("estimate") or {}).get("requests")
                meta["rate"] = {"remaining": remaining, "limit": limit,
                                "reset": reset}
                if remaining is None:
                    b.skip("rate", "this hour's request budget",
                           "GitHub did not report one")
                elif need is None:
                    b.add("rate", "this hour's request budget", OK,
                          f"{remaining:,} of {limit:,} left")
                elif remaining >= need:
                    b.add("rate", "this hour's request budget", OK,
                          f"{remaining:,} of {limit:,} left, and the first mine "
                          f"needs about {need:,} — it fits in one hour")
                else:
                    when = time.strftime("%H:%M", time.localtime(reset)) if reset else "?"
                    b.add("rate", "this hour's request budget", WARN,
                          f"{remaining:,} left and the first mine needs about "
                          f"{need:,}. It will pause when the budget runs out and "
                          f"resume after {when}; nothing is lost, it just takes "
                          "more than one hour to fill in.")
            else:
                b.skip("rate", "this hour's request budget",
                       f"/rate_limit answered {status}")

    # 13 — somewhere to put it
    if not b.blocked:
        target = (state_dir / "projects" / meta["slug"]) if state_dir and meta.get("slug") else None
        if target is None:
            b.skip("state", "somewhere to keep the mined history",
                   "no state directory was named")
        else:
            base = state_dir
            try:
                base.mkdir(parents=True, exist_ok=True)
                writable = os.access(base, os.W_OK)
            except OSError as exc:
                writable = False
                b.add("state", "somewhere to keep the mined history", FAIL,
                      f"cannot create {base}: {exc}")
            if writable:
                free = shutil.disk_usage(base).free
                est = ((meta.get("estimate") or {}).get("artifacts") or 0) * 2600
                if est and free < est * 4:
                    b.add("state", "somewhere to keep the mined history", WARN,
                          f"{free / 1e9:.1f}GB free at {base}; this project's "
                          f"manifest and cache will want roughly "
                          f"{est / 1e6:.0f}MB")
                else:
                    size = (f" · about {est / 1e6:.0f}MB expected"
                            if est >= 1e6 else
                            " · under a megabyte expected" if est else "")
                    b.add("state", "somewhere to keep the mined history", OK,
                          f"{base}{size}"
                          + (f" · {free / 1e9:.0f}GB free" if est else ""))

    # 14 — is it already being watched
    if not b.blocked and meta.get("slug"):
        if meta["slug"] in known_slugs:
            b.add("duplicate", "not already being watched", WARN,
                  "this project is already in the observatory — inducting it "
                  "again re-points it at this directory and keeps the history "
                  "already mined")
        else:
            b.add("duplicate", "not already being watched", OK, "new to the observatory")

    # 15 — the attribution contract, which is only knowable after mining
    if not b.blocked:
        b.skip("marker", "does this repository use the fix-event marker",
               "unmeasured until the first mine. Repositories without it are "
               "still fully watchable — every artifact is then scored by the "
               "named agent-smell heuristics instead, and the page says which.",
               informational=True)

    b.fill_unreached()
    return {
        "path": str(p),
        "meta": meta,
        "checks": b.checks,
        "tally": b.tally(),
        "verdict": b.verdict(),
        "blocked": b.blocked,
        "stopped_by": b.stopped_by,
        "nwo": meta.get("nwo"),
        "slug": meta.get("slug"),
    }
