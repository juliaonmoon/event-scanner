#!/bin/bash
# Daily event-scanner update, run via cron on the VPS.
set -e
cd /opt/event_scanner/repo
export GIT_SSH_COMMAND='ssh -F /opt/event_scanner/.ssh/config'

git fetch origin main
git checkout main
git reset --hard origin/main

python3 update.py

git config user.name "event-scanner-vps"
git config user.email "vps@juliaonmoon.local"
git add opportunities.json index.html
if ! git diff --staged --quiet; then
  git commit -m "Daily scan $(date -u '+%Y-%m-%d %H:%M UTC') (VPS)"
  git push origin main
  git push origin HEAD:master --force
fi
