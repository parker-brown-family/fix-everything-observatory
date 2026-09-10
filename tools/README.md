# find-duplicates

The same work, filed more than once, in a flooded issue queue.

```
python3 find-duplicates.py omacom/omarchy
```

One file, standard library only, `gh` for the API. Read-only: it never mutates
anything, and `--commands` prints commands for you to read rather than running them.

## What it is for

A queue that arrives faster than it drains stops being a prioritisation problem and
becomes a discovery problem. The expensive thing is no longer deciding what to do
about a report — it is finding out that five people already sent the same patch.

On `omacom/omarchy`, reading the entire open queue on 2026-09-08:

| | |
|---|---|
| **3,477** open items examined | none missed: 0 not reached |
| **2,212** distinct pieces of work | the rest are the same work, filed again |
| **756** duplicate items in 316 groups | the largest is 16 items from 15 people, all for one inverted boolean |
| **298** apply cleanly and close an issue | and duplicate nothing else in the queue |
| **317** no longer apply to the base | they cannot merge as they stand |
| **123** arrived after a fix for the same surface closed | plus 61 filed before one, which are the fair ones to close |
| **3** carry an approving review | out of 1,977 open pull requests |

The last two rows are what the run is for. The Codex usage collector was fixed for
codex-cli 0.149 and merged on 25 August; the CLI moved to 0.150, the collector still
hardcodes an `--ask-for-approval` value it rejects, and ten open items now say so —
the most recent filed the day before this run. No merged pull request has ever
mentioned that flag. The queue was too loud to say it.

## What it prints

- **Arrived after you closed something on this surface.** Either a fix did not reach
  people or a neighbouring case is being read as the same one. Never safe to close,
  so no command is generated for anything in this section.
- **Filed before that fix landed.** Plausibly superseded, and the fair ones to close.
- **Applies cleanly, closes an issue, duplicates nothing.** Sorted smallest first.
- **The same work, filed more than once.** Each group names the patch worth reading
  and what closes when it merges, plus the runner-up if you disagree.
- **Real, reported repeatedly, nothing mergeable yet.** A surface with no candidate:
  every patch for it is a draft, conflicting, or has changes requested.

`--html` writes a page you can send someone. `--json` writes everything, including
every group's evidence, for tooling.

## How a group is formed

Five kinds of evidence, kept apart on purpose so you can reject a group at a glance:

| | |
|---|---|
| `closes` | a pull request's `closingIssuesReferences`. Ground truth |
| `refs` | a patch naming at most three issues in its body: authorial intent |
| `text` | cosine over tf-idf of title (×3) and the first 1,500 characters of body, ≥ 0.55 |
| `files` | two patches touching the same file, where at most five patches touch it, and the pair shares two such files |
| `mentions` | any other `#1234`. The weakest, and never enough on its own |

A patch that closes or names an issue merges on its own. Everything else must also
clear a topical floor of 0.22 cosine before it may merge anything, and an item with
more than six merging edges is treated as a bridge: it joins its single strongest
neighbour instead of fusing every group it touches.

Those two rules exist because the first version did not have them. It reported one
group of 1,025 items — half the sample — after shared files chained a keyboard
backlight bug to a locale bug in the clock, through eight hops of nothing. The
number was enormous and meant nothing.

## What it cannot know

**A group is a surface, not a diagnosis.** Two reports about the same file and the
same symptom land together even when the causes differ. Checked by hand on this
data: one group paired a merged fix for FPC fingerprint readers with open reports
about Broadcom ControlVault readers — the same subsystem, the same file, a different
device. Right to look at together, wrong to close as duplicates.

That is why nothing is closed for you, why the only generated commands are for items
filed before the fix they match, and why every group prints what formed it.

**It reads the whole queue, and says so when it cannot.** GitHub's search stops at
1,000 results per query, which is fewer than omarchy has open. Where the queue is
larger, the fetch splits by creation date and halves any window that comes back full,
so no query hits the ceiling — 3,477 of 3,477 items on this run. When something is
genuinely out of reach the report counts it as unexamined rather than quietly
counting it as distinct, because unexamined is not unique.

**It does not judge people.** There is no contributor score. The only author
statistic is how many distinct people reported a surface, which is a fact about the
bug.

**Check state is read, not assumed.** Where a repository has no automated checks
configured — `omacom/omarchy` has none on any of the 1,000 pull requests examined —
the report says so, and "applies cleanly" never gets rendered as "works".

## Choosing which patch to keep

Ineligible outright: drafts, conflicting branches, failing checks, and anything with
changes requested. Among the rest, the score prefers a patch that closes the group's
own issues, has an approving review, comes from someone who has landed a patch here
before, touches tests, and stays focused; it penalises a diff over 400 lines. Ties
break toward the oldest, because first-to-file is what a maintainer would do and it
cannot be gamed by rewriting a description.

Raw review counts are deliberately not scored. On omarchy 206 open pull requests
carry a "review" and nearly all are an automated pass, several of which say they
could not review the patch. Only a decision by someone with standing counts.

## Tests

```
python3 find-duplicates-test.py
```

Twenty assertions against a fixture with known-correct answers: that three differently
worded reports of one bug group together, that a neighbouring surface stays separate,
that a patch and the issue it closes is not called duplication, that a draft and a
changes-requested patch never become the recommendation, and that no generated command
is anything but a close.
