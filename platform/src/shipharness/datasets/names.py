"""The course's names for features, house rules, sections, assignments, and test filters.

Each feature in `teamtrack-features-v1` has one command alias (`version-checks` for F4). Commands
and make targets accept the alias or the code, in any case, and normalise it to the code with
`feature_code`; the dataset, scores, and exports keep the code. Terminal and console output name a
feature, rule, section, or filter as "<Kind> N: <name>" (`feature_label`, `rule_label`, ...):
"Feature 4: Version checks on issue edits", "House rule 1: Tenant isolation". Referee checks with
a code name read "<name> (<code>)" (`referee_check_label`): "Flaky tests (flakiness)".
"""

from __future__ import annotations

import re

FEATURE_ALIASES: dict[str, str] = {
    "F1": "org-search",
    "F2": "comments",
    "F3": "safe-retries",
    "F4": "version-checks",
    "F5": "bulk-close",
    "F6": "watchers",
    "F7": "labels",
}
# Earlier aliases that still work.
EXTRA_ALIASES: dict[str, str] = {"idempotent-create": "F3"}
FEATURE_NAMES: dict[str, str] = {
    "F1": "Org-wide issue search",
    "F2": "Comments on issues",
    "F3": "Safe retries for issue creation",
    "F4": "Version checks on issue edits",
    "F5": "Bulk close",
    "F6": "Watchers",
    "F7": "Labels",
}
RULE_NAMES: dict[str, str] = {
    "R1": "Tenant isolation",
    "R2": "Roles",
    "R3": "API conventions",
    "R4": "Safe retries",
    "R5": "Audit log",
    "R6": "Layering",
    "R7": "Migrations",
    "R8": "Deleted issues stay hidden",
}
SECTION_NAMES: dict[int, str] = {
    1: "Instructions",
    2: "State and sessions",
    3: "Scope and sandbox",
    4: "Verification",
}
# Assignment N belongs to Section N and carries its name.
ASSIGNMENT_NAMES: dict[int, str] = dict(SECTION_NAMES)
FILTER_NAMES: dict[int, str] = {
    1: "Builds and collects",
    2: "Passes five runs",
    3: "Adds coverage or catches a mutant",
    4: "Real assertions",
    5: "No source changes",
    6: "No duplicate tests",
}
# Referee checks whose machine names are not words people read; shown as "<name> (<code>)".
REFEREE_CHECK_NAMES: dict[str, str] = {
    "regression": "Existing tests",
    "diff_scope": "Files outside the allowed paths",
    "flakiness": "Flaky tests",
    "continuity": "Session continuity",
}
# Other names the same checks go by: gate items (`checkrun.CHECK_LABELS`), finding rules
# (`Finding.rule`), and the runner's progress labels.
REFEREE_CHECK_ALIASES: dict[str, str] = {
    "existing tests": "regression",
    "diff scope": "diff_scope",
    "scope": "diff_scope",
    "flaky": "flakiness",
}
_BY_ALIAS = {alias: code for code, alias in FEATURE_ALIASES.items()} | EXTRA_ALIASES
_CODE = re.compile(r"[A-Za-z][0-9]+")


class UnknownFeature(ValueError):
    """A feature name that is neither an alias nor a code."""


def valid_feature_names() -> str:
    """'org-search (F1), comments (F2), ...': every alias with its code."""
    return ", ".join(f"{alias} ({code})" for code, alias in FEATURE_ALIASES.items())


def feature_code(name: str) -> str:
    """The code for an alias or a code, in any case: `Version-Checks` and `f4` give `F4`. A code
    the dataset lacks passes through (the task lookup reports it); anything else is refused."""
    text = name.strip()
    if text.lower() in _BY_ALIAS:
        return _BY_ALIAS[text.lower()]
    if _CODE.fullmatch(text):
        return text.upper()
    raise UnknownFeature(
        f"unknown feature {name!r}: use a name or its code: {valid_feature_names()}"
    )


def plain_name(code: str) -> str | None:
    """'Version checks on issue edits' for F4; None for a code that is not a course feature
    (control tasks)."""
    return FEATURE_NAMES.get(code)


def _number(code: str | int) -> int:
    return code if isinstance(code, int) else int(str(code).lstrip("SAFRsafr"))


def feature_short(code: str) -> str:
    """'Feature 4' for F4; the code alone for a control task."""
    return f"Feature {code[1:]}" if code in FEATURE_NAMES else code


def feature_label(code: str) -> str:
    """'Feature 4: Version checks on issue edits'; the code alone for a control task."""
    name = FEATURE_NAMES.get(code)
    return f"{feature_short(code)}: {name}" if name else code


def rule_short(code: str) -> str:
    """'House rule 1' for R1; anything else (regression, hidden, scope) unchanged."""
    return f"House rule {code[1:]}" if code in RULE_NAMES else code


def rule_label(code: str) -> str:
    """'House rule 1: Tenant isolation' for R1; anything else unchanged."""
    name = RULE_NAMES.get(code)
    return f"{rule_short(code)}: {name}" if name else code


def referee_check_code(name: str) -> str | None:
    """'diff_scope' for diff_scope, 'diff scope', or 'scope'; None for any other name."""
    code = REFEREE_CHECK_ALIASES.get(name, name)
    return code if code in REFEREE_CHECK_NAMES else None


def referee_check_label(name: str) -> str:
    """'Files outside the allowed paths (diff_scope)' for diff_scope (or a name it goes by);
    any other name unchanged."""
    code = referee_check_code(name)
    return f"{REFEREE_CHECK_NAMES[code]} ({code})" if code else name


def section_label(section: int | str) -> str:
    """'Section 2: State and sessions' for 2 or "S2"."""
    number = _number(section)
    return f"Section {number}: {SECTION_NAMES[number]}"


def assignment_label(assignment: int | str) -> str:
    """'Assignment 4: Verification' for 4 or "A4"."""
    number = _number(assignment)
    return f"Assignment {number}: {ASSIGNMENT_NAMES[number]}"


def filter_label(number: int) -> str:
    """'Filter 2: Passes five runs' for 2."""
    return f"Filter {number}: {FILTER_NAMES[number]}"
