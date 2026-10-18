"""Build the Live Demo Guide PDF from the Markdown in guide/.

Usage (from the repository root, in WSL or Linux):

    uv run python guide/source/build_pdf.py [--images [DIR]] [--desktop-copy DIR]
                                                     [--html FILE] [--no-pdf]

Order: cover, contents, source/intro.md, part0.md, chapters/1-*.md to chapters/5-*.md, appendix.md.
The conventions it implements are in source/CONVENTIONS.md. It makes no model calls and starts no
container: it renders HTML and prints it with Playwright's Chromium (A4).

--images [DIR]     first copy the images the guide uses from DIR (default ~/guide-work/images)
                   into guide/images/, scaled to 2000 px wide; drop unused ones
--desktop-copy DIR also copy the finished PDF into DIR (created if missing)
--html FILE        also write the final HTML to FILE (for looking at the layout in a browser)
--no-pdf           write the HTML only (needs --html)
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent  # guide
OUTPUT = ROOT / "Harness Engineering Demo Guide.pdf"
DEFAULT_IMAGES = Path("~/guide-work/images").expanduser()

COURSE = "Module 1: Harness Engineering for Coding Agents"
SUBTITLE = "Live Demo Guide"
DATE = "2026-10-18"
SHORT = "Module 1 · Live Demo Guide"

# `> [!TYPE]` boxes: class suffix and the title printed at the top of the box.
BOXES = {
    "CHECKPOINT": ("checkpoint", "✓ Checkpoint"),
    "IFDIFFERENT": ("ifdifferent", "If it looks different"),
    "INSTRUCTOR": ("instructor", "Instructor note"),
    "WARNING": ("warning", "⚠ Warning"),
    "NOTE": ("note", "Note"),
    "TIP": ("note", "Tip"),
}
# Step field labels (`**Where:** ...`).
FIELDS = {
    "where": "where",
    "type": "type",
    "you should see": "see",
    "look at": "look",
    "what it means": "means",
}
STEP_RE = re.compile(r"^Step\s+(\d+)\s*:\s*(.+)$")
BOX_RE = re.compile(r"^\[!([A-Z]+)\]\s*")


def _slug(text: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _css_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class Heading:
    level: int
    text: str
    ident: str


@dataclass
class Part:
    source: Path
    name: str  # named page
    title: str = ""
    kicker: str = ""
    headings: list[Heading] = field(default_factory=list)
    html: str = ""


@dataclass
class Report:
    missing_images: list[str] = field(default_factory=list)
    missing_parts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Builder:
    def __init__(self, report: Report) -> None:
        self.md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
        self.md.renderer.rules["fence"] = self._fence
        self.md.renderer.rules["image"] = self._image
        self.report = report
        self.used: set[str] = set()
        self.source: Path = ROOT

    # -- renderer rules -------------------------------------------------------------------------

    def _fence(self, tokens, idx, options, env):  # noqa: ANN001
        tok = tokens[idx]
        lang = (tok.info or "").strip().split()[0] if tok.info else ""
        code = _esc(tok.content.rstrip("\n"))
        if lang in ("bash", "sh", "shell", "console"):
            return (
                '<div class="cmd"><div class="cmd-bar"><span class="cmd-label">Type this</span>'
                '<span class="cmd-copy">⧉ copy</span></div>'
                f'<pre class="cmd-body"><code>{code}</code></pre></div>\n'
            )
        label = {"text": "Output", "ini": "File", "": "Output"}.get(lang, lang)
        return (
            f'<div class="out"><div class="out-bar">{_esc(label)}</div>'
            f'<pre class="out-body"><code>{code}</code></pre></div>\n'
        )

    def _image(self, tokens, idx, options, env):  # noqa: ANN001
        tok = tokens[idx]
        src = tok.attrGet("src") or ""
        alt = self.md.renderer.renderInlineAsText(tok.children or [], options, env)
        resolved = self._resolve(src)
        if resolved is None:
            self.report.missing_images.append(f"{self.source.name}: {src}")
            return (
                f'<span class="img-missing"><b>Image not built yet</b><br>{_esc(src)}'
                f"<br><i>{_esc(alt)}</i></span>"
            )
        return f'<img src="{_esc(resolved)}" alt="{_esc(alt)}">'

    def _resolve(self, src: str) -> str | None:
        """Image paths: `images/...` from part0/appendix, `../images/...` from chapters/."""
        if re.match(r"^[a-z]+:", src):
            return src
        candidates = [(self.source.parent / src).resolve(), (ROOT / src.lstrip("./")).resolve()]
        stripped = re.sub(r"^(\.\./)+", "", src)
        candidates.append((ROOT / stripped).resolve())
        for path in candidates:
            if path.is_file() and path.stat().st_size > 0:
                return (
                    path.relative_to(ROOT).as_posix()
                    if path.is_relative_to(ROOT)
                    else path.as_uri()
                )
        return None

    # -- token helpers --------------------------------------------------------------------------

    @staticmethod
    def _groups(tokens: list[Token]) -> list[list[Token]]:
        groups, i = [], 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.nesting == 1:
                depth, j = 0, i
                while j < len(tokens):
                    depth += tokens[j].nesting
                    if depth == 0:
                        break
                    j += 1
                groups.append(tokens[i : j + 1])
                i = j + 1
            else:
                groups.append([tok])
                i += 1
        return groups

    def _render(self, tokens: list[Token]) -> str:
        return self.md.renderer.render(tokens, self.md.options, {})

    @staticmethod
    def _inline(group: list[Token]) -> Token | None:
        if len(group) == 3 and group[0].type == "paragraph_open" and group[1].type == "inline":
            return group[1]
        return None

    def _is_image_para(self, group: list[Token]) -> bool:
        inline = self._inline(group)
        if inline is None:
            return False
        kids = [
            k for k in inline.children or [] if not (k.type == "text" and not k.content.strip())
        ]
        kids = [k for k in kids if k.type != "softbreak"]
        return len(kids) == 1 and kids[0].type == "image"

    def _is_caption(self, group: list[Token]) -> bool:
        inline = self._inline(group)
        kids = self._trim(inline) if inline is not None else []
        return bool(kids) and kids[0].type == "em_open" and kids[-1].type == "em_close"

    @staticmethod
    def _trim(inline: Token) -> list[Token]:
        """The inline children without empty text tokens at either end."""
        kids = list(inline.children or [])
        while kids and kids[0].type == "text" and not kids[0].content:
            kids.pop(0)
        while kids and kids[-1].type == "text" and not kids[-1].content:
            kids.pop()
        return kids

    def _mark_field(self, group: list[Token]) -> None:
        inline = self._inline(group)
        kids = self._trim(inline) if inline is not None else []
        if not kids or kids[0].type != "strong_open":
            return
        label = kids[1].content if len(kids) > 1 else ""
        key = label.strip().rstrip(":").strip().lower()
        if key in FIELDS:
            group[0].attrSet("class", f"field field-{FIELDS[key]}")

    def _box(self, group: list[Token]) -> str | None:
        if group[0].type != "blockquote_open" or len(group) < 4 or group[2].type != "inline":
            return None
        inline = group[2]
        match = BOX_RE.match(inline.content)
        if not match or match.group(1) not in BOXES:
            if match:
                self.report.warnings.append(f"{self.source.name}: unknown box [!{match.group(1)}]")
            return None
        kind, title = BOXES[match.group(1)]
        kids = inline.children or []
        while kids and kids[0].type == "text" and not kids[0].content:
            del kids[0]
        if kids and kids[0].type == "text":
            kids[0].content = BOX_RE.sub("", kids[0].content, count=1)
            if not kids[0].content and len(kids) > 1 and kids[1].type in ("softbreak", "hardbreak"):
                del kids[0:2]
        inner = group[1:-1]
        for tok in inner:  # a "cause → fix" line starts a new line; wrapped prose flows on
            kids = tok.children or []
            for k, kid in enumerate(kids):
                if kid.type != "softbreak":
                    continue
                line = []
                for nxt in kids[k + 1 :]:
                    if nxt.type in ("softbreak", "hardbreak"):
                        break
                    line.append(nxt.content)
                if "→" in "".join(line):
                    kid.type = "hardbreak"
        body = self._render(inner)
        body = re.sub(r"^<p>\s*</p>\n?", "", body)
        return f'<div class="box box-{kind}"><div class="box-title">{title}</div>{body}</div>\n'

    # -- one Markdown file ----------------------------------------------------------------------

    def part(self, source: Path, name: str) -> Part:
        self.source = source
        part = Part(source=source, name=name)
        text = source.read_text(encoding="utf-8")
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        groups = self._groups(self.md.parse(text))

        blocks: list[tuple[str, str]] = []  # (kind, html)
        i = 0
        while i < len(groups):
            group = groups[i]
            first = group[0]
            if first.type == "heading_open":
                level = int(first.tag[1])
                title = group[1].content.strip()
                if level == 1:
                    part.title = title
                    blocks.append(("h1", title))
                elif level <= 3:
                    blocks.append((f"h{level}", title))
                else:
                    blocks.append(("html", self._render(group)))
                i += 1
                continue
            if self._is_image_para(group):
                img = self._render([group[1]])
                caption, callouts, used = "", "", 1
                if i + 1 < len(groups) and self._is_caption(groups[i + 1]):
                    cap_inline = groups[i + 1][1]
                    caption = self.md.renderer.renderInline(
                        self._trim(cap_inline)[1:-1], self.md.options, {}
                    )
                    used = 2
                    if i + 2 < len(groups) and groups[i + 2][0].type == "ordered_list_open":
                        callouts = self._render(groups[i + 2]).replace(
                            "<ol", '<ol class="callouts"', 1
                        )
                        used = 3
                else:
                    self.report.warnings.append(f"{source.name}: image without a caption line")
                fig = f'<figure class="shot">{img}'
                if caption:
                    fig += f"<figcaption>{caption}</figcaption>"
                fig += f"{callouts}</figure>\n"
                blocks.append(("figure", fig))
                i += used
                continue
            box = self._box(group)
            if box is not None:
                blocks.append(("box", box))
                i += 1
                continue
            self._mark_field(group)
            kind = "table" if first.type == "table_open" else "html"
            rendered = self._render(group)
            if kind == "table":
                rendered = f'<div class="table-wrap">{rendered}</div>'
            blocks.append((kind, rendered))
            i += 1

        part.html = self._assemble(part, self._keep_labels(blocks))
        return part

    @staticmethod
    def _keep_labels(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Join a "Type:" or "You should see:" line with the command, output, or screenshot
        right after it, so the label never ends a page alone."""
        out: list[tuple[str, str]] = []
        for kind, content in blocks:
            prev = out[-1] if out else None
            follows = kind == "figure" or content.startswith(
                ('<div class="cmd"', '<div class="out"')
            )
            if (
                prev
                and follows
                and prev[1].startswith(
                    ('<p class="field field-type"', '<p class="field field-see"')
                )
            ):
                out[-1] = ("keep", f'<div class="keep">{prev[1]}{content}</div>')
            else:
                out.append((kind, content))
        return out

    def _assemble(self, part: Part, blocks: list[tuple[str, str]]) -> str:
        out: list[str] = []
        in_step = False
        pending_head: str | None = None  # step head waiting for its first block

        def close_step() -> None:
            nonlocal in_step, pending_head
            if pending_head is not None:
                out.append(f'<div class="step-head">{pending_head}</div>')
                pending_head = None
            if in_step:
                out.append("</div></section>\n")
            in_step = False

        has_figure: list[int] = []
        for kind, content in blocks:
            if kind == "h1":
                close_step()
                ident = _slug(content, self.used)
                part.headings.append(Heading(1, content, ident))
                kicker, _, title = content.partition(":")
                if not title:
                    kicker, title = "", content
                title = title.strip()
                part.kicker, part.title = kicker.strip(), title[:1].upper() + title[1:]
                band = f'<header class="band" id="{ident}">'
                if part.kicker:
                    band += f'<div class="band-kicker">{_esc(part.kicker)}</div>'
                band += f"<h1>{_esc(part.title)}</h1></header>\n"
                out.append(band)
            elif kind in ("h2", "h3"):
                step = STEP_RE.match(content) if kind == "h3" else None
                close_step()
                ident = _slug(content, self.used)
                if kind == "h2":
                    part.headings.append(Heading(2, content, ident))
                    out.append(f'<h2 id="{ident}">{self._inline_md(content)}</h2>\n')
                elif step:
                    in_step = True
                    has_figure.append(len(out))
                    out.append(f'<section class="step" id="{ident}">')
                    pending_head = (
                        f'<h3 class="step-title"><span class="step-num">Step {step.group(1)}</span>'
                        f'<span class="step-text">{self._inline_md(step.group(2))}</span></h3>'
                    )
                    out.append('<div class="step-body">')
                else:
                    out.append(f'<h3 id="{ident}">{self._inline_md(content)}</h3>\n')
            else:
                if pending_head is not None:
                    # Keep the step title with its first block (never an orphaned title).
                    out.append(f'<div class="step-head">{pending_head}{content}</div>')
                    pending_head = None
                else:
                    out.append(content)
                if in_step and kind == "figure":
                    start = has_figure[-1]
                    out[start] = out[start].replace('class="step"', 'class="step step-long"', 1)
        close_step()
        return "".join(out)

    def _inline_md(self, text: str) -> str:
        return self.md.renderInline(text)


# -- page rules, cover, contents ----------------------------------------------------------------


def page_rules(parts: list[Part]) -> str:
    rules = []
    for part in parts:
        label = f"{part.kicker}: {part.title}" if part.kicker else part.title
        rules.append(
            f"@page {part.name} {{ @top-right {{ content: {_css_string(label)}; }} }}\n"
            f".part-{part.name} {{ page: {part.name}; }}"
        )
    return "\n".join(rules)


def cover_html() -> str:
    return f"""
<section class="cover">
  <div class="cover-top">
    <div class="cover-tag">shipharness · TeamTrack</div>
  </div>
  <div class="cover-main">
    <div class="cover-arms">
      <span class="arm arm-bare">bare arm</span><span class="arm arm-harness">harness arm</span>
    </div>
    <h1 class="cover-title">{_esc(COURSE)}</h1>
    <div class="cover-sub">{_esc(SUBTITLE)}</div>
    <p class="cover-blurb">Every command, every screen and every result of the five live demos,
    step by step, with what to say in class.</p>
  </div>
  <div class="cover-foot"><span>{_esc(DATE)}</span><span>Console screens 1 to 5 · Terminal 1 and
  Terminal 2</span></div>
</section>
"""


def toc_html(parts: list[Part], pages: dict[str, int] | None) -> str:
    rows = []
    for part in parts:
        for head in part.headings:
            page = str(pages.get(head.ident, "")) if pages else "00"
            cls = "toc-1" if head.level == 1 else "toc-2"
            text = head.text
            if head.level == 1 and part.kicker:
                text = f'<span class="toc-kicker">{_esc(part.kicker)}</span>{_esc(part.title)}'
            else:
                text = MarkdownIt().renderInline(text)
            rows.append(
                f'<li class="{cls}"><a href="#{head.ident}"><span class="toc-text">{text}</span>'
                f'<span class="toc-dots"></span><span class="toc-page">{page}</span></a></li>'
            )
    return (
        '<section class="toc"><h1 class="toc-title">Contents</h1>'
        f'<ol class="toc-list">{"".join(rows)}</ol></section>'
    )


def document(parts: list[Part], pages: dict[str, int] | None) -> str:
    template = (BUILD / "template.html").read_text(encoding="utf-8")
    css = (BUILD / "style.css").read_text(encoding="utf-8")
    body = "".join(
        f'<section class="part part-{p.name}" data-source="{_esc(p.source.name)}">'
        f"{p.html}</section>"
        for p in parts
    )
    return (
        template.replace("{{base}}", ROOT.as_uri() + "/")
        .replace("{{title}}", _esc(f"{COURSE}: {SUBTITLE}"))
        .replace("{{css}}", css + "\n" + page_rules(parts))
        .replace("{{cover}}", cover_html())
        .replace("{{toc}}", toc_html(parts, pages))
        .replace("{{body}}", body)
    )


# -- reading the page numbers back from the PDF -------------------------------------------------


def _objects(data: bytes) -> dict[int, bytes]:
    objs = {}
    for match in re.finditer(rb"(\d+) 0 obj\s*(.*?)\s*endobj", data, re.S):
        objs[int(match.group(1))] = match.group(2)
    # Object streams (PDF 1.5) hold more objects: unpack them too.
    for body in list(objs.values()):
        if b"/ObjStm" not in body:
            continue
        head, _, stream = body.partition(b"stream")
        stream = stream.lstrip(b"\r\n").rsplit(b"endstream", 1)[0]
        try:
            raw = zlib.decompress(stream)
        except zlib.error:
            continue
        n = int(re.search(rb"/N (\d+)", head).group(1))
        first = int(re.search(rb"/First (\d+)", head).group(1))
        nums = list(map(int, raw[:first].split()))
        for k in range(n):
            num, off = nums[2 * k], nums[2 * k + 1]
            end = nums[2 * k + 3] if k + 1 < n else len(raw) - first
            objs.setdefault(num, raw[first + off : first + end])
    return objs


def dest_pages(pdf: Path) -> dict[str, int]:
    """Named destination -> 1-based page number, read from the PDF Chromium writes."""
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf))
        return {
            name.lstrip("/"): reader.get_destination_page_number(dest) + 1
            for name, dest in reader.named_destinations.items()
        }
    except ImportError:
        pass
    data = pdf.read_bytes()
    objs = _objects(data)
    catalog = next(b for b in objs.values() if re.search(rb"/Type\s*/Catalog", b))
    root_pages = int(re.search(rb"/Pages (\d+) 0 R", catalog).group(1))
    order: list[int] = []

    def walk(num: int) -> None:
        body = objs[num]
        if re.search(rb"/Type\s*/Pages", body):
            kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S).group(1)
            for kid in re.findall(rb"(\d+) 0 R", kids):
                walk(int(kid))
        else:
            order.append(num)

    walk(root_pages)
    index = {num: i + 1 for i, num in enumerate(order)}
    dests_ref = re.search(rb"/Dests (\d+) 0 R", catalog)
    if dests_ref:
        table = objs[int(dests_ref.group(1))]
    else:
        names = re.search(rb"/Dests\s*<<(.*?)>>", catalog, re.S)
        table = names.group(1) if names else b""
    out = {}
    for name, page in re.findall(rb"/([^\s/\[\]<>()]+)\s*\[\s*(\d+) 0 R", table):
        decoded = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), name)
        out[decoded.decode("utf-8", "replace")] = index.get(int(page), 0)
    return out


def print_pdf(html_text: str, out: Path) -> int:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / "guide.html"
        page_file.write_text(html_text, encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(page_file.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.pdf(
                path=str(out),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                outline=True,
                tagged=True,
            )
            browser.close()
    return len(re.findall(rb"/Type\s*/Page[^s]", out.read_bytes()))


# -- main ----------------------------------------------------------------------------------------


def sources(report: Report) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path, name in ((BUILD / "intro.md", "intro"), (ROOT / "part0.md", "part0")):
        if path.is_file():
            found.append((path, name))
        else:
            report.missing_parts.append(path.name)
    for n in range(1, 6):
        matches = sorted((ROOT / "chapters").glob(f"{n}-*.md"))
        if matches:
            found.append((matches[0], f"ch{n}"))
            if len(matches) > 1:
                report.warnings.append(f"chapter {n}: several files, using {matches[0].name}")
        else:
            report.missing_parts.append(f"chapters/{n}-*.md")
    appendix = ROOT / "appendix.md"
    if appendix.is_file():
        found.append((appendix, "appendix"))
    else:
        report.missing_parts.append("appendix.md")
    return found


IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:\.\./)*images/([^)\s]+\.png)\)")
MAX_WIDTH = 2000  # px: about 290 dpi at the A4 text width, and a fraction of the capture size


def _trim_bottom(img):  # noqa: ANN001, ANN202
    """Cut the empty console background below the last content, so a short screen (the run
    list) does not print as a mostly black page. Top, left and right stay as captured."""
    from PIL import Image, ImageChops

    bg = img.getpixel((img.width - 1, img.height - 1))
    plain = Image.new("RGB", img.size, bg)
    diff = ImageChops.difference(img, plain).convert("L").point(lambda v: 255 if v > 24 else 0)
    box = diff.getbbox()
    if not box:
        return img
    bottom = min(img.height, box[3] + img.height // 40)
    return img.crop((0, 0, img.width, bottom)) if bottom < img.height * 0.9 else img


def referenced_images() -> set[str]:
    """Image paths below images/ that the Markdown sources use."""
    found: set[str] = set()
    for path, _ in sources(Report()):
        found.update(IMAGE_RE.findall(path.read_text(encoding="utf-8")))
    return found


def copy_images(src: Path) -> tuple[int, list[str], int]:
    """Copy the images the guide uses from src into images/, scaled to MAX_WIDTH, and remove
    the ones it no longer uses. Returns (copied, missing in src, removed)."""
    from PIL import Image

    dest = ROOT / "images"
    wanted = referenced_images()
    copied, missing = 0, []
    for rel in sorted(wanted):
        source = src / rel
        if not source.is_file():
            missing.append(rel)
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            img = _trim_bottom(img.convert("RGB"))
            if img.width > MAX_WIDTH:
                img = img.resize(
                    (MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS
                )
            # 256 colours: flat console screenshots keep their text, at a third of the size.
            img = img.convert("RGB").quantize(256, method=Image.Quantize.FASTOCTREE)
            img.save(target, optimize=True)
        copied += 1
    removed = 0
    for old in dest.rglob("*.png") if dest.is_dir() else []:
        if old.relative_to(dest).as_posix() not in wanted:
            old.unlink()
            removed += 1
    return copied, missing, removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--images", nargs="?", const=str(DEFAULT_IMAGES), default=None, metavar="DIR")
    ap.add_argument("--desktop-copy", metavar="DIR")
    ap.add_argument("--html", metavar="FILE")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args(argv)

    if args.images:
        src = Path(args.images).expanduser()
        if not src.is_dir():
            print(f"x images folder not found: {args.images}")
            return 1
        copied, missing, removed = copy_images(src)
        print(f"images: copied {copied} PNG files into guide/images/, removed {removed}")
        for rel in missing:
            print(f"! image not in {src.name}/: {rel}")

    report = Report()
    builder = Builder(report)
    parts = [builder.part(path, name) for path, name in sources(report)]

    if args.no_pdf:
        if not args.html:
            print("x --no-pdf needs --html FILE")
            return 1
        Path(args.html).write_text(document(parts, None), encoding="utf-8")
        print(f"html: {args.html}")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        draft = Path(tmp) / "pass1.pdf"
        print_pdf(document(parts, None), draft)
        pages = dest_pages(draft)
    final_html = document(parts, pages)
    if args.html:
        Path(args.html).write_text(final_html, encoding="utf-8")
    count = print_pdf(final_html, OUTPUT)
    wanted = [h.ident for p in parts for h in p.headings]
    unknown = [ident for ident in wanted if not pages.get(ident)]
    print(f"pdf: guide/{OUTPUT.name} ({count} pages, A4)")
    if unknown:
        print(f"! contents: no page found for {len(unknown)} headings: {', '.join(unknown[:5])}")
    for name in report.missing_parts:
        print(f"! missing source: {name}")
    for name in report.missing_images:
        print(f"! image not found (placeholder shown): {name}")
    for line in report.warnings:
        print(f"! {line}")
    if args.desktop_copy:
        dest = Path(args.desktop_copy).expanduser()
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUTPUT, dest / OUTPUT.name)
        print(f"copy: {dest.name}/{OUTPUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
