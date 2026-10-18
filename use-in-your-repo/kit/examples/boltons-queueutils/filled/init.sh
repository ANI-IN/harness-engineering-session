#!/usr/bin/env bash
# init.sh for boltons-queueutils: reach a known state, then run one basic end-to-end test.
#
#   bash init.sh          imports, then the queueutils tests and doctest
set -euo pipefail
cd "$(dirname "$0")"

echo "== imports: the three modules load"
python -c "import boltons.typeutils, boltons.listutils, boltons.queueutils"

echo "== basic end-to-end test: queueutils, stop at the first failure (full suite: see AGENTS.md)"
python -m pytest --doctest-modules boltons/queueutils.py tests/test_queueutils.py -x -q \
  --no-header -p no:cacheprovider
