#!/usr/bin/env bash
# Prefixes every release body with "# YYYY-MM-DD", the IST date in its vN.YYYYDDD.k tag. Safe to re-run.
set -euo pipefail

export tmp
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/notes"
jobs=${JOBS:-8}

latest=$(gh api 'repos/{owner}/{repo}/releases/latest' --jq .tag_name)
gh api --paginate 'repos/{owner}/{repo}/releases?per_page=100' \
  --jq '.[] | [.tag_name, (.body // "" | @base64)] | @tsv' > "$tmp/releases.tsv"

while IFS=$'\t' read -r tag body; do
  if ! [[ "$tag" =~ ^v[0-9]+\.([0-9]{4})([0-9]{1,3})\.[0-9]+$ ]]; then
    echo "Skipping $tag, unknown tag format" >&2
    continue
  fi
  day=$(date -u -d "${BASH_REMATCH[1]}-01-01 +$((10#${BASH_REMATCH[2]} - 1)) days" +%F)
  notes=$(base64 -d <<< "$body")
  [[ "$notes" == "# $day"* ]] && continue
  printf '# %s\n%s\n' "$day" "$notes" > "$tmp/notes/$tag.md"
done < "$tmp/releases.tsv"
echo "$(wc -l < "$tmp/releases.tsv") releases, $(ls "$tmp/notes" | wc -l) to edit with $jobs jobs, latest is $latest"

edit() {
  for attempt in 1 2 3 4 5; do
    gh release edit "$1" --notes-file "$tmp/notes/$1.md" >/dev/null && { echo "$1"; return; }
    [ "$attempt" -lt 5 ] || return 1
    echo "Edit of $1 failed, retrying in $((attempt * 60))s" >&2
    sleep $((attempt * 60))
  done
}
export -f edit

status=0
ls "$tmp/notes" | sed 's/\.md$//' | xargs -P "$jobs" -I{} bash -c 'edit "$1"' _ {} || status=$?

if [ "$(gh api 'repos/{owner}/{repo}/releases/latest' --jq .tag_name)" != "$latest" ]; then
  gh release edit "$latest" --latest >/dev/null
fi
exit "$status"
