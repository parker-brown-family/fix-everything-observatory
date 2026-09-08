#!/usr/bin/env python3
"""Lighter probe: PR merge behaviour + who acts + duplicate clustering on open issues."""
import json, subprocess, statistics, sys, datetime, collections, re

GH = "/home/parker/bin/gh"
REPO = "omacom/omarchy"

def gql(query, **vars):
    args = [GH, "api", "graphql", "-f", "query=" + query]
    for k, v in vars.items():
        args += ["-f", f"{k}={v}"]
    o = subprocess.run(args, capture_output=True, text=True)
    if o.returncode:
        print("ERR", o.stderr[:300], file=sys.stderr)
        return None
    return json.loads(o.stdout)

def hours(a, b):
    f = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.datetime.strptime(b, f) - datetime.datetime.strptime(a, f)).total_seconds() / 3600

def med(xs):
    return round(statistics.median(xs), 1) if xs else None

out = {}

PRQ = """
query($cursor:String,$q:String!){
 search(query:$q,type:ISSUE,first:50,after:$cursor){
  issueCount pageInfo{hasNextPage endCursor}
  nodes{... on PullRequest{
    number createdAt closedAt mergedAt additions deletions changedFiles
    authorAssociation
    author{login}
    mergedBy{login}
    comments{totalCount}
    reviews(first:0){totalCount}
    closingIssuesReferences(first:0){totalCount}
  }}
 }}
"""
rows, cur = [], None
for _ in range(6):
    d = gql(PRQ, q=f"repo:{REPO} is:pr is:closed closed:>=2026-08-01", **({"cursor": cur} if cur else {}))
    if not d:
        break
    s = d["data"]["search"]
    out["closed_prs_since_aug1"] = s["issueCount"]
    rows += [n for n in s["nodes"] if n]
    if not s["pageInfo"]["hasNextPage"]:
        break
    cur = s["pageInfo"]["endCursor"]

out["pr_sampled"] = len(rows)
merged = [r for r in rows if r.get("mergedAt")]
out["pr_merge_rate"] = round(len(merged) / len(rows), 3) if rows else None
out["pr_median_h_to_merge"] = med([hours(r["createdAt"], r["mergedAt"]) for r in merged])
out["pr_median_h_to_close_unmerged"] = med([hours(r["createdAt"], r["closedAt"]) for r in rows if not r.get("mergedAt")])
out["pr_merged_by"] = dict(collections.Counter((r.get("mergedBy") or {}).get("login") for r in merged).most_common(8))
out["pr_authors_top"] = dict(collections.Counter((r.get("author") or {}).get("login") for r in rows).most_common(10))

def pb(pred, name):
    hit = [r for r in rows if pred(r)]
    miss = [r for r in rows if not pred(r)]
    return {"signal": name, "n": len(hit),
            "merge_with": round(sum(1 for r in hit if r.get("mergedAt")) / len(hit), 3) if hit else None,
            "merge_without": round(sum(1 for r in miss if r.get("mergedAt")) / len(miss), 3) if miss else None,
            "med_h_with": med([hours(r["createdAt"], r["closedAt"]) for r in hit])}

out["pr_signals"] = [
    pb(lambda r: (r["additions"] + r["deletions"]) <= 20, "diff<=20"),
    pb(lambda r: (r["additions"] + r["deletions"]) > 200, "diff>200"),
    pb(lambda r: r["changedFiles"] == 1, "1 file"),
    pb(lambda r: r["changedFiles"] > 5, ">5 files"),
    pb(lambda r: r["authorAssociation"] in ("MEMBER", "OWNER", "COLLABORATOR"), "member/owner author"),
    pb(lambda r: r["comments"]["totalCount"] == 0, "0 comments"),
    pb(lambda r: r["reviews"]["totalCount"] > 0, "has review"),
    pb(lambda r: r["closingIssuesReferences"]["totalCount"] > 0, "closes an issue"),
]

print(json.dumps(out, indent=1))
