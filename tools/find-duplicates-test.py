#!/usr/bin/env python3
"""Smoke test for find-duplicates, on a fixture with known-correct answers.

Runs the real code path (normalise → Grouper → plan) against a hand-built queue
where every expected grouping is known in advance, so a regression in the edge
rules fails here rather than in a report someone is about to act on.

    python3 tools/find-duplicates-test.py
"""
import importlib.machinery, importlib.util, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_loader(
    "qc", importlib.machinery.SourceFileLoader("qc", str(HERE / "find-duplicates.py")))
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)

D = "2026-09-01T10:00:00Z"


def issue(n, title, body="", author="someone", created=D):
    return {"number": n, "title": title, "body": body, "createdAt": created,
            "url": f"https://example/{n}", "author": {"login": author},
            "labels": {"nodes": []}, "comments": {"totalCount": 0}}


def pr(n, title, body="", author="someone", closes=(), files=(), mergeable="MERGEABLE",
       decision=None, assoc="NONE", draft=False, adds=10, dels=2, created=D):
    return {"number": n, "title": title, "body": body, "createdAt": created,
            "url": f"https://example/{n}", "isDraft": draft, "mergeable": mergeable,
            "authorAssociation": assoc, "reviewDecision": decision,
            "additions": adds, "deletions": dels, "changedFiles": len(files) or 1,
            "author": {"login": author},
            "closingIssuesReferences": {"nodes": [{"number": c} for c in closes]},
            "files": {"nodes": [{"path": f} for f in files]},
            "commits": {"nodes": [{"commit": {"statusCheckRollup": None}}]},
            "reviews": {"totalCount": 0}, "comments": {"totalCount": 0}}


issues = [
    # one surface, three independent reporters, different words
    issue(101, "Network panel reports 100% packet loss on a healthy link",
          "The wifi panel probe pings 1.1.1.1 and reports total packet loss even though "
          "browsing works fine. Probe host unreachable on my network.", "ana"),
    issue(102, "Wifi indicator shows packet loss when 1.1.1.1 is blocked",
          "Our corporate DNS blocks 1.1.1.1 so the network probe reports loss. The panel "
          "should fall back to another host before claiming the link is down.", "ben"),
    issue(103, "network-status: false packet loss where the probe host is unreachable",
          "Probe pings a single hardcoded host; when that host is blocked the panel claims "
          "100% packet loss on a working connection.", "cara"),
    # a different surface entirely
    issue(110, "Bar clock ignores locale and always renders English month names",
          "The clock widget formats dates in English regardless of LC_TIME.", "dee"),
    # an issue whose fix already shipped
    issue(120, "Keyboard backlight stays off after unlock",
          "After unlocking, the keyboard backlight never comes back. See #900 for the same "
          "thing.", "eli"),
    # a lone issue with a clean patch waiting
    issue(130, "Screenshot tool writes to the wrong directory", "", "fay"),
]

prs = [
    # the patch for the packet-loss surface, closing one of its issues
    pr(201, "Fall back to a second probe host before reporting packet loss",
       "Adds a fallback host and a TCP handshake check.\n\nFixes #101", "gus",
       closes=[101], files=["bin/network-status", "test/network_test.sh"],
       assoc="CONTRIBUTOR"),
    # a competing patch for the same surface, conflicting so it cannot be the winner
    pr(202, "Use a second host when the network probe fails",
       "Same idea: probe a second host.\n\nRelated to #102", "hana",
       closes=[], files=["bin/network-status"], mergeable="CONFLICTING"),
    # a third competing patch, mergeable but larger and closing nothing
    pr(203, "Rework the network probe to try several hosts",
       "Reworks the probe loop to walk a host list. Refs #103", "ivan",
       closes=[], files=["bin/network-status"], adds=300, dels=120),
    # unique, clean, closes an issue: a free win
    pr(210, "Write screenshots to the configured directory", "Fixes #130", "jo",
       closes=[130], files=["bin/screenshot"]),
    # somebody with standing asked for changes: never the recommendation
    pr(220, "Rewrite the clock widget locale handling",
       "Fixes #110", "kim", closes=[110], files=["bar/clock.qml"],
       decision="CHANGES_REQUESTED"),
    # a draft, also never the recommendation
    pr(221, "WIP: clock locale", "Refs #110", "lee", files=["bar/clock.qml"], draft=True),
]

settled = {
    "since": "2026-08-01",
    "merged": [{"number": 900, "title": "Restore keyboard backlight state on unlock",
                "body": "Fixes #120 — restores the backlight level saved before lock.",
                "createdAt": "2026-08-10T09:00:00Z", "mergedAt": "2026-08-12T09:00:00Z",
                "url": "https://example/900", "author": {"login": "maintainer"},
                "files": {"nodes": [{"path": "bin/brightness-keyboard"}]},
                "closingIssuesReferences": {"nodes": [{"number": 120}]}}],
    "closed": [],
}

coverage = {"open_issues_total": len(issues), "open_issues_sampled": len(issues),
            "open_prs_total": len(prs), "open_prs_sampled": len(prs),
            "settled_since": "2026-08-01", "merged_sampled": 1, "closed_sampled": 0,
            "unexamined": 0}

items = qc.normalise(issues, prs, settled)
g = qc.Grouper(items, {"example"})
groups, find = g.build()
p = qc.plan("example/repo", items, groups, find, g.sim, g.edges, coverage)

fails = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got}" + ("" if ok else f"  (want {want})"))
    if not ok:
        fails.append(name)


print("find-duplicates fixture")

# the three packet-loss reports and their three patches are one surface
packet = [grp for grp in p["groups"] if 101 in [m["n"] for m in grp["members"]]]
check("packet-loss surface found", len(packet), 1)
if packet:
    members = sorted(m["n"] for m in packet[0]["members"])
    check("packet-loss members", members, [101, 102, 103, 201, 202, 203])
    check("packet-loss keeps the closing, non-conflicting patch", packet[0]["keep"], 201)
    check("packet-loss reporters counted", packet[0]["reporters"], 6)
    check("packet-loss trusted", packet[0]["confidence"], "high")

# the locale surface must not absorb the packet-loss one, and since its only patches
# are a draft and one somebody asked for changes on, it belongs in "stuck"
locale = [grp for grp in p["groups"] + p["stuck"] if 110 in [m["n"] for m in grp["members"]]]
check("locale surface separate", len(locale), 1)
if locale:
    check("locale members", sorted(m["n"] for m in locale[0]["members"]), [110, 220, 221])
    check("locale has no recommendation (changes requested, and a draft)",
          locale[0]["keep"], None)
    check("locale is listed as stuck, not as a collapse",
          locale[0] in p["stuck"], True)

# the backlight issue duplicates work already merged
check("already-fixed groups", len(p["already_fixed"]), 1)
if p["already_fixed"]:
    af = p["already_fixed"][0]
    check("already-fixed points at the merged PR", af["shipped"][0]["n"], 900)
    check("already-fixed lists the open issue", [o["n"] for o in af["still_open"]], [120])

# the lone clean patch is a free win, and the conflicting one is listed as such
check("free wins", [w["n"] for w in p["free_wins"]], [210])
check("conflicting", [c["n"] for c in p["conflicting"]], [202])

# a patch and the issue it closes is the normal shape of a fix, not a duplicate
check("patch + its own issue is not called duplication", p["summary"]["patch_plus_its_own_issue"], 1)
check("that pair is not in the collapse list",
      any(210 in [m["n"] for m in grp["members"]] for grp in p["groups"] + p["stuck"]), False)

# nothing mutating may ever appear in the printed commands
cmds = qc.render_commands(p)
check("commands contain no merge", "gh pr merge" in cmds, False)
check("commands contain no comment-only post", "gh issue comment" in cmds, False)
check("commands are close-only", all(l.split()[2] == "close"
                                     for l in cmds.splitlines()
                                     if l.startswith("gh ")), True)

# a group that is only a passing mention must not merge
check("stuck groups have no recommendation",
      all(grp["keep"] is None for grp in p["stuck"]), True)

print(f"\n{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
