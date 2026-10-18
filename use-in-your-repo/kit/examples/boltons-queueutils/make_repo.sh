#!/usr/bin/env bash
# Build the starting repository of the worked example in use-in-your-repo/apply-to-your-repo.md: three boltons
# modules (typeutils, listutils, queueutils) and their tests, copied from the pinned boltons clone
# (tag 26.2.0, BSD-3-Clause license) that platform/scripts/fetch_testgen_libs.py fetches.
#
#   uv run python platform/scripts/fetch_testgen_libs.py boltons
#   bash use-in-your-repo/kit/examples/boltons-queueutils/make_repo.sh /tmp/bq-example
set -euo pipefail

target="${1:?usage: make_repo.sh <new directory>}"
here="$(cd "$(dirname "$0")" && pwd)"
clone="$here/../../../../.shipharness/libs/boltons/src"

if [ ! -f "$clone/boltons/queueutils.py" ]; then
  echo "ERROR boltons clone not found at $clone: run uv run python platform/scripts/fetch_testgen_libs.py boltons"
  exit 1
fi
if [ -e "$target" ]; then
  echo "ERROR $target already exists: pick a new directory"
  exit 1
fi

mkdir -p "$target/boltons" "$target/tests"
cp "$clone/LICENSE" "$clone/.gitignore" "$target/"
for f in __init__.py typeutils.py listutils.py queueutils.py; do
  cp "$clone/boltons/$f" "$target/boltons/"
done
for f in __init__.py conftest.py test_typeutils.py test_listutils.py test_queueutils.py; do
  cp "$clone/tests/$f" "$target/tests/"
done

cd "$target"
git init -q -b main
git add -A
git -c user.name=example -c user.email=example@example.invalid commit -q \
  -m "boltons 26.2.0 (4332b35): typeutils, listutils, queueutils and their tests"
echo "created $target from boltons $(git -C "$clone" rev-parse --short HEAD)"
git ls-files
