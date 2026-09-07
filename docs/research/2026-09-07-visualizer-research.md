# Research notes — repair-swarm visualizer field scan (2026-09-07)

Scope: what existing repo/agent visualizers do well, what chart forms fit
"lifespan / volume / closeability", and which interaction patterns make a live
instrument feel finished. Feeds decision record 0001.

## What the field does

**Gource-family repo animators** (gource.io, navid-m/rush, CodeFlower,
pomber/git-history): the enduring lesson is *legible motion* — actors visibly
travel to the thing they change, and history replays as animation rather than
as a table. Weakness for our case: they visualize the file tree, not the
issue/PR lifecycle, and none has an analytic layer (no durations, no rates).

**Agent-observability dashboards 2026** (Arize/Langfuse/AgentOps class,
CrewAI swarm dashboards, swarm-ai.org): converged on three panes — a live
event stream, a trajectory/graph view, and per-run drill-down. The drill-down
("click any run, see its whole story") is the feature users describe as the
product. Weakness: uniformly generic BI aesthetics; nothing identity-driven.

**Flow analytics** (cumulative flow diagrams, aging-WIP charts, Planview/
Kanban literature): the CFD is the canonical "is the system healing" picture —
stacked bands of state over time where *vertical gap = WIP* and *horizontal
gap = lead time*. It answers volume + closeability + lifespan in one geometry,
which is exactly Parker's swarm-scale triple. Aging-WIP charts answer "what's
been open too long" — our orbit-radius-as-age already encodes this; it needs
labeled reference rings to become readable rather than decorative.

**Timeline scrubbing** (streaming-viz patents, Animate/ChartBlender papers):
the standard is video-transport grammar — scrub + play/pause + a cursor that
lives *inside* the chart, not only in a footer slider. Events must surface at
the cursor as it passes (they call this event surfacing; we call it comments
coming up in real time).

## Implications adopted (see decision 0001)

1. CFD replaces the bare sediment strip as the analytic backbone; sediment
   texture stays inside the closed band (identity + geometry, not either/or).
2. Per-ticket drill-down ("the story of #N") is the product feature, not a
   tooltip nicety.
3. A live event feed (comments + state changes) runs in both wall-clock mode
   and replay mode — same lane, same grammar.
4. Age rings with labels (1d / 1w / 1m) turn the swarm's radius into a chart.
5. Keep the identity skin (Tokyo Night, diff motif, omarchy mark) — the field
   is aesthetically generic; identity is our differentiation.
6. Budget honesty stays a feature: fog for the unfetched, API budget on the
   rail, unknown never rendered as zero.

## Sources

- https://gource.io/
- https://github.com/navid-m/rush
- https://livablesoftware.com/tools-to-visualize-the-history-of-a-git-repository/
- https://arize.com/blog/best-ai-observability-tools-for-autonomous-agents-in-2026/
- https://github.com/Smilkoski/agent-swarm-dashboard
- https://www.swarm-ai.org/dashboard/
- https://www.planview.com/resources/articles/cumulative-flow-diagram/
- https://docondev.com/blog/2025/1/10/making-the-flow-of-work-visible-with-cumulative-flow-diagrams
- https://business.adobe.com/blog/basics/cumulative-flow
