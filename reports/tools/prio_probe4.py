#!/usr/bin/env python3
"""Arrival vs drain rate, weekly, for issues and PRs. Search issueCount only (cheap)."""
import json, subprocess, datetime

GH = "/home/parker/bin/gh"
R = "omacom/omarchy"

def count(q):
    o = subprocess.run([GH, "api", "-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=1",
                        "--jq", ".total_count"], capture_output=True, text=True)
    return int(o.stdout.strip()) if o.returncode == 0 and o.stdout.strip() else None

weeks = []
end = datetime.date(2026, 9, 7)
for i in range(6):
    b = end - datetime.timedelta(days=7 * (i + 1))
    e = end - datetime.timedelta(days=7 * i)
    weeks.append((b.isoformat(), e.isoformat()))

rows = []
for b, e in weeks:
    rows.append({
        "week": f"{b}..{e}",
        "issues_opened": count(f"repo:{R} is:issue created:{b}..{e}"),
        "issues_closed": count(f"repo:{R} is:issue closed:{b}..{e}"),
        "prs_opened": count(f"repo:{R} is:pr created:{b}..{e}"),
        "prs_merged": count(f"repo:{R} is:pr merged:{b}..{e}"),
        "prs_closed": count(f"repo:{R} is:pr closed:{b}..{e}"),
    })

extra = {
    "open_issues_no_comment": count(f"repo:{R} is:issue is:open comments:0"),
    "open_issues_reactions_ge3": count(f"repo:{R} is:issue is:open reactions:>=3"),
    "open_issues_linked_pr": count(f"repo:{R} is:issue is:open linked:pr"),
    "open_issues_labelled_bug": count(f"repo:{R} is:issue is:open label:bug"),
    "open_issues_older_90d": count(f"repo:{R} is:issue is:open created:<2026-06-09"),
    "open_prs_older_30d": count(f"repo:{R} is:pr is:open created:<2026-08-08"),
    "open_prs_draft": count(f"repo:{R} is:pr is:open is:draft"),
    "open_issues_dhh_commented": count(f"repo:{R} is:issue is:open commenter:dhh"),
    "open_prs_dhh_commented": count(f"repo:{R} is:pr is:open commenter:dhh"),
}
print(json.dumps({"weekly": rows, "snapshot": extra}, indent=1))
