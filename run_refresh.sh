#!/bin/bash
# Local refresh runner — primary mechanism, same reasoning as daily-check's
# run_refresh.sh: GitHub Actions' own schedule: cron proved unreliable
# (documented, hit repeatedly). Today (Aug 28) is the actual Rakhi day, so
# this needs to be reliable right now.
set -euo pipefail
cd "$(dirname "$0")"

source "$HOME/.config/curefoods-clickhouse.env"

python3 -m build.build_data

git add data.json data-*.json index.html
if git diff --staged --quiet; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') no data changes, skipping commit"
  exit 0
fi
git commit -q -m "Local refresh $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git pull --rebase --autostash -q origin main
git push -q
echo "$(date '+%Y-%m-%d %H:%M:%S') pushed data refresh"
