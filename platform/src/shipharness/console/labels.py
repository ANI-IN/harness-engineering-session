"""How the console and the terminal name referee checks, test filters, and primary measures.

People read "<Kind> N: <name>" (`shipharness.datasets.names`): "House rule 1: Tenant isolation",
"Filter 3: Adds coverage or catches a mutant". Event payloads, scores, and exports keep the machine
ids (`r1_tenant`, `R1`, `r1_new_violations`, filter numbers); only the words shown change.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from shipharness.datasets.names import (
    FILTER_NAMES,
    REFEREE_CHECK_ALIASES,
    RULE_NAMES,
    filter_label,
    referee_check_code,
    referee_check_label,
    rule_label,
    rule_short,
)

# Primary-measure fields as people read them.
MEASURE_LABELS = {
    "r1_new_violations": f"{rule_label('R1')}, new violations",
    "continuity_failure": "continuity failure",
    "out_of_scope_files": "files changed outside the allowed paths",
    "test_phase_source_edits": "test-phase source edits",
    "hidden_passed": "hidden tests passed",
    "mutants_killed": "mutants killed",
}


# A rule check's name ("r1_tenant", `shipharness.checks.builtin.RULE_LABELS`) or its rule label.
_RULE_CHECK = re.compile(r"[Rr]([0-9])(_[a-z_]+)?")


def _rule(name: str) -> str | None:
    """The house rule a check name ("r1_tenant") or rule label ("R1") stands for, else None."""
    match = _RULE_CHECK.fullmatch(name)
    code = f"R{match.group(1)}" if match else ""
    return code if code in RULE_NAMES else None


def check_label(name: str) -> str:
    """'House rule 1: Tenant isolation' for r1_tenant or R1; 'Flaky tests (flakiness)' for
    flakiness (and the other `REFEREE_CHECK_NAMES`); any other check name unchanged."""
    code = _rule(name)
    return rule_label(code) if code else referee_check_label(name)


# Referee checks shown by a plainer name on the console pills; the four code-named checks read
# "<name> (<code>)" everywhere (`referee_check_label`).
PLAIN_CHECKS = {"hidden_tests": "hidden tests", "board": "board check"}


def check_short(name: str) -> str:
    """'House rule 1' for r1_tenant or R1 (where space is tight), 'hidden tests' for
    hidden_tests, 'board check' for board, 'Flaky tests (flakiness)' for flakiness; any other
    name unchanged."""
    code = _rule(name)
    if code:
        return rule_short(code)
    return PLAIN_CHECKS.get(name) or referee_check_label(name)


def progress_label(check: str, label: str) -> str:
    """A check's progress label with the plain check name: 'Flaky tests (flakiness), run 5/5'
    for 'flakiness run 5/5'. The runner emits the short form; other labels unchanged."""
    code = referee_check_code(check)
    if not code:
        return label
    plain = referee_check_label(code)
    names = [code, *(a for a, c in REFEREE_CHECK_ALIASES.items() if c == code)]
    for name in sorted(names, key=len, reverse=True):
        if label == name:
            return plain
        if label.startswith(name + " "):
            return f"{plain}, {label[len(name) + 1 :]}"
    return label


def filter_name(number: int) -> str:
    """'Filter 3: Adds coverage or catches a mutant'; 'Filter 9' for a number without a name."""
    return filter_label(number) if number in FILTER_NAMES else f"Filter {number}"


def measure_label(name: str) -> str:
    """'House rule 1: Tenant isolation, new violations' for r1_new_violations; others as is."""
    return MEASURE_LABELS.get(name, name)


# A pytest equality assertion in a discard reason: "assert 422 == 412" (left: what the code gave,
# right: what the test expected). Simple literals only: a number or a quoted string.
_ASSERT_EQ = re.compile(r"assert (-?\d+|'[^']*'|\"[^\"]*\") == (-?\d+|'[^']*'|\"[^\"]*\")\s*$")


def spec_mismatch(reason: str, spec: str) -> tuple[str, str] | None:
    """(returned, expected) when a test filter's discard reason is a failed equality assertion
    whose expected value the feature's spec states explicitly (a status code such as 412, or a
    value such as 'precondition_failed'), and the code returned something else. None otherwise:
    the console then shows the plain reason and claims nothing."""
    match = _ASSERT_EQ.search(reason.strip())
    if not match or not spec:
        return None
    returned, expected = match.groups()
    if returned == expected:
        return None
    word = expected.strip("'\"")
    if expected[0] not in "'\"" and not re.fullmatch(r"[1-5]\d\d", word):
        return None  # a number counts only as an HTTP status code (100 to 599)
    if len(word) < 3 or not re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", spec):
        return None
    return returned, expected


def measure_words(values: dict[str, object]) -> str:
    """The primary values for the terminal, in plain words: 'House rule 1: Tenant isolation, new
    violations: 0'; booleans as yes / no; several values joined with '; '."""
    if not values:
        return "no primary measure"
    parts = []
    for name, value in values.items():
        shown = ("yes" if value else "no") if isinstance(value, bool) else str(value)
        parts.append(f"{measure_label(name)}: {shown}")
    return "; ".join(parts)


# The agent's claim, per phase (owner decision, 2026-10-19). One run has a build phase and then a
# test phase; the test phase is named only when the agent called finish() in it, so a run whose
# only claim was the build claim reads "agent said: done", and a Section 4 run whose test phase
# ended "not done" reads "agent said: done (build) · not done (test phase)".
CLAIM_WORDS = {"done": "done", "not_done": "not done", "none": "no claim"}
_PHASE_WORDS = (("build", "build"), ("test", "test phase"))


def claim_parts(claims: Mapping[str, str]) -> list[tuple[str, str]]:
    """[(claim key, words)] per phase, from {phase: "done" | "not_done" | "none"}: the run's claim
    events (console) or AgentRunResult.claims (terminal). The key picks the pill colour."""
    said = {phase: claims.get(phase) or "none" for phase, _ in _PHASE_WORDS}
    words = {key: CLAIM_WORDS.get(key, key.replace("_", " ")) for key in said.values()}
    if said["test"] == "none":  # no claim in the test phase (or no test phase): build only
        return [(said["build"], words[said["build"]])]
    return [(said[phase], f"{words[said[phase]]} ({name})") for phase, name in _PHASE_WORDS]


def claim_words(claims: Mapping[str, str]) -> str:
    """'agent said: done (build) · not done (test phase)', or 'agent said: done' (one phase)."""
    return "agent said: " + " · ".join(words for _, words in claim_parts(claims))
