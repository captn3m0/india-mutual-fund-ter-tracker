#!/usr/bin/env bash
# Creates GitHub releases for backfilled tags, oldest first. Push the tags before running.
set -euo pipefail

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

/bin/git log --reverse --format=%H --grep='^Backfilled from the AMFI TER export' -- data.csv |
  while read -r sha; do
    tag=$(/bin/git tag --points-at "$sha" 'v*' | head -1)
    [ -n "$tag" ] || { echo "No tag for $sha" >&2; exit 1; }
    if gh release view "$tag" >/dev/null 2>&1; then
      echo "Skipping $tag, release exists"
      continue
    fi
    /bin/git show "$sha:data.csv" > "$tmp/data.csv"
    changelog=$(/bin/git log -1 --format=%B "$sha" | grep '^- "' || true)
    if [ -n "$changelog" ]; then
      printf 'Total Expense Ratio Changes (Direct Plans):\n\n%s\n' "$changelog" > "$tmp/notes.md"
    else
      echo 'No TER changes in any Direct Plans' > "$tmp/notes.md"
    fi
    gh release create "$tag" --verify-tag --latest=false --notes-file "$tmp/notes.md" "$tmp/data.csv"
    sleep 3
  done
