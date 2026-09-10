# 0003 — The plugin channel is a clone, so tracked means shipped

Date: 2026-09-10 · Status: accepted · Source: issue #17, confirmed rather than invalidated

`omarchy plugin add` runs a plain `git clone` — no `--depth`, no `--filter`, no
sparse checkout (`/usr/share/omarchy/bin/omarchy-plugin-add:120`). Every tracked
file, and the whole history, lands in
`~/.local/share/omarchy/plugins/brownfamilysports.observatory`. Measured on a
fresh clone, 2026-09-10: **8.2 MB** — a 5.2 MB working tree plus 3.1 MB of
`.git`. The runtime the plugin actually needs is 1.5 MB of that, most of it the
seed.

`reports/` alone was 2.6 MB: larger than everything required to run the thing.

This is the same argument that untracked `handoffs/` in `92cf491`. It was not
extended past that directory at the time, and the gap cost something real — two
of the shipped documents described a capability in the present tense that had
been removed four commits earlier, to the marketplace reviewer auditing the
repository. Three of the shipped mockups fetched a web font from Google's CDN
while the README promised `api.github.com` and nothing else.

## The test

**Does a person who installed the plugin need this file?** Not "is it good
work" — the untracked material is the better half of the thinking. It stays on
disk and in history; it stops arriving uninvited on other people's machines.

## What stops shipping

| Path | Bytes | Why it goes |
|---|---:|---|
| `reports/` (23 files) | 2,671,624 | Instrument output about somebody else's repository, its intermediates, three design mockups, six priority probes, and an unsent draft note. None of it runs. |
| `docs/2026-09-07-omarchy-packaging.html` | 105,287 | Rendered brief for a packaging plan that is parked. |
| `docs/body.html` | 55,153 | The same brief again, as an extracted fragment. |
| `tools/reel/` (13 files) | 122,880 | The pipeline that cuts a demo clip of the observatory for a phone. Committed on 2026-09-09 under "get the repo up to date"; it fails the same test as everything above, and its two detached-child `Popen` calls broke the repository's own spawn gate the moment it became tracked. Reversed here. |

The worklist and the duplicate map are the strongest single argument for
untracking rather than the weakest. They name 3,477 tickets belonging to several
hundred people and carry our verdicts on them, measured as right about half the
time on the duplicate bands. That is a working note. It is not something to place
on a stranger's disk because they installed a status bar widget.

`reports/2026-09-08-note-for-the-maintainer.md` settles the "published on
purpose" question by itself: its first line reads *NOT SENT*.

## What keeps shipping, and why

- `seed/` (1.2 MB) — deliberate. The instrument opens full instead of empty.
- `preview.png` (620 KB) — the marketplace listing renders it.
- `tools/` (204 KB) — `find-duplicates.py` is publicly linked from
  omacom/omarchy#11192 and from an X post. Untracking it breaks a live link.
- `docs/decisions/`, `docs/research/`, `docs/2026-09-07-qa-pass.md` — the README
  sends readers here by name.

## What this does not fix, and why that is fine

Untracking does not shrink `.git`. A clone is full, so the history comes with it.
Measured 2026-09-10, by blob, across every reachable object:

| In history | Bytes |
|---|---:|
| Files still tracked today — `seed/manifest.js.gz`, `preview.png`, and successive versions of `app/swarm.html`, `observatory.py`, `README.md` | 3,264,863 |
| Gone from HEAD, reachable only in history | 1,841,360 |

So **two thirds of `.git` is the history of files we ship on purpose**, and a
rewrite recovers 1.8 MB at most. Against that: every existing clone breaks, every
commit link dies — including the ones in the closing comment on issue #17 and in
this file — and a public repository under marketplace review gets force-pushed.
Declined on the numbers rather than skipped.

The visible tree is the part a reviewer reads, and the part that misled one. That
is now clean, and `bin/verify` keeps it that way.

Future reports and briefs are ignored by default, the way handoffs are. Anything
meant to ship gets added deliberately with `git add -f`, and that decision gets a
line in this file.
