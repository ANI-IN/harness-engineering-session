"""Readable feature names: one alias per dataset feature, accepted by every command in place of
the code (case-insensitive) and normalised to the code; the dataset and exports keep the code."""

from __future__ import annotations

import json

import pytest

from shipharness.ab.commands import FEATURES_FILE
from shipharness.datasets.names import (
    EXTRA_ALIASES,
    FEATURE_ALIASES,
    FEATURE_NAMES,
    FILTER_NAMES,
    RULE_NAMES,
    SECTION_NAMES,
    UnknownFeature,
    assignment_label,
    feature_code,
    feature_label,
    feature_short,
    filter_label,
    rule_label,
    rule_short,
    section_label,
    valid_feature_names,
)

EXPECTED = {
    "F1": "org-search",
    "F2": "comments",
    "F3": "safe-retries",
    "F4": "version-checks",
    "F5": "bulk-close",
    "F6": "watchers",
    "F7": "labels",
}


def _dataset_features() -> set[str]:
    ids = set()
    for line in FEATURES_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["inputs"]["feature_id"])
    return ids


def test_every_dataset_feature_has_exactly_one_alias() -> None:
    # Control tasks (C1-C8) are not course features: they keep their code and have no alias.
    features = {code for code in _dataset_features() if code.startswith("F")}
    assert features == set(FEATURE_ALIASES)
    aliases = list(FEATURE_ALIASES.values())
    assert len(aliases) == len(set(aliases))  # one feature per alias
    assert FEATURE_ALIASES == EXPECTED


@pytest.mark.parametrize(("name", "code"), [*((a, c) for c, a in EXPECTED.items())])
def test_an_alias_normalises_to_its_code(name: str, code: str) -> None:
    assert feature_code(name) == code
    assert feature_code(name.upper()) == code
    assert feature_code(f" {name.title()} ") == code


def test_the_old_feature_3_alias_still_works() -> None:
    assert EXTRA_ALIASES == {"idempotent-create": "F3"}
    assert feature_code("idempotent-create") == "F3"
    assert feature_code("Safe-Retries") == "F3"
    assert feature_code("F3") == "F3"


def test_codes_still_work_in_any_case() -> None:
    assert feature_code("F4") == "F4"
    assert feature_code("f4") == "F4"
    assert feature_code("C3") == "C3"  # control tasks keep their code


def test_an_unknown_name_lists_the_valid_names_and_codes() -> None:
    with pytest.raises(UnknownFeature) as caught:
        feature_code("versions")
    message = str(caught.value)
    assert "'versions'" in message
    for code, alias in EXPECTED.items():
        assert f"{alias} ({code})" in message
    assert valid_feature_names() in message


def test_the_label_is_kind_number_and_exact_name() -> None:
    assert feature_label("F4") == "Feature 4: Version checks on issue edits"
    assert feature_label("F1") == "Feature 1: Org-wide issue search"
    assert feature_label("F3") == "Feature 3: Safe retries for issue creation"
    assert feature_short("F4") == "Feature 4"
    assert feature_label("C2") == "C2"  # a control task: the code alone
    assert feature_label("F-07") == "F-07"
    assert feature_short("C2") == "C2"


def test_the_owner_names_for_rules_sections_assignments_and_filters() -> None:
    assert FEATURE_NAMES["F5"] == "Bulk close"
    assert RULE_NAMES == {
        "R1": "Tenant isolation",
        "R2": "Roles",
        "R3": "API conventions",
        "R4": "Safe retries",
        "R5": "Audit log",
        "R6": "Layering",
        "R7": "Migrations",
        "R8": "Deleted issues stay hidden",
    }
    assert rule_label("R1") == "House rule 1: Tenant isolation"
    assert rule_short("R4") == "House rule 4"
    assert rule_label("regression") == "regression"  # not a house rule: unchanged
    assert SECTION_NAMES[2] == "State and sessions"
    assert section_label(1) == "Section 1: Instructions"
    assert section_label("S3") == "Section 3: Scope and sandbox"
    assert assignment_label(4) == "Assignment 4: Verification"
    assert FILTER_NAMES[3] == "Adds coverage or catches a mutant"
    assert filter_label(1) == "Filter 1: Builds and collects"
    assert filter_label(6) == "Filter 6: No duplicate tests"
