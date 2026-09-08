#!/usr/bin/env python3
"""Build a collapse map of the open omarchy queue.

Four kinds of edge, each kept separate so a cluster can be defended by the evidence
that formed it rather than by a single opaque score:

  closes    PR -> issue, from closingIssuesReferences. Ground truth.
  mentions  a #1234 in the body pointing at another open item. Ground truth.
  files     two PRs touching the same file. Rare files only, weighted by rarity.
  text      cosine over tf-idf of title (x3) + first 1500 chars of body.

Clusters are connected components. The report keeps, per cluster, which edge kinds
formed it and how many DISTINCT non-agent-smelling reporters it has, because a
recurrence count that a single fleet can inflate is not evidence of anything.
"""
import json, re, math, pathlib, collections, sys, datetime

sys.path.insert(0, "/home/parker/Work/fix-everything-observatory")
from observatory import smell_of  # reuse the shipped heuristic, do not reinvent it

HERE = pathlib.Path(__file__).parent
DATA = json.loads((HERE / "queue.json").read_text())
OUT = pathlib.Path("/home/parker/Work/fix-everything-observatory/reports/2026-09-07-collapse-map.json")

STOP = set("""a an the of on in to for with when after is are not does doesn t can t cannot and or my i it
this that if but as be by at from was were has have had will would should could there their they them then
than so no yes you your we our us me he she his her its into out up down over under again very just only
issue issues bug bugs error errors fail fails failed failing broken break breaks work works working
please help thanks thank hi hello also still even more most some any all one two new old
omarchy omarchyos arch linux system user users using use used make makes made get gets got
describe description expected actual behavior behaviour steps reproduce reproduction version
title body report reported reporting open opened close closed fix fixes fixed
what where which who why how here need needs needed want wants
add adds added set sets setting settings run runs running start starts started
com http https github www org net md sh conf config file files
""".split())

NUM_RE = re.compile(r"#(\d+)")
TOK_RE = re.compile(r"[a-z][a-z0-9_.-]{2,}")


def toks(text, cap=None):
    t = (text or "").lower()
    if cap:
        t = t[:cap]
    out = []
    for w in TOK_RE.findall(t):
        w = w.strip(".-_")
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w)
    return out


# ---------- nodes ----------
nodes = {}          # number -> record
for kind, rows in (("issue", DATA["issues"]), ("pr", DATA["prs"])):
    for r in rows:
        author = (r.get("author") or {}).get("login") or "?"
        sm = smell_of({"title": r.get("title"), "body": r.get("body"),
                       "user": {"login": author,
                                "type": "Bot" if (r.get("author") or {}).get("__typename") == "Bot" else "User"}})
        nodes[r["number"]] = {
            "n": r["number"], "type": kind, "title": r.get("title") or "",
            "author": author, "created": r.get("createdAt"),
            "smell": sm["score"], "signals": sm["signals"],
            "comments": (r.get("comments") or {}).get("totalCount", 0),
            "files": [f["path"] for f in ((r.get("files") or {}).get("nodes") or [])],
            "closes": [c["number"] for c in ((r.get("closingIssuesReferences") or {}).get("nodes") or [])],
            "body": r.get("body") or "",
        }

print(f"nodes: {len(nodes)}", file=sys.stderr)

# ---------- edges ----------
edges = collections.defaultdict(set)   # (a,b) sorted -> {kinds}

def add(a, b, kind):
    if a == b or a not in nodes or b not in nodes:
        return
    edges[(min(a, b), max(a, b))].add(kind)

for n, r in nodes.items():
    for t in r["closes"]:
        add(n, t, "closes")
    for m in NUM_RE.findall(r["body"][:2500]):
        add(n, int(m), "mentions")

# same-file edges. First pass at 2..12 PRs per file produced a 1,025-item component:
# shared files chain the whole graph together transitively, so one edge kind silently
# ate half the queue. Tightened to rare files AND a pair sharing two of them.
byfile = collections.defaultdict(list)
for n, r in nodes.items():
    for f in r["files"]:
        byfile[f].append(n)
pairfiles = collections.Counter()
for f, ns in byfile.items():
    if 2 <= len(ns) <= 5:             # a file five PRs touch is not a coincidence
        for i in range(len(ns)):
            for j in range(i + 1, len(ns)):
                pairfiles[(min(ns[i], ns[j]), max(ns[i], ns[j]))] += 1
for (a, b), c in pairfiles.items():
    if c >= 2:
        add(a, b, "files")

# ---------- text similarity ----------
docs = {}
for n, r in nodes.items():
    tf = collections.Counter(toks(r["title"]) * 3 + toks(r["body"], cap=1500))
    docs[n] = tf

df = collections.Counter()
for tf in docs.values():
    df.update(tf.keys())
N = len(docs)

vecs = {}
for n, tf in docs.items():
    v = {}
    for w, c in tf.items():
        if df[w] < 2 or df[w] > N * 0.20:      # unique noise / repo boilerplate
            continue
        v[w] = (1 + math.log(c)) * math.log(N / df[w])
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    vecs[n] = {w: x / norm for w, x in v.items()}

inv = collections.defaultdict(list)
for n, v in vecs.items():
    for w in v:
        if df[w] <= 60:                        # candidate generation on rare terms only
            inv[w].append(n)

cand = collections.Counter()
for w, ns in inv.items():
    if len(ns) > 60:
        continue
    for i in range(len(ns)):
        for j in range(i + 1, len(ns)):
            cand[(min(ns[i], ns[j]), max(ns[i], ns[j]))] += 1

THRESH = 0.55
sims = {}
for (a, b), shared in cand.items():
    if shared < 2:
        continue
    va, vb = vecs[a], vecs[b]
    if len(va) > len(vb):
        va, vb = vb, va
    s = sum(x * vb.get(w, 0.0) for w, x in va.items())
    if s >= THRESH:
        sims[(a, b)] = round(s, 3)
        add(a, b, "text")

print(f"candidate pairs: {len(cand)}, text edges: {len(sims)}, all edges: {len(edges)}", file=sys.stderr)

# ---------- union-find ----------
parent = {n: n for n in nodes}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

def cos(a, b):
    va, vb = vecs[a], vecs[b]
    if len(va) > len(vb):
        va, vb = vb, va
    return sum(x * vb.get(w, 0.0) for w, x in va.items())

# Every edge that carries a union must be either ground truth (a PR that closes an issue,
# strong text agreement) or a weaker signal BACKED by topical agreement. Without this,
# a PR mentioning an unrelated ticket in passing merged a lock-screen focus bug with an
# unattended-update hang: 30 items in one cluster, none of it defensible.
TOPIC_FLOOR = 0.22
edge_sim = {}
unioning = []
for (a, b), ks in edges.items():
    s = cos(a, b)
    edge_sim[(a, b)] = round(s, 3)
    if "closes" in ks or "text" in ks or s >= TOPIC_FLOOR:
        unioning.append((a, b))

# A meta-issue listing thirty tickets is still a BRIDGE even when it is on topic:
# unioning through it merges every cluster it touches. Hubs do not carry the union;
# they are attached afterwards to their single strongest neighbour.
deg = collections.Counter()
for (a, b) in unioning:
    deg[a] += 1
    deg[b] += 1
HUB = 6
hubs = {n for n, d in deg.items() if d > HUB}

for (a, b) in unioning:
    if a not in hubs and b not in hubs:
        union(a, b)

RANK = {"closes": 4, "text": 3, "mentions": 2, "files": 1}
uset = set(unioning)
for h in sorted(hubs, key=lambda n: deg[n]):
    best, bestkey = None, (0, 0.0)
    for (a, b) in uset:
        if h not in (a, b):
            continue
        other = b if a == h else a
        if other in hubs:
            continue
        key = (max(RANK[k] for k in edges[(a, b)]), edge_sim[(a, b)])
        if key > bestkey:
            best, bestkey = other, key
    if best is not None:
        union(best, h)

groups = collections.defaultdict(list)
for n in nodes:
    groups[find(n)].append(n)

clusters = []
for root, members in groups.items():
    if len(members) < 2:
        continue
    kinds = collections.Counter()
    sims_in = []
    for (a, b), ks in edges.items():
        if find(a) == root and find(b) == root:
            for k in ks:
                kinds[k] += 1
            sims_in.append(edge_sim[(a, b)])
    ms = sorted(members, key=lambda n: nodes[n]["created"])
    humans = {nodes[n]["author"] for n in ms if nodes[n]["smell"] < 2}
    clusters.append({
        "id": root,
        "size": len(ms),
        "issues": sum(1 for n in ms if nodes[n]["type"] == "issue"),
        "prs": sum(1 for n in ms if nodes[n]["type"] == "pr"),
        "edge_kinds": dict(kinds),
        "median_edge_similarity": round(sorted(sims_in)[len(sims_in) // 2], 3) if sims_in else None,
        "hard_evidence": bool(kinds["closes"] or kinds["mentions"] or kinds["files"]),
        "distinct_authors": len({nodes[n]["author"] for n in ms}),
        "distinct_low_smell_authors": len(humans),
        "representative": ms[0],
        "members": [{"n": n, "type": nodes[n]["type"], "title": nodes[n]["title"][:110],
                     "author": nodes[n]["author"], "smell": nodes[n]["smell"],
                     "created": nodes[n]["created"]} for n in ms],
    })

clusters.sort(key=lambda c: (-c["size"], c["representative"]))

clustered = sum(c["size"] for c in clusters)
hard = [c for c in clusters if c["hard_evidence"]]
textonly = [c for c in clusters if not c["hard_evidence"]]

report = {
    "generated": datetime.datetime.now().isoformat(timespec="seconds"),
    "repo": "omacom/omarchy",
    "method": {
        "nodes": "1000 newest open issues + 1000 newest open PRs (GitHub search ceiling)",
        "edges": "closes | mentions | same rare file | tf-idf cosine >= %.2f on title(x3)+body[:1500]" % THRESH,
        "clusters": "connected components of the union of those edges",
    },
    "stats": {
        "nodes": len(nodes),
        "edges": len(edges),
        "hub_nodes_excluded_from_bridging": len(hubs),
        "text_edges": len(sims),
        "clusters": len(clusters),
        "clustered_items": clustered,
        "clustered_pct": round(clustered / len(nodes), 3),
        "clusters_with_hard_evidence": len(hard),
        "items_in_hard_clusters": sum(c["size"] for c in hard),
        "text_only_clusters": len(textonly),
        "items_in_text_only_clusters": sum(c["size"] for c in textonly),
        "largest_cluster": clusters[0]["size"] if clusters else 0,
        "clusters_2": sum(1 for c in clusters if c["size"] == 2),
        "clusters_3_5": sum(1 for c in clusters if 3 <= c["size"] <= 5),
        "clusters_6plus": sum(1 for c in clusters if c["size"] >= 6),
        "collapsible_surplus": clustered - len(clusters),
    },
    "clusters": clusters,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=1))

print(json.dumps(report["stats"], indent=1))
print("\n--- top clusters ---")
for c in clusters[:12]:
    print(f"\n#{c['representative']} · {c['size']} items ({c['issues']}i/{c['prs']}p) · "
          f"{c['distinct_authors']} authors ({c['distinct_low_smell_authors']} low-smell) · {c['edge_kinds']}")
    for m in c["members"][:6]:
        print(f"   {m['type'][:1]}{m['n']:>6} smell{m['smell']} {m['author'][:16]:16} {m['title'][:88]}")
    if c["size"] > 6:
        print(f"   … {c['size']-6} more")
