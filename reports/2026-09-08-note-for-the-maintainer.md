# Draft note to the omarchy maintainers — NOT SENT

Nothing in this file has been posted anywhere. It exists so the decision to send it,
or not to, is Parker's and is made against the actual words.

The rule this sits under: nothing goes to `omacom/omarchy` without an explicit,
per-batch go-ahead. See the consent-gate issue in this repo.

---

## The note

> **Subject:** the Codex limits collector is broken again, and ten open items say so
>
> #7649 fixed the usage collector for codex-cli 0.149 and merged on 25 August. The
> CLI moved on, and the collector still hardcodes an `--ask-for-approval` value that
> 0.150 and 0.151 reject, so the widget reads "Codex limits unavailable" again.
>
> Ten open items describe it: #7825, #8460, #8656, #8721, #8849, #8868, #8971,
> #8977, #9247, #10727 — the last filed yesterday. Two of them are patches. No
> merged pull request has ever mentioned `ask-for-approval`, so nothing on main
> addresses the flag itself. The original report, #7781, was closed on 22 August
> without a fix, and #8398 was reopened by its author for the same reason.
>
> I found it by grouping the open queue on evidence — what a patch says it closes,
> what its body names, which files it touches, how the text agrees — rather than by
> keyword. The script is a single standard-library Python file, read-only, and
> prints commands rather than running them: <link>
>
> Run over all 3,457 open items it also says: N distinct pieces of work, 208 patches
> that apply cleanly and close an issue and duplicate nothing else, and 93 that no
> longer apply to main.
>
> Nothing has been posted to the repository and nothing needs a reply. If the
> grouping is useful I am happy to keep it running; if not, ignore this.

## Why it is shaped like that

**The finding leads, not the tool.** A maintainer under a flood has no reason to
read a pitch. They have every reason to read "a bug you closed is still happening".

**It is verifiable in one click.** Every claim points at a numbered item they can
open. If the Codex claim is wrong, thirty seconds proves it and the rest can be
discarded.

**There is no ask.** No request to merge, adopt, install, or reply. An unsolicited
message to somebody with 1,967 open pull requests should cost them nothing.

**It does not mention duplicates first.** "You have 413 duplicates" sounds like a
criticism of their triage. "Your fix did not reach nine people" is a fact about the
software.

## How the claim was checked

Three independent angles, all on 2026-09-07:

1. **The grouping** put nine open items around the closed #7781 on evidence.
2. **The timeline** on #7781 shows it closed as completed by its own reporter, with
   no closing pull request.
3. **A direct search**, not using the grouping at all: two merged pull requests have
   ever touched the collector (#6780, #7649, the latter on 25 August), and **zero**
   merged pull requests mention `ask-for-approval`. Ten open items match
   `"Codex limits" in:title`.

The third check is the one that matters, because it could have killed the claim and
did not.

## What must be true before it is sent

1. The Codex claim re-verified on the day of sending — a closed issue can be reopened
   and a bug can be fixed between now and then.
2. The link points at something readable: the tool and its README, not a raw repo
   directory.
3. Sent once, to one place, by a person. Not as an issue on their tracker, not as a
   comment on nine tickets, not from an automated account.
