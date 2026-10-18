"""Names of check parameters (`CheckContext.params`, runner `--params`).

The referee and the verify gate build params with these names; the checks read them. One module so a
rename on either side cannot silently drop an input.
"""

from __future__ import annotations

ADAPTER = "adapter"
ALLOWED_PATHS = "allowed_paths"  # {"build": [globs], "test": [globs]}
ARTIFACTS_DIR = "artifacts_dir"
BOARD_MODE = "board_mode"
CHANGED_FILES = "changed_files"  # files in the shipped diff
DIFF_PATH = "diff_path"  # alternative to CHANGED_FILES: a unified diff file
EXEMPTIONS = "exemptions"  # {"R4": ["POST /path", ...]}
FLAKY_RUNS = "flaky_runs"
HARNESS_ARTIFACTS = "harness_artifacts"  # globs of harness-owned files
HIDDEN_TESTS = "hidden_tests"  # pytest node ids, relative to the build
MIGRATIONS_DIR = "migrations_dir"
PHASE_FILES = "phase_files"  # {"test": [files changed during the test phase]}
R3_MAX_EXAMPLES = "r3_max_examples"
REGRESSION_EXPECTED = "regression_expected"  # node ids that existed at the checkpoint
REGRESSION_TARGETS = "regression_targets"  # pytest targets for existing tests
RUN_ID = "run_id"  # the scored run, when the run log holds several (A/B)
RUN_LOG = "run_log"
SESSION_PATCHES = "session_patches"  # one diff file per session, in order
SHIPPED_TESTS = "shipped_tests"  # node ids of tests the arm shipped
TEST_GLOBS = "test_globs"

ALL_NAMES = (
    ADAPTER,
    ALLOWED_PATHS,
    ARTIFACTS_DIR,
    BOARD_MODE,
    CHANGED_FILES,
    DIFF_PATH,
    EXEMPTIONS,
    FLAKY_RUNS,
    HARNESS_ARTIFACTS,
    HIDDEN_TESTS,
    MIGRATIONS_DIR,
    PHASE_FILES,
    R3_MAX_EXAMPLES,
    REGRESSION_EXPECTED,
    REGRESSION_TARGETS,
    RUN_ID,
    RUN_LOG,
    SESSION_PATCHES,
    SHIPPED_TESTS,
    TEST_GLOBS,
)
