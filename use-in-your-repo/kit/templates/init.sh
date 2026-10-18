#!/usr/bin/env bash
# REPLACE: TeamTrack's init.sh as the harness writes it for Feature 1. Keep its two jobs: reach a known state, then run one basic end-to-end test. Run it before you commit.
# init.sh for Feature 1: Org-wide issue search, written by the harness initializer step.
# It runs a basic end-to-end test before you implement the feature, and can start the
# development server.
#
#   bash init.sh          scratch database at head, then a basic end-to-end test
#   bash init.sh serve    the same, then the development server in the background
set -euo pipefail
cd "$(dirname "$0")"

# A scratch database outside the repository, so setup leaves no files to commit.
# REPLACE: the environment your app needs for a scratch run (TeamTrack: a seeded SQLite file in /tmp).
export TEAMTRACK_DATABASE_URL="sqlite:////tmp/teamtrack-dev.db"
export TEAMTRACK_SEED=true

# REPLACE: your setup step (TeamTrack: Alembic shows one head, then upgrades an empty database). Delete it if you have no database.
echo "== migrations (exactly one head, House rule 7: Migrations)"
python -m alembic heads
python -m alembic upgrade head

# REPLACE: one fast test that proves the app works end to end, stopping at the first failure.
echo "== basic end-to-end test: issues, stop at the first failure (full suite: run_visible_tests)"
python -m pytest tests/visible/test_issues.py -x -q --no-header -p no:cacheprovider

# REPLACE: how to start your development server, or delete this block.
if [ "${1:-}" = "serve" ]; then
  echo "== development server on http://127.0.0.1:8000 (log in /tmp/teamtrack-dev.log)"
  nohup python -m uvicorn app.main:create_app --factory --port 8000 \
    >/tmp/teamtrack-dev.log 2>&1 &
  echo "server pid $!"
fi
