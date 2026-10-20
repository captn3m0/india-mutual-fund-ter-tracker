"""
One-off backfill of the daily data.csv commits that were
missed while the scraper was broken. Replays the AMFI
monthly TER exports day by day, and commits each change
with the same authorship, message and tags as the workflow.

Usage: uv run python -m scripts.backfill CACHE_DIR START END
"""

import io
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone

import requests

from src import FINAL_HEADERS, PLANS, fetch_ter_xlsx, generate_diff, parse_ter, read_ter_rows, write_csv

V1_FIELDS = [
    "Base TER (%)",
    "Additional expense as per Regulation 52(6A)(b) (%)",
    "Additional expense as per Regulation 52(6A)(c) (%)",
    "GST (%)",
    "Total TER (%)",
]
V1_HEADERS = ["Scheme Name"] + [f"{plan} - {field}" for plan in PLANS for field in V1_FIELDS]
V2_START = date(2026, 4, 1)
COMMIT_TIME = time(6, 5, tzinfo=timezone.utc)
IST = timezone(timedelta(hours=5, minutes=30))
BOT = "github-actions[bot]"
GIT_ENV = {
    "GIT_AUTHOR_NAME": BOT,
    "GIT_AUTHOR_EMAIL": "github-actions[bot]@users.noreply.github.com",
    "GIT_COMMITTER_NAME": BOT,
    "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
}
GIT = ["/bin/git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
FILENAME = "data.csv"


def headers_for(day):
    return FINAL_HEADERS if day >= V2_START else V1_HEADERS


def month_start(day):
    return day.replace(day=1)


def prev_month_start(day):
    return month_start(month_start(day) - timedelta(days=1))


def load_month(session, cache_dir, month):
    path = os.path.join(cache_dir, f"{month:%Y-%m}.xlsx")
    if not os.path.exists(path):
        print(f"Downloading {month:%m-%Y}", file=sys.stderr)
        with open(path + ".tmp", "wb") as f:
            f.write(fetch_ter_xlsx(session, month))
        os.rename(path + ".tmp", path)
    with open(path, "rb") as f:
        if month >= V2_START:
            return list(read_ter_rows(f.read()))
        headers = ["Scheme Name", "TER Date"] + V1_HEADERS[1:]
        return [[None] + row for row in read_ter_rows(f.read(), headers)]


"""
Yields (day, rows) snapshots that mirror what the scraper
would have seen: the latest row per scheme from the previous
and current month, never mixing the v1 and v2 schemas.
"""


def snapshots(months, start, end):
    day = start
    while day <= end:
        window = [m for m in (prev_month_start(day), month_start(day)) if (m >= V2_START) == (day >= V2_START)]
        rows = [r for m in window for r in months[m] if r[2].date() <= day]
        data = sorted((row[1:] for row in parse_ter(rows).values()), key=lambda row: (row[1].lower(), row[0] or ""))
        yield day, data if day >= V2_START else [row[1:] for row in data]
        day += timedelta(days=1)


def git(*args, env=None, stdin=None):
    return subprocess.run(
        GIT + list(args), check=True, text=True, input=stdin, capture_output=True, env={**os.environ, **(env or {})}
    ).stdout


def commit(day, changelog):
    stamp = datetime.combine(day, COMMIT_TIME)
    tag = f"v{2 if day >= V2_START else 1}.{stamp.astimezone(IST):%Y%j}.{stamp.astimezone(IST).hour}"
    env = {**GIT_ENV, "GIT_AUTHOR_DATE": stamp.isoformat(), "GIT_COMMITTER_DATE": stamp.isoformat()}
    message = (
        "Update Total Expense Ratios\n\n"
        f"Backfilled from the AMFI TER export for {day:%Y-%m-%d}.\n\n"
        f"Changes in TER (Direct Plans):\n\n{changelog}"
    )
    git("add", FILENAME)
    git("commit", "-q", "--no-verify", "-F", "-", env=env, stdin=message)
    git("tag", "-a", "-m", tag, tag, env=env)
    return tag


def main(cache_dir, start, end):
    if git("status", "--porcelain", "--untracked-files=no").strip():
        sys.exit("Working tree is dirty")
    os.makedirs(cache_dir, exist_ok=True)
    session = requests.Session()
    months, month = {}, prev_month_start(start)
    while month <= end:
        months[month] = load_month(session, cache_dir, month)
        month = month_start(month + timedelta(days=32))
    previous = os.path.join(cache_dir, "previous.csv")
    for day, data in snapshots(months, start, end):
        with open(FILENAME, encoding="utf-8") as f:
            old = f.read()
        write_csv(FILENAME, data, headers_for(day))
        with open(FILENAME, encoding="utf-8") as f:
            if f.read() == old:
                continue
        with open(previous, "w", encoding="utf-8") as f:
            f.write(old)
        out = io.StringIO()
        generate_diff(previous, FILENAME, out)
        tag = commit(day, out.getvalue())
        print(f"{day} {tag} {len(data)} schemes, {out.getvalue().count(chr(10))} TER changes", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
