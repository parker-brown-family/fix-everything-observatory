# Handoff — observatory instrument + ALLOCATE AGENT (2026-09-07)

## Status
Landed and pushed. Public repo `parker-brown-family/fix-everything-observatory`,
branch `main`, my last commit `989db67`, 0 ahead/behind origin. **A concurrent
session has uncommitted prompt-review work** in the same worktree (`app/swarm.html`,
`observatory.py`, `.gitignore`, `README.md` show as modified — attribution
glossing, issue-vs-PR job kinds, `agent-report-*.md`). That is NOT mine; leave it.

## What's done (my commits, oldest→newest)
- **Motion knob** (`69cb77c`) — speed knob now scales the swarm's own animation, not the replay ramp. Verified: motion tracks knob 0.1/0.5/1/4×; 0px phase-jump on mid-flight change.
- **Walk the whole repo + stop inventing zeros** (`f2fc1c5`) — miner follows GitHub Link cursors to the end (8887 artifacts / 19801 comments / 14753 events); window stats render `—` past the fetched horizon; distilled cache (~14MB not ~150); slice-can't-clobber-a-walk guard; sprite atlas + lane dedupe + memoized filters. Verified in-browser + `mined …` log lines.
- **Media-player transport** (`6db1a29`) — ⏮ ▶ ⏭, playback-rate ladder (0.25–4×, separate from MOTION), weekday-led clock + day counter, filling scrubber, event sparks on cursor-crossing (teleports >60d don't spark). Verified: rates 1.9/7.4/29.7 days/s; clean console.
- **Rename reconciliation** (`20bd4a3` carried it) — everything is `observatory` now; killed the stale `fix-tracker-sni.py` chip (pid 1057597) pointing at the deleted old path and relaunched the current applet.
- **ALLOCATE AGENT** (`20bd4a3`) — inspector button on open tickets POSTs `/api/allocate` (X-Fix-Observatory header gates cross-origin) → server writes a ticket-primed prompt and spawns `claude`. Local-instance only (page checks hostname). Verified 403/409/200 + correct prompt for #8758.
- **Clean-env spawn** (`989db67`) — `clean_agent_env()` strips `CLAUDE_CODE_*`/`CLAUDECODE`/`ANTHROPIC_MODEL*` so the agent is a clean TOP-LEVEL claude, not a transcript-off child. Verified: child sees 0 CLAUDE_CODE markers.

Plus a global (non-repo) fix: `~/.claude/settings.json` `modelOverrides: {"default":"claude-opus-5"}` so old CC builds stop rejecting the `default` alias.

## How to run / verify
```
bin/fix-everything-observatory open      # ensure tokened server + open the swarm
bin/fix-everything-observatory status
```
Server is currently UP (tokened, `exhaustive`, poll=900s) at http://127.0.0.1:4517/app/swarm.html. First cold mine ~13 min; borrows the gh token via the launcher.

## Not done / next
- **#3** seed manifest for instant first-load (fresh clone is empty ~13 min).
- **#4** ALLOCATE AGENT should preflight the spawned `claude` version + warn if outdated (the v2.1.251 model failure Parker hit).
- **#5** WebGL mote layer for locked 60fps (canvas 2D ~40fps at 3400 live motes).
- Minor (not filed): page fetches JetBrains Mono from Google Fonts — not truly offline.

## Watch out
- **Shared worktree** — a concurrent session's uncommitted work is present. Do not `git add -A`, stash, or checkout.
- Never launch the server from inside a claude session for production; the launcher/tray does it clean. The code now scrubs markers regardless, but the belt matters.
- Don't hardcode a model in any spawn — inherit the user's (portability).

## Where it's recorded
APES episode: **none — repo not APES-registered** (gap flagged). lean-ctx:
`ctx_session decision` (resume breadcrumb). file-memory:
`~/.claude/projects/-home-parker-Work-fix-everything-tracker/memory/` →
`observatory-project.md`, `observatory-model-alias-and-portability.md`. Harvest:
`handoffs/c4443a40-5739-4d5d-985b-e93ee5cd3fa1.cdx`. Follow-ups: issues #3–#5
(`follow-up` label → ~/FOLLOWUPS.md).
