"""Filter 6: discard a proposed test that duplicates an existing test or an earlier kept candidate.

TestGen-LLM added a filter that removes previously seen test cases (B11 F-b-26). This filter
follows the shipharness Filter protocol (`shipharness.filters.models.Filter`): a `number`, a
`name`, and `evaluate(cand, ctx) -> FilterResult`, so `run_pipeline(..., filters=[...])` can run it.

Two tests are duplicates when their decorators, parameter lists, and bodies are equal as syntax
trees after this normalisation:

1. the function name, comments, blank lines, and formatting are ignored;
2. a docstring (a string literal as the first statement) is dropped;
3. every local variable (a name the test binds in its body: `=`, `+=`, annotated assignment, `for`,
   `with ... as`, `:=`, comprehension targets, `except ... as`) is renamed to a placeholder in
   order of first appearance in the source.

Parameters (pytest fixtures), global names, imported names, attribute names, and literal values
are never renamed.
"""

from __future__ import annotations

from collections.abc import Iterable

from shipharness.filters.models import CandidateTest, FilterContext, FilterResult


def normalized(source: str, test_id: str) -> str | None:
    """A comparable text form of one test function, or None if the source does not parse or has
    no function with that test id ("file::name" or "file::Class::name")."""
    # TODO(A4-5): parse with `ast`, find the function, apply the normalisation in the module
    # docstring, and return `ast.dump(...)` of (decorators, arguments, body) without attributes.
    raise NotImplementedError("TODO(A4-5): normalized")


class NoDuplicateTest:
    number = 6
    name = "not a duplicate of an existing or earlier test"

    def __init__(self, existing: Iterable[CandidateTest] = ()) -> None:
        """`existing`: the existing suite's tests, captured at the start of the test phase
        (for example with `shipharness.filters.collect_candidates(workspace, files)`)."""
        self.existing = list(existing)
        # TODO(A4-6): precompute the normalised form of every existing test, and keep a record
        # of the candidates this instance has kept, in order.

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        # TODO(A4-7): discard (passed=False) when `cand` duplicates an existing test (other than
        # one with the same test id) or a candidate this instance kept earlier; name that test's
        # id in the reason. Discard with a reason when the candidate cannot be normalised. Keep
        # it otherwise and remember it. Every result has filter=6 and a non-empty reason.
        raise NotImplementedError("TODO(A4-7): NoDuplicateTest.evaluate")
