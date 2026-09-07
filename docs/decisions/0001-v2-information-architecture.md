# 0001 — V2 information architecture: instrument, not feature pile

Date: 2026-09-07 · Status: accepted · Input: docs/research/2026-09-07-visualizer-research.md

Parker's brief: treat this as a startup product, fully polished; must scrub,
pause, show per-ticket history, and show comments arriving in real time.
Decisions were made autonomously (Parker AFK); alternatives are recorded so
any of these can be re-litigated cheaply.

## D1 — Three synchronized bands; the CFD is the analytic backbone
Swarm (hero, identity) on top; a thin event lane; a cumulative flow diagram
at the bottom (bands: merged / closed / still-open, stacked over time).
CFD chosen because its geometry natively answers the swarm-scale triple:
band width = volume, vertical gap = WIP, horizontal gap = lead time.
*Rejected:* separate births/settles bar chart (v1) — two encodings for what
one geometry shows; kept only as the red/green weekly pulse inside the lane.

## D2 — The ticket story is the product feature
Click any mote (or feed row) → the right rail becomes an inspector: one
chronological story — opened → labeled → commented → closed → reopened →
merged — built by joining the issues, comments, and events feeds client-side.
*Rejected:* per-ticket API fetch on click (clean data, but burns the rate
budget and dies offline; the joined feeds already cover the fetched horizon).

## D3 — One event grammar for live and replay
A feed lane shows comments/state-changes as they happen (live poll) AND as
the scrub cursor crosses them (replay). Same rows, same pings on the swarm.
*Rejected:* separate "live ticker" and "replay annotations" — two systems to
polish, and users would learn two grammars for one idea.

## D4 — Budget-honest mining with ETags
Miner adds repo-wide comments + issue-events feeds (2 pages each unauth).
All requests conditional (If-None-Match); 304s are free against the GitHub
rate limit, so a 300s cycle is safe unauthenticated. Guard: if remaining
budget < 8, skip the cycle and say so in the manifest; the rail displays the
API budget. Token raises pages (10/3/3) automatically.
*Rejected:* websockets/webhooks (needs a registered app or repo rights we
don't have; polling with ETags reaches "feels live" at zero infrastructure).

## D5 — Age becomes a chart, not a vibe
The swarm's orbit-radius-by-age gains labeled reference rings (1d / 1w / 1m).
This is the aging-WIP chart folded into the hero view.

## D6 — Default scope is ALL ARTIFACTS
The wild still has zero marker-attributed tickets; a product that opens on an
empty screen is dead on arrival. Marker scope stays one click away with its
honest zero + explanation; attribution counts stay on the rail permanently.
*Rejected:* marker-first default (v1) — right doctrine, wrong first frame.

## D7 — The official mark everywhere
The omarchy glyph is U+E900 in /usr/share/fonts/omarchy/omarchy.ttf; the
v1 hand-drawn spiral was wrong. Rendered from the font at 256px: page brand,
favicon, tray icon, desktop icon. The spiral SVG stays in-tree as history.

## D8 — Reopens are measured-within-window
The events feed gives real closed/reopened/merged events inside the fetched
horizon. Labels say "in window"; absence outside the window stays unknown,
never zero (house rule: unknown is not zero).

## D9 — Single file, no build, stdlib only — unchanged
The page must lift onto wecanfixeverything.com by copying two files (page +
manifest). Every dependency added is a deployment negotiation later.
