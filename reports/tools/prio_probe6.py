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
 "open_issues_no_label": f"repo:{R} is:issue is:open no:label",
 "open_issues_last7d": f"repo:{R} is:issue is:open created:>=2026-08-31",
 "open_issues_last7d_bug": f"repo:{R} is:issue is:open created:>=2026-08-31 label:bug",
 "open_issues_older30d_bug": f"repo:{R} is:issue is:open created:<2026-08-08 label:bug",
 "open_issues_older30d": f"repo:{R} is:issue is:open created:<2026-08-08",
 "open_prs_review_none": f"repo:{R} is:pr is:open review:none",
 "open_prs_review_approved": f"repo:{R} is:pr is:open review:approved",
 "open_prs_no_comment": f"repo:{R} is:pr is:open comments:0",
 "open_issues_reactions_ge10": f"repo:{R} is:issue is:open reactions:>=10",
 "open_issues_lockscreen": f"repo:{R} is:issue is:open \"lock screen\" in:title",
}
out = {}
for k, q in qs.items():
    out[k] = count(q)
    time.sleep(2.5)
print(json.dumps(out, indent=1))
