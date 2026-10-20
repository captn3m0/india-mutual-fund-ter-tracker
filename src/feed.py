import json
import os
import re
import subprocess
import sys

CHANGE_RE = re.compile(r'^- "(.+)" (lowered|increased) its TER from ([\d.]+) to ([\d.]+)$')
TAG_RE = re.compile(r"tag: (v[\d.]+)")
REPO_URL = "https://github.com/captn3m0/india-mutual-fund-ter-tracker"
OUTPUT = "site/_data/changes.json"
MAX_ENTRIES = 100

"""
Parses the changelog lines that the update workflow
writes into commit messages for data.csv, and returns
one entry per commit that changed a Direct Plan TER.
"""


def parse_log(log):
    for commit in log.split("\x1e"):
        if not commit.strip():
            continue
        sha, timestamp, refs, body = commit.strip().split("\x00", 3)
        changes = []
        for line in body.splitlines():
            m = CHANGE_RE.match(line.strip())
            if m:
                scheme, verb, old, new = m.groups()
                changes.append({"scheme": scheme, "old": old, "new": new, "direction": verb})
        if not changes:
            continue
        tag = TAG_RE.search(refs)
        yield {
            "id": sha,
            "date": timestamp,
            "tag": tag.group(1) if tag else None,
            "url": f"{REPO_URL}/releases/tag/{tag.group(1)}" if tag else f"{REPO_URL}/commit/{sha}",
            "changes": changes,
        }


def git_log():
    return subprocess.run(
        ["git", "log", "--format=%H%x00%aI%x00%D%x00%B%x1e", "--", ":/data.csv"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


if __name__ == "__main__":
    entries = list(parse_log(git_log()))[:MAX_ENTRIES]
    output = sys.argv[1] if len(sys.argv) > 1 else OUTPUT
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1)
    print(f"Wrote {len(entries)} entries to {output}", file=sys.stderr)
