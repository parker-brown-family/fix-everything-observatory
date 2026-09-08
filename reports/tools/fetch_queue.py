#!/usr/bin/env python3
"""Fetch the live open queue (issues + PRs) with bodies, for collapse-map clustering.

Caches to queue.json so the clustering pass can be re-run for free.
"""
import json, subprocess, sys, pathlib, time

GH = "/home/parker/bin/gh"
REPO = "omacom/omarchy"
OUT = pathlib.Path(__file__).parent / "queue.json"

def gql(q, cursor=None):
    args = [GH, "api", "graphql", "-f", "query=" + q, "-f", "q=" + CURRENT_Q]
    if cursor:
        args += ["-f", "cursor=" + cursor]
    for attempt in range(3):
        o = subprocess.run(args, capture_output=True, text=True)
        if o.returncode == 0:
            try:
                d = json.loads(o.stdout)
            except json.JSONDecodeError:
                time.sleep(5); continue
            if "errors" in d:
                print("GQL ERR", str(d["errors"])[:200], file=sys.stderr)
                time.sleep(5); continue
            return d
        print("ERR", o.stderr[:200], file=sys.stderr)
        time.sleep(5)
    return None

ISSUE_Q = """
query($cursor:String,$q:String!){
 search(query:$q,type:ISSUE,first:50,after:$cursor){
  issueCount pageInfo{hasNextPage endCursor}
  nodes{... on Issue{
    number title body createdAt
    author{login __typename}
    labels(first:5){nodes{name}}
    comments{totalCount}
    reactions{totalCount}
  }}}}
"""

PR_Q = """
query($cursor:String,$q:String!){
 search(query:$q,type:ISSUE,first:50,after:$cursor){
  issueCount pageInfo{hasNextPage endCursor}
  nodes{... on PullRequest{
    number title body createdAt
    author{login __typename}
    labels(first:5){nodes{name}}
    comments{totalCount}
    changedFiles additions deletions
    closingIssuesReferences(first:10){nodes{number}}
    files(first:20){nodes{path}}
  }}}}
"""

def harvest(query, q, pages):
    global CURRENT_Q
    CURRENT_Q = q
    rows, cur = [], None
    for i in range(pages):
        d = gql(query, cur)
        if not d:
            break
        s = d["data"]["search"]
        rows += [n for n in s["nodes"] if n]
        print(f"  page {i+1}: {len(rows)} rows", file=sys.stderr)
        if not s["pageInfo"]["hasNextPage"]:
            break
        cur = s["pageInfo"]["endCursor"]
    return rows

CURRENT_Q = ""
print("issues...", file=sys.stderr)
issues = harvest(ISSUE_Q, f"repo:{REPO} is:issue is:open sort:created-desc", 20)
print("prs...", file=sys.stderr)
prs = harvest(PR_Q, f"repo:{REPO} is:pr is:open sort:created-desc", 20)

# trim bodies on the way to disk: the clustering only needs the first ~3k chars
for r in issues + prs:
    if r.get("body") and len(r["body"]) > 4000:
        r["body"] = r["body"][:4000]

OUT.write_text(json.dumps({"issues": issues, "prs": prs}, indent=0))
print(f"wrote {OUT}: {len(issues)} issues, {len(prs)} prs", file=sys.stderr)
