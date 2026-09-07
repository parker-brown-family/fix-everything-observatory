# fix-everything-tracker

The instrument panel for [wecanfixeverything.com](https://wecanfixeverything.com/):
a live, scrubbable visualizer of the Omarchy repair swarm. It watches the
`omacom/omarchy` repo heal itself — tickets and PRs, the disposable agents that
open them, and the comments and state-changes that move them — on the swarm
scale Parker cares about: **volume**, **lifespan**, **closeability**, and which
work **smells agentic**.

> Agents are disposable ships. Issues and comments are the civilization.
> The repository is the planet. This is the observatory.

Click the Omarchy chip in the bar tray → the swarm opens.

## What it shows

- **The swarm** — every open ticket orbits the repo hive; orbit radius = age
  (labelled 1 day / 1 week / 1 month rings). Circles are issues, diamonds are
  PRs. Colour is attribution: **cyan** = carries the fix-event marker, **violet**
  = smells agentic, **yellow** = one weak signal, **ghost** = no signal. Reopened
  tickets wear a red ring.
- **Stats bar** — OPEN NOW · OPENED · SETTLED · MERGED · REOPENED ·
  AGENT-SMELLING · MARKER · COMMENTS, all tracking the scrub cursor and
  animating during replay.
- **Event lane + live feed** — comments and state-changes as ticks on a
  timeline and as a live feed that surfaces the newest activity; each feed row
  clicks through to the ticket. In live mode it shows "N ago"; while scrubbing
  it shows the event's own time.
- **Cumulative flow diagram** — stacked merged / closed / still-open bands over
  time. The vertical gap is work-in-progress; the horizontal gap is lead time.
  This is the "is the system healing" picture.
- **The ticket story** — click any mote (or feed row) and the right rail becomes
  an inspector: the whole chronological story — opened → labelled → commented →
  closed → reopened → merged — joined from the issues, comments, and events
  feeds, with real comment snippets and a GitHub link.
- **Replay** — `space` plays the whole history from the beginning; the scrubber
  and dragging the flow area move the cursor by hand; `←/→` step a day.
- **Simulation** — `l` toggles a watermarked synthetic 180-day healing arc, for
  demoing the shape before the wild data is rich.

## Agent smell

GitHub gives a comment an id and an author but no agent/session identity, so
attribution is ours. The miner scores named, explainable signals per artifact
and ships the evidence, so the inspector can say *why* something smells:

| signal | weight | matches |
|---|---|---|
| ai-trailer | 2 | "Generated with Claude Code/Copilot/Codex…", Co-Authored-By AI, 🤖 |
| agent-phrase | 2 | "this PR was created automatically / by an agent…" |
| claude-template | 2 | the `## Summary … ## Test plan` PR body shape |
| bot-author | 2 | `[bot]` accounts / GitHub `type: Bot` |
| conventional-title | 1 | `fix:`/`feat:` prefix on a long descriptive title |
| error-fingerprint | 1 | fenced traceback + `Fixes #N` |
| emoji-title | 1 | emoji-led title |

Attribution taxonomy: **marker** (definitive) → **smell** (score ≥ 2) →
**hint** (score 1) → **none**. A missing smell means "no signal matched",
never "human-confirmed".

## Parts

| Path | What |
|---|---|
| `tracker.py` | Miner + server. Conditional (ETag) GitHub API calls: issues/PRs, repo-wide comments, repo-wide events. Scores smell, writes `data/manifest.{json,js}`, serves the app. Stdlib only. Skips a cycle below 8 API requests remaining. |
| `app/swarm.html` | The visualizer — single self-contained file, no build, so it lifts onto the site by copying it + the manifest. |
| `tray/fix-tracker-sni.py` | SNI StatusNotifierItem applet — the Omarchy chip in the quickshell bar tray; any click opens the swarm. Pure Gio, no appindicator. |
| `tray/render-icons.sh` | Renders the icons from the official Omarchy glyph (U+E900 in the `omarchy` font) — reproducible, pixel-faithful to the bar mark. |
| `bin/fix-everything-tracker` | Entrypoint: `open · mine · serve · tray · status · install`. |
| `contract/omarchy-fix-event-v1.md` | The event-marker pattern that makes a ticket definitively attributable to the one-click fixer. |
| `docs/` | Research notes, decision records (0001 IA, 0002 smell + stats), QA pass. |

## Run

```
bin/fix-everything-tracker open      # ensure server, open the swarm
bin/fix-everything-tracker install   # icons + desktop entry + start the tray
bin/fix-everything-tracker status    # is it up? recent log
```

Pin the tray icon so it's always visible (not in the hover drawer): in
`~/.config/omarchy/shell.json`, the `omarchy.tray` entry under `bar.layout.right`:

```
{ "id": "omarchy.tray", "pinned": ["fix-everything-tracker"] }
```

Autostart on login (add to hyprland config by hand — config writes flash the
CRT banner on this box):

```
exec-once = /home/parker/Work/fix-everything-tracker/bin/fix-everything-tracker tray
```

Env: `FIX_TRACKER_REPO` (default `omacom/omarchy`), `FIX_TRACKER_PORT` (4517),
`FIX_TRACKER_PAGES`, `FIX_TRACKER_INTERVAL` (300s), `GITHUB_TOKEN` (raises the
fetch horizon 3→10 pages and the rate budget).

## Toward wecanfixeverything.com

`app/swarm.html` has no build step and one data dependency (`data/manifest.js`).
Hosting on the site is: run the miner anywhere, publish the manifest next to the
page. The moment the one-click fixer stamps the `omarchy-fix-event:v1` marker,
MARKER scope stops being empty and the swarm becomes the site's live pulse.

Design decisions and the field research behind them are in `docs/decisions/` and
`docs/research/`.
