# Handoff — observatory rename + allocation-prompt review (2026-09-07)

## Status
Landed and pushed. `main` = `20bd4a3`, in sync with origin. Rename commit is `e383374`; `20bd4a3` (one-click ALLOCATE AGENT) came from a concurrent session and sits on top — both survived.

## What's done
- Full rename `fix-everything-tracker` → `fix-everything-observatory`: GitHub repo (old URL redirects), remote URL (`github-bfs` alias), directory, `bin/` entrypoint, `observatory.py`, `tray/fix-observatory-sni.py`, page header, `FIX_OBSERVATORY_*` env knobs, `X-Fix-Observatory` header (client+server together), User-Agent, D-Bus name, log paths. Verified: zero "tracker" occurrences, `py_compile` + `bash -n` clean, server started from the new path and served `swarm.html` HTTP 200, then stopped (was down before).
- External surfaces renamed: desktop entry, hicolor icon, `shell.json` tray pin. Claude project memory copied to the new path key.
- Reviewed `agent_prompt()` (observatory.py:468): PR tickets get a failure-diagnosis job, no report destination, no live-Omarchy machine context, cryptic attribution field, unignored `data/agent-prompt-*.md`. Fix sketched in-session, NOT applied.

## How to run/verify
```
bin/fix-everything-observatory status
bin/fix-everything-observatory open
```

## Not done / next
- Land the prompt-template fix — the falsifiable spec and sketch are in the repo's issue #1 (PR/issue branch, report destination, attribution legend, gitignore line).
- Attribution unknown-vs-none collapse (`swarm.html:278`, prompt interpolation) — issue #2.

## Watch out
- Sessions/lean-ctx anchored pre-rename point at the dead path; relaunch from this dir. Old memory dir at the `-tracker` path key is a stale duplicate.
- Repo is not APES-registered; `agent-orient-boot` resolves nothing here.
- `FIX_TRACKER_*` env vars and `X-Fix-Tracker` are gone with no shims — nothing external shipped under them.

## Where it's recorded
Session harvest: `handoffs/dc79a65b-….cdx` (7 facts; cdx-audit: clean). Memory: `~/.claude/projects/-home-parker-Work-fix-everything-observatory/memory/rename-and-external-surfaces.md`. Issues: #1, #2 (both `follow-up`-labelled, in `~/FOLLOWUPS.md`). No APES episode — repo unregistered. lean-ctx promotion skipped — mis-rooted this session.
