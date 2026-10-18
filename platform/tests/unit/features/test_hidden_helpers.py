"""The hidden board tests read markup the way the specs describe it (ruling R-7).

The F2 and F4 specs name class tokens, attributes, and hidden fields, not a byte layout. The
helpers in those hidden test files must accept any attribute order, quote style, extra classes,
and any HTML escaping of comment text.
"""

from __future__ import annotations

import importlib.util
import sys
from html import unescape
from types import ModuleType

from tests.unit.features import support


def hidden_module(rel: str) -> ModuleType:
    path = support.HIDDEN / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(support.HIDDEN))  # hidden_support, as the referee mounts it
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(support.HIDDEN))
    return module


F4_PAGES = [
    '<form class="edit-issue" method="post"><input type="hidden" name="version" value="3"></form>',
    "<form method=post class='card edit-issue'>"
    "<input value='3' name='version' type='hidden'/></form>",
    '<form class="edit-issue wide"><input name=version value=3 type=HIDDEN></form>',
]


def test_f4_form_version_accepts_any_attribute_order_and_quote_style() -> None:
    board = hidden_module("f4/test_f4_board.py")
    for page in F4_PAGES:
        assert board.form_version(f"<main>{page}</main>") == "3", page


def test_f4_form_version_needs_a_hidden_field_in_the_edit_form() -> None:
    board = hidden_module("f4/test_f4_board.py")
    visible = '<form class="edit-issue"><input type="text" name="version" value="3"></form>'
    outside = '<input type="hidden" name="version" value="3"><form class="edit-issue"></form>'
    assert board.form_version(visible) is None
    assert board.form_version(outside) is None


F2_PAGE = """
<section aria-label="Comments" class='comments panel'>
  <article data-comment-id='1' class="comment highlighted">
    <p>&#60;script&#62;x()&#60;/script&#62;</p>
  </article>
  <div class="comment" data-comment-id="2"><p>Second</p></div>
  <section class="nested"><p>inside</p></section>
  <form class="add-comment narrow" method="post"></form>
</section>
<footer class="comment-footer"></footer>
"""


def test_f2_helpers_accept_extra_classes_and_any_attribute_order() -> None:
    board = hidden_module("f2/test_f2_board.py")
    panel = board.panel(F2_PAGE)
    assert board.comment_ids(panel) == ["1", "2"]
    assert "inside" in panel and "comment-footer" not in panel
    assert board.has_class(F2_PAGE, "add-comment")
    assert not board.has_class(F2_PAGE, "add")


def test_f2_escaping_may_use_numeric_references() -> None:
    board = hidden_module("f2/test_f2_board.py")
    panel = board.panel(F2_PAGE)
    assert "<script>" not in panel
    assert "<script>x()</script>" in unescape(panel)
