# Omarchy one-click fixer event contract

The one-click error action creates an issue and, when an agent is summoned, a pull request. Both bodies carry the same fenced marker. Agents are disposable; the event and its GitHub artifacts persist.

```text
<!-- omarchy-fix-event:v1
source: one-click-error-fixer
event_id: 01J...
error_fingerprint: sha256:...
observed_at: 2026-09-07T19:42:11Z
repo: omacom/omarchy
repo_revision: <full git sha or null>
component: <path or null>
agent_backend: claude|codex|opencode|pi|gemini|copilot|other
agent_session: <ephemeral local trace or null>
evidence: <url to redacted log/screenshot or null>
-->
```

Required fields are `source`, `event_id`, `error_fingerprint`, and `observed_at`. Values that were not measured stay `null`; they are never replaced with zero, an empty string, or a guessed identity.

Recommended labels (an index, not truth): `origin:agent`, `intake:one-click`, and `lifecycle:triage|active|merged|closed|reopened`.

The PR body should also contain `Fixes #<issue-number>`. The miner joins issue → PR → commits → checks → comments and records every observed state transition with its timestamp. A missing marker means “unattributed,” not “human.”
