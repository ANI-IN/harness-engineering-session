"""Your tests for filter 6. Write each test before the code it checks, and see it fail first."""

from __future__ import annotations

from a4_verification.dedup_filter import normalized

ORIGINAL = """\
def test_a(client):
    r = client.get("/x")
    assert r.status_code == 200
"""


def test_the_function_name_is_ignored() -> None:
    renamed = ORIGINAL.replace("test_a", "test_b")
    assert normalized(ORIGINAL, "t.py::test_a") == normalized(renamed, "t.py::test_b")


# TODO(A4-9): add your own tests, for example:
#   - a docstring and comments are ignored; a changed literal is not;
#   - locals renamed consistently are equal; swapped locals are not;
#   - a candidate equal to an existing test is discarded and the reason names that test;
#   - a later copy of a kept candidate is discarded; a file that does not parse is discarded.
