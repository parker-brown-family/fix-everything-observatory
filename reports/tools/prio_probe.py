#!/usr/bin/env python3
"""Probe omacom/omarchy for signals that actually predict maintainer attention."""
import json, subprocess, statistics, sys, datetime, collections

GH = "/home/parker/bin/gh"
REPO = "omacom/omarchy"

def gql(query, **vars):
    args = [GH, "api", "graphql", "-f", "query=" + query]
    for k, v in vars.items():
        args += ["-f", f"{k}={v}"]
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode:
        print("ERR", out.stderr[:400], file=sys.stderr)
        return None
    return json.loads(out.stdout)

Q = """
query($cursor:String, $q:String!) {
  search(query:$q, type:ISSUE, first:100, after:$cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on Issue {
        number title createdAt closedAt stateReason authorAssociation
        comments { totalCount }
        reactions { totalCount }
        participants { totalCount }
        labels(first:10) { nodes { name } }
        timelineItems(first:0, itemTypes:[CROSS_REFERENCED_EVENT]) { totalCount }
      }
      ... on PullRequest {
        number title createdAt closedAt mergedAt authorAssociation
        additions deletions changedFiles
        comments { totalCount }
        reactions { totalCount }
        participants { totalCount }
        labels(first:10) { nodes { name } }
      }
    }
  }
}
"""

def harvest(q, pages=4):
    rows, cursor = [], None
    total = None
    for _ in range(pages):
        d = gql(Q, q=q, **({"cursor": cursor} if cursor else {}))
        if not d:
            break
        s = d["data"]["search"]
        total = s["issueCount"]
        rows += s["nodes"]
        if not s["pageInfo"]["hasNextPage"]:
            break
        cursor = s["pageInfo"]["endCursor"]
    return total, rows

def hours(a, b):
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.datetime.strptime(b, fmt) - datetime.datetime.strptime(a, fmt)).total_seconds() / 3600

def med(xs):
    return round(statistics.median(xs), 1) if xs else None

out = {}

# 1. recently closed issues
tot, closed = harvest(f"repo:{REPO} is:issue is:closed closed:>=2026-07-01", pages=5)
out["closed_issues_since_jul1"] = tot
rows = [r for r in closed if r.get("__typename") == "Issue" and r.get("closedAt")]
out["closed_sampled"] = len(rows)
by_reason = collections.Counter(r["stateReason"] for r in rows)
out["close_reason"] = dict(by_reason)

def bucket(pred, name, rs):
    hit = [r for r in rs if pred(r)]
    miss = [r for r in rs if not pred(r)]
    return {
        "signal": name,
        "n_with": len(hit), "n_without": len(miss),
        "completed_rate_with": round(sum(1 for r in hit if r["stateReason"] == "COMPLETED") / len(hit), 3) if hit else None,
        "completed_rate_without": round(sum(1 for r in miss if r["stateReason"] == "COMPLETED") / len(miss), 3) if miss else None,
        "median_hours_with": med([hours(r["createdAt"], r["closedAt"]) for r in hit]),
        "median_hours_without": med([hours(r["createdAt"], r["closedAt"]) for r in miss]),
    }

sigs = [
    (lambda r: r["reactions"]["totalCount"] >= 3, "reactions>=3"),
    (lambda r: r["reactions"]["totalCount"] >= 8, "reactions>=8"),
    (lambda r: r["comments"]["totalCount"] >= 5, "comments>=5"),
    (lambda r: r["participants"]["totalCount"] >= 4, "participants>=4"),
    (lambda r: r["timelineItems"]["totalCount"] >= 1, "cross-referenced>=1"),
    (lambda r: bool(r["labels"]["nodes"]), "has any label"),
    (lambda r: any(l["name"] == "bug" for l in r["labels"]["nodes"]), "label:bug"),
    (lambda r: r["authorAssociation"] in ("MEMBER", "OWNER", "COLLABORATOR"), "author is member/owner"),
]
out["closed_issue_signals"] = [bucket(p, n, rows) for p, n in sigs]

# distribution of attention on OPEN issues
tot_open, openrows = harvest(f"repo:{REPO} is:issue is:open", pages=5)
orows = [r for r in openrows if r.get("__typename") == "Issue"]
out["open_issues_total"] = tot_open
out["open_sampled"] = len(orows)
out["open_reaction_hist"] = dict(collections.Counter(min(r["reactions"]["totalCount"], 5) for r in orows))
out["open_comment_hist"] = dict(collections.Counter(min(r["comments"]["totalCount"], 5) for r in orows))
out["open_labelled_pct"] = round(sum(1 for r in orows if r["labels"]["nodes"]) / len(orows), 3) if orows else None
out["open_label_freq"] = dict(collections.Counter(l["name"] for r in orows for l in r["labels"]["nodes"]))

# 2. PRs
tot_pr, prs = harvest(f"repo:{REPO} is:pr is:closed closed:>=2026-07-01", pages=5)
prows = [r for r in prs if r.get("__typename") == "PullRequest"]
out["closed_prs_since_jul1"] = tot_pr
out["pr_sampled"] = len(prows)
merged = [r for r in prows if r.get("mergedAt")]
out["pr_merge_rate"] = round(len(merged) / len(prows), 3) if prows else None
out["pr_median_hours_to_merge"] = med([hours(r["createdAt"], r["mergedAt"]) for r in merged])
out["pr_median_hours_to_reject"] = med([hours(r["createdAt"], r["closedAt"]) for r in prows if not r.get("mergedAt")])

def prbucket(pred, name):
    hit = [r for r in prows if pred(r)]
    miss = [r for r in prows if not pred(r)]
    return {"signal": name, "n_with": len(hit),
            "merge_rate_with": round(sum(1 for r in hit if r.get("mergedAt")) / len(hit), 3) if hit else None,
            "merge_rate_without": round(sum(1 for r in miss if r.get("mergedAt")) / len(miss), 3) if miss else None,
            "median_h_with": med([hours(r["createdAt"], r["closedAt"]) for r in hit])}

out["pr_signals"] = [
    prbucket(lambda r: (r["additions"] + r["deletions"]) <= 20, "diff <=20 lines"),
    prbucket(lambda r: (r["additions"] + r["deletions"]) > 200, "diff >200 lines"),
    prbucket(lambda r: r["changedFiles"] == 1, "single file"),
    prbucket(lambda r: r["authorAssociation"] in ("MEMBER", "OWNER", "COLLABORATOR"), "author member/owner"),
    prbucket(lambda r: r["comments"]["totalCount"] == 0, "zero comments"),
    prbucket(lambda r: r["reactions"]["totalCount"] >= 2, "reactions>=2"),
]

# open PR backlog age
tot_openpr, oprs = harvest(f"repo:{REPO} is:pr is:open", pages=3)
op = [r for r in oprs if r.get("__typename") == "PullRequest"]
out["open_prs_total"] = tot_openpr
now = "2026-09-07T18:00:00Z"
out["open_pr_median_age_days"] = med([hours(r["createdAt"], now) / 24 for r in op])

print(json.dumps(out, indent=1))
