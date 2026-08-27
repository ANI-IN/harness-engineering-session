"""Negative proof that the shellcheck gate can fail.

CI always installs shellcheck; locally the tests skip if it is absent
(make doctor reports that separately).
"""

import shutil
import subprocess

import pytest

needs_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None, reason="shellcheck not installed"
)


@needs_shellcheck
def test_shellcheck_fails_on_violation(tmp_path):
    bad = tmp_path / "verify.sh"
    bad.write_text('#!/usr/bin/env bash\necho $1\n', encoding="utf-8")  # SC2086
    proc = subprocess.run(["shellcheck", str(bad)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "SC2086" in proc.stdout


@needs_shellcheck
def test_shellcheck_passes_clean_script(tmp_path):
    good = tmp_path / "verify.sh"
    good.write_text('#!/usr/bin/env bash\necho "$1"\n', encoding="utf-8")
    proc = subprocess.run(["shellcheck", str(good)], capture_output=True, text=True)
    assert proc.returncode == 0
