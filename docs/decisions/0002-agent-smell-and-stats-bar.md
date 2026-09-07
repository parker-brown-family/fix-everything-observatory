# 0002 — Agent smell is a scored, explainable signal; stats bar up top

Date: 2026-09-07 · Status: accepted · Source: Parker (mid-hunt message)

Parker: tickets opened by agents have a *smell* in the title or description —
make those visually distinct; and add a stats bar (opened / closed / etc).

## Agent smell

The miner scores named signals per artifact and ships the evidence, so the UI
can say *why* something smells rather than just tinting it:

| signal | weight | what it matches |
|---|---|---|
| ai-trailer | 2 | "Generated with Claude Code / Copilot / Codex…", Co-Authored-By AI identities, 🤖 trailers |
| agent-phrase | 2 | "this PR was created automatically / by an agent…" |
| claude-template | 2 | the `## Summary … ## Test plan` PR body shape |
| bot-author | 2 | `[bot]` accounts, GitHub `type: Bot` |
| conventional-title | 1 | `fix:`/`feat:`-style prefix on a long descriptive title |
| error-fingerprint | 1 | fenced traceback/panic + `Fixes #N` |
| emoji-title | 1 | emoji-led title |

Attribution taxonomy becomes: **marker** (the fix-event stamp, definitive,
cyan) → **smell** (score ≥ 2, violet) → **hint** (score 1, yellow) → **none**
(ghost). Violet is reassigned from "agents disagree" (unused) to "smells
agentic" — the natural AI hue in Tokyo Night.

The signals are heuristics and say so: the inspector lists them per ticket,
and the rail keeps marker/smell/hint/none counts side by side. A missing
smell means "no signal matched", never "human-confirmed".

## Stats bar

A counters strip under the header: OPEN NOW · OPENED (window) · CLOSED ·
MERGED · REOPENED · AGENT-SMELLING · COMMENTS. Values track the scrub time T,
so replaying history animates the counters. Window-clipped numbers are
labeled with the window, per the unknown-is-not-zero rule.

## Default scope

Scopes cycle ALL → AGENTIC (marker+smell+hint) → MARKER ONLY; default ALL
(decision 0001 D6 stands; AGENTIC is the new second stop since it is the
view Parker actually wants to stare at).
