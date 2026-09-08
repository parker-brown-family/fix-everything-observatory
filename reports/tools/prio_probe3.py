#!/usr/bin/env python3
"""Backlog shape: arrival rate, age distribution, and duplicate clustering on open issue titles."""
import json, subprocess, sys, datetime, collections, re, statistics

GH = "/home/parker/bin/gh"
REPO = "omacom/omarchy"
NOW = datetime.datetime(2026, 9, 7, 19, 0, 0)

def gql(gqlq, **v):
    a = [GH, "api", "graphql", "-f", "query=" + gqlq]
    for k, val in v.items():
        a += ["-f", f"{k}={val}"]
    o = subprocess.run(a, capture_output=True, text=True)
    if o.returncode:
        print("ERR", o.stderr[:300], file=sys.stderr)
        return None
    return json.loads(o.stdout)

Q = """
query($cursor:String,$q:String!){
 search(query:$q,type:ISSUE,first:100,after:$cursor){
  issueCount pageInfo{hasNextPage endCursor}
  nodes{
   ... on Issue{number title createdAt comments{totalCount} author{login}}
   ... on PullRequest{number title createdAt comments{totalCount} author{login}}
  }}}
"""

def harvest(q, pages=10):
    rows, cur, tot = [], None, None
    for _ in range(pages):
        d = gql(Q, q=q, **({"cursor": cur} if cur else {}))
        if not d:
            break
        s = d["data"]["search"]
        tot = s["issueCount"]
        rows += [n for n in s["nodes"] if n]
        if not s["pageInfo"]["hasNextPage"]:
            break
        cur = s["pageInfo"]["endCursor"]
    return tot, rows

def age_days(ts):
    return (NOW - datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")).total_seconds() / 86400

out = {}

for kind in ("issue", "pr"):
    tot, rows = harvest(f"repo:{REPO} is:{kind} is:open sort:created-desc", pages=10)
    ages = [age_days(r["createdAt"]) for r in rows]
    out[f"open_{kind}"] = {
        "total": tot, "sampled": len(rows),
        "median_age_days": round(statistics.median(ages), 2) if ages else None,
        "age_buckets": dict(collections.Counter(
            "<1d" if a < 1 else "1-7d" if a < 7 else "7-30d" if a < 30 else "30-90d" if a < 90 else ">90d"
            for a in ages)),
        "top_authors": dict(collections.Counter((r.get("author") or {}).get("login") for r in rows).most_common(8)),
        "zero_comment_pct": round(sum(1 for r in rows if r["comments"]["totalCount"] == 0) / len(rows), 3) if rows else None,
    }
    if kind == "issue":
        issue_rows = rows

STOP = set("a an the of on in to for with when after is are not does doesn't can't cannot and or my i it "
           "issue bug error fails failing broken doesn't work working from at by if but as be".split())

def toks(t):
    return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2]

clusters = collections.Counter()
for r in issue_rows:
    for w in set(toks(r["title"])):
        clusters[w] += 1
out["open_issue_title_terms"] = dict(clusters.most_common(30))

# bigram clustering: stronger duplicate signal
big = collections.Counter()
for r in issue_rows:
    t = toks(r["title"])
    for a, b in zip(t, t[1:]):
        big[a + " " + b] += 1
out["open_issue_title_bigrams"] = dict(big.most_common(25))
out["open_issue_sample_titles"] = [r["title"][:90] for r in issue_rows[:15]]

print(json.dumps(out, indent=1))
