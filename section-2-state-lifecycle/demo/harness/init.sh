#!/usr/bin/env bash
# init.sh for Feature 2: Comments on issues, written by the harness initializer step.
# It runs a basic end-to-end test before you implement the feature, and can start the
# development server.
#
#   bash init.sh          scratch database at head, then a basic end-to-end test
#   bash init.sh serve    the same, then the development server in the background
set -euo pipefail
cd "$(dirname "$0")"

# A scratch database outside the repository, so setup leaves no files to commit.
export TEAMTRACK_DATABASE_URL="sqlite:////tmp/teamtrack-dev.db"
export TEAMTRACK_SEED=true

echo "== migrations (exactly one head, House rule 7: Migrations)"
python -m alembic heads
python -m alembic upgrade head

echo "== basic end-to-end test: issues, stop at the first failure (full suite: run_visible_tests)"
python -m pytest tests/visible/test_issues.py -x -q --no-header -p no:cacheprovider

if [ "${1:-}" = "serve" ]; then
  echo "== development server on http://127.0.0.1:8000 (log in /tmp/teamtrack-dev.log)"
  nohup python -m uvicorn app.main:create_app --factory --port 8000 \
    >/tmp/teamtrack-dev.log 2>&1 &
  echo "server pid $!"
fi
