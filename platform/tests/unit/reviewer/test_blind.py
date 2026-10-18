from __future__ import annotations

from shipharness.reviewer.blind import blind

HARNESS_DIFF = """From 1234567890abcdef1234567890abcdef12345678 Mon Sep 17 00:00:00 2001
From: agent <agent@sandbox.invalid>
Date: Fri, 16 Oct 2026 10:00:00 +0000
Subject: [PATCH] F1 done, see progress.md

diff --git a/AGENTS.md b/AGENTS.md
index 1111111..2222222 100644
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1 +1 @@
-# Map
+# Map v2
diff --git a/app/api/issues.py b/app/api/issues.py
index 3333333..4444444 100644
--- a/app/api/issues.py
+++ b/app/api/issues.py
@@ -10,2 +10,3 @@ def list_issues():
     rows = repo.list(org_id)
+    # cursor pagination
     return rows
diff --git a/progress.md b/progress.md
index 5555555..6666666 100644
--- a/progress.md
+++ b/progress.md
@@ -1 +1,2 @@
 # Progress
+- harness arm worked on F1
diff --git a/.agents/skills/add-endpoint/SKILL.md b/.agents/skills/add-endpoint/SKILL.md
new file mode 100644
--- /dev/null
+++ b/.agents/skills/add-endpoint/SKILL.md
@@ -0,0 +1 @@
+---
diff --git a/docs/exec-plans/active/F1.md b/docs/exec-plans/active/F1.md
--- a/docs/exec-plans/active/F1.md
+++ b/docs/exec-plans/active/F1.md
@@ -1 +1 @@
-x
+y
diff --git a/feature_list.json b/feature_list.json
--- a/feature_list.json
+++ b/feature_list.json
@@ -1 +1 @@
-{}
+{"a": 1}
diff --git a/session-handoff.md b/session-handoff.md
--- a/session-handoff.md
+++ b/session-handoff.md
@@ -1 +1 @@
-a
+b
diff --git a/init.sh b/init.sh
--- a/init.sh
+++ b/init.sh
@@ -1 +1 @@
-a
+b
"""

BARE_DIFF = """diff --git a/app/api/issues.py b/app/api/issues.py
index 7777777..8888888 100644
--- a/app/api/issues.py
+++ b/app/api/issues.py
@@ -10,2 +10,3 @@ def list_issues():
     rows = repo.list(org_id)
+    # cursor pagination
     return rows
"""


def test_two_arms_with_the_same_code_change_blind_to_the_same_text() -> None:
    assert blind(HARNESS_DIFF) == blind(BARE_DIFF)


def test_harness_artifacts_and_commit_metadata_are_removed() -> None:
    text = blind(HARNESS_DIFF)
    for word in (
        "AGENTS.md",
        "progress.md",
        "session-handoff.md",
        "feature_list.json",
        "init.sh",
        ".agents/",
        "exec-plans",
        "Subject:",
        "From:",
        "Date:",
        "harness arm",
    ):
        assert word not in text
    assert "app/api/issues.py" in text and "+    # cursor pagination" in text


def test_index_lines_with_blob_hashes_are_removed() -> None:
    assert "index " not in blind(BARE_DIFF)


def test_workspace_paths_and_run_ids_are_normalised() -> None:
    diff = BARE_DIFF.replace(
        "# cursor pagination",
        "# built in /tmp/shipharness-ws/ab-20261016-100000-abc123/harness/ws"
        " by r-20261016-100000-def456",
    )
    text = blind(diff)
    assert "shipharness-ws" not in text
    assert "/harness/ws" not in text
    assert "ab-20261016" not in text and "r-20261016" not in text
    assert "<workspace>" in text and "<id>" in text


def test_windows_workspace_paths_are_normalised() -> None:
    diff = BARE_DIFF.replace(
        "# cursor pagination", r"# C:\Users\x\AppData\Local\Temp\shipharness-ws\ab-1\bare\ws\app"
    )
    text = blind(diff)
    assert "bare" not in text and "<workspace>" in text


def test_bytes_input_and_empty_diff() -> None:
    assert blind(BARE_DIFF.encode()) == blind(BARE_DIFF)
    assert blind("") == ""
