#!/usr/bin/env python3
import json, subprocess, time
GH = "/home/parker/bin/gh"; R = "omacom/omarchy"

def count(q, tries=3):
    for _ in range(tries):
        o = subprocess.run([GH, "api", "-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=1",
                            "--jq", ".total_count"], capture_output=True, text=True)
        if o.returncode == 0 and o.stdout.strip():
            return int(o.stdout.strip())
        time.sleep(20)
    return None

qs = {
 "open_issues_no_comment": f"repo:{R} is:issue is:open comments:0",
 "open_issues_reactions_ge3": f"repo:{R} is:issue is:open reactions:>=3",
 "open_issues_linked_pr": f"repo:{R} is:issue is:open linked:pr",
 "open_issues_labelled_bug": f"repo:{R} is:issue is:open label:bug",
 "open_issues_older_90d": f"repo:{R} is:issue is:open created:<2026-06-09",
 "open_prs_older_30d": f"repo:{R} is:pr is:open created:<2026-08-08",
 "open_prs_draft": f"repo:{R} is:pr is:open draft:true",
 "open_issues_dhh_commented": f"repo:{R} is:issue is:open commenter:dhh",
 "open_prs_dhh_commented": f"repo:{R} is:pr is:open commenter:dhh",
 "open_prs_linked_issue": f"repo:{R} is:pr is:open linked:issue",
 "closed_issues_completed_7d": f"repo:{R} is:issue is:closed reason:completed closed:>=2026-08-31",
 "closed_issues_notplanned_7d": f"repo:{R} is:issue is:closed reason:\"not planned\" closed:>=2026-08-31",
}
out = {}
for k, q in qs.items():
    out[k] = count(q)
    time.sleep(2.5)
print(json.dumps(out, indent=1))
