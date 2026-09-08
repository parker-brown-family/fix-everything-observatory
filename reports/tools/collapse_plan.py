#!/usr/bin/env python3
"""Read the collapse map; run the agent-inflation invalidation test; draft collapse comments.

Nothing here posts anything. The comments are drafts on disk for review.
"""
import json, pathlib, collections

MAP = pathlib.Path("/home/parker/Work/fix-everything-observatory/reports/2026-09-07-collapse-map.json")
PLAN = pathlib.Path("/home/parker/Work/fix-everything-observatory/reports/2026-09-07-collapse-plan.md")
rep = json.loads(MAP.read_text())
cl = rep["clusters"]

# ---- invalidation test: does the picture change once agent-smelling reporters are removed? ----
def human_only(c):
    return [m for m in c["members"] if m["smell"] < 2]

with_agents = sorted(cl, key=lambda c: -c["size"])[:20]
without = sorted(cl, key=lambda c: -len(human_only(c)))[:20]
top_with = [c["representative"] for c in with_agents]
top_without = [c["representative"] for c in without]
overlap = len(set(top_with) & set(top_without))

# how much of the collapse survives a two-distinct-humans requirement?
strict = [c for c in cl if len({m["author"] for m in human_only(c)}) >= 2]
strict_items = sum(c["size"] for c in strict)

# who authors the clustered mass
authors = collections.Counter(m["author"] for c in cl for m in c["members"])
smelly_items = sum(1 for c in cl for m in c["members"] if m["smell"] >= 2)

test = {
    "top20_overlap_with_and_without_agent_authors": f"{overlap}/20",
    "clusters_total": len(cl),
    "clusters_with_2plus_distinct_human_reporters": len(strict),
    "items_in_those_clusters": strict_items,
    "collapsible_surplus_strict": strict_items - len(strict),
    "clustered_items_authored_by_agent_smelling": smelly_items,
    "busiest_author_in_clustered_mass": authors.most_common(3),
}
print(json.dumps(test, indent=1))

# ---- the plan ----
lines = ["# Collapse plan — omacom/omarchy open queue",
         "",
         f"Generated {rep['generated']} from {rep['stats']['nodes']} sampled open items "
         f"({rep['method']['nodes']}).",
         "",
         "Nothing in this file has been posted anywhere. Each entry is a candidate collapse:",
         "one surface, several tickets, and the evidence that binds them.",
         "",
         f"- clusters: **{rep['stats']['clusters']}**",
         f"- items inside a cluster: **{rep['stats']['clustered_items']}** of {rep['stats']['nodes']} "
         f"({rep['stats']['clustered_pct']:.0%})",
         f"- redundant items the collapse would remove: **{rep['stats']['collapsible_surplus']}**",
         f"- clusters with two or more distinct low-smell reporters: **{len(strict)}** "
         f"(surplus {test['collapsible_surplus_strict']})",
         "",
         "## The twenty biggest candidates",
         ""]

for c in sorted(cl, key=lambda c: -c["size"])[:20]:
    rep_n = c["representative"]
    head = next(m for m in c["members"] if m["n"] == rep_n)
    kinds = ", ".join(f"{k}×{v}" for k, v in sorted(c["edge_kinds"].items(), key=lambda kv: -kv[1]))
    lines += [f"### {head['title']}",
              "",
              f"**{c['size']} items** ({c['issues']} issues, {c['prs']} PRs) · "
              f"{c['distinct_authors']} authors, {c['distinct_low_smell_authors']} low-smell · "
              f"edges: {kinds} · median similarity {c['median_edge_similarity']}",
              "",
              f"Anchor: #{rep_n} (oldest). Members:",
              ""]
    for m in c["members"]:
        tag = "PR " if m["type"] == "pr" else "iss"
        smell = f" ·smell{m['smell']}" if m["smell"] else ""
        lines.append(f"- {tag} #{m['n']} — {m['title']} — @{m['author']}{smell}")
    lines += ["",
              "> Draft comment (not posted):",
              ">",
              f"> These look like one surface. #{rep_n} is the oldest report; "
              f"{c['size'] - 1} other open items describe the same failure "
              f"({', '.join('#' + str(m['n']) for m in c['members'] if m['n'] != rep_n)}). "
              f"Evidence: {kinds}. Proposing they collapse onto #{rep_n}, with the strongest patch "
              f"kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.",
              ""]

lines += ["## Invalidation test",
          "",
          "The brief promised this check: compute the ranking with and without agent-smelling",
          "reporters, and if the top twenty is the same list either way, agent inflation is not",
          "material and the identity-dedupe can be dropped.",
          "",
          f"- overlap of the top twenty, with and without agent authors: **{overlap}/20**",
          f"- clustered items authored by something that smells agentic: **{smelly_items}** "
          f"of {rep['stats']['clustered_items']}",
          f"- clusters surviving a two-distinct-human-reporters requirement: **{len(strict)}** "
          f"of {len(cl)}",
          ""]

PLAN.write_text("\n".join(lines))
print(f"\nwrote {PLAN} ({len(lines)} lines)")
