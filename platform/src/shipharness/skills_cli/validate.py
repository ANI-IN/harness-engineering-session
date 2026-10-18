"""Agent Skills validation.

Errors are the checks the reference validator skills-ref 0.1.1 runs (B5): frontmatter present and
parseable, only the six spec fields, `name` rules (read with the ASCII charset `a-z0-9-`),
`description` and `compatibility` lengths, and `metadata` as a string map. Warnings are the
spec's recommendations that skills-ref does not check (B1): SKILL.md under 500 lines, file
references one level deep, and referenced files that do not exist.

The frontmatter parser is a small strict subset of YAML (scalars, quoted strings, block scalars, and
one nested string map). It rejects what strictyaml, the parser skills-ref uses, rejects for skill
frontmatter: flow style, duplicate keys, and unquoted values that contain `: `.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_FIELDS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500
MAX_LINES = 500
SKIP_DIRS = {"__pycache__", "node_modules"}

_NAME_CHARS = re.compile(r"^[a-z0-9-]+$")
_KEY = re.compile(r"^([^\s#:][^:]*?):(?:[ \t]+(.*?))?[ \t]*$")
_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_PATH_TOKEN = re.compile(r"(?<![\w./-])((?:scripts|references|assets)/[\w./-]*)")
_URL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", re.IGNORECASE)

FieldValue = str | dict[str, str] | list[str]


@dataclass
class SkillReport:
    folder: Path
    name: str | None = None
    lines: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# --- frontmatter ---------------------------------------------------------------------------


def _scalar(raw: str, where: str) -> str:
    """One plain or quoted YAML scalar on a single line."""
    value = raw.strip()
    if not value:
        return ""
    if value[0] in "[{":
        raise ValueError(f"{where}: flow style ([...] or {{...}}) is not allowed; use block style")
    if value[0] == '"':
        end = value.rfind('"')
        if end == 0 or value[end + 1 :].strip() and not value[end + 1 :].strip().startswith("#"):
            raise ValueError(f"{where}: unterminated double-quoted string")
        inner = value[1:end]
        return (
            inner.replace("\\\\", "\0")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\0", "\\")
        )
    if value[0] == "'":
        end = value.rfind("'")
        if end == 0 or value[end + 1 :].strip() and not value[end + 1 :].strip().startswith("#"):
            raise ValueError(f"{where}: unterminated single-quoted string")
        return value[1:end].replace("''", "'")
    if value[0] in "&*!%@`|>":
        raise ValueError(f"{where}: a value may not start with {value[0]!r}; quote the value")
    comment = re.search(r"\s#", value)
    if comment:
        value = value[: comment.start()].rstrip()
    if ": " in value or value.endswith(":"):
        raise ValueError(f"{where}: the value contains ': '; quote the value")
    return value


def _indented_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Lines after `start` that are indented (or blank), with the common indentation removed."""
    block: list[str] = []
    index = start
    while index < len(lines) and (not lines[index].strip() or lines[index][:1] in " \t"):
        block.append(lines[index])
        index += 1
    while block and not block[-1].strip():
        block.pop()
        index -= 1
    indents = [len(line) - len(line.lstrip()) for line in block if line.strip()]
    cut = min(indents) if indents else 0
    return [line[cut:] if line.strip() else "" for line in block], index


def _block_scalar(indicator: str, block: list[str]) -> str:
    """Literal (|) keeps line breaks, folded (>) joins lines; trailing newlines are dropped."""
    if indicator.startswith("|"):
        return "\n".join(block)
    else:
        paragraphs: list[str] = []
        current: list[str] = []
        for line in block:
            if line.strip():
                current.append(line.strip())
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        if current:
            paragraphs.append(" ".join(current))
        return "\n".join(paragraphs)


def _nested(block: list[str], key: str) -> FieldValue:
    content = [line for line in block if line.strip() and not line.lstrip().startswith("#")]
    if all(line.startswith("- ") or line == "-" for line in content):
        return [_scalar(line[1:], f"'{key}' item") for line in content]
    mapping: dict[str, str] = {}
    for line in content:
        if line[:1] in " \t":
            raise ValueError(f"'{key}': nested values deeper than one level are not allowed")
        match = _KEY.match(line)
        if not match:
            raise ValueError(f"'{key}': line {line.strip()!r} is not a key: value pair")
        sub_key, raw = match.group(1).strip(), match.group(2) or ""
        if sub_key in mapping:
            raise ValueError(f"'{key}': duplicate key '{sub_key}'")
        mapping[sub_key] = _scalar(raw, f"'{key}.{sub_key}'")
    return mapping


def parse_skill_frontmatter(text: str) -> tuple[dict[str, FieldValue], int]:
    """Parse the frontmatter of a SKILL.md. Returns (fields, 1-based line where the body starts).

    Raises ValueError with a readable reason when the frontmatter is missing or not parseable.
    """
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
    except StopIteration:
        raise ValueError("SKILL.md frontmatter is not closed with ---") from None
    body = lines[1:close]
    fields: dict[str, FieldValue] = {}
    index = 0
    while index < len(body):
        line = body[index]
        where = f"frontmatter line {index + 2}"
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[:1] in " \t":
            raise ValueError(f"{where}: unexpected indentation")
        match = _KEY.match(line)
        if not match:
            raise ValueError(f"{where}: {line.strip()!r} is not a key: value pair")
        key, raw = match.group(1).strip(), (match.group(2) or "").strip()
        if key in fields:
            raise ValueError(f"{where}: duplicate key '{key}'")
        block, index = _indented_block(body, index + 1)
        if re.fullmatch(r"[|>][+-]?", raw):
            fields[key] = _block_scalar(raw, block)
        elif not raw:
            fields[key] = _nested(block, key) if any(b.strip() for b in block) else ""
        elif block:
            # A plain scalar continued on indented lines folds into one line.
            parts = [_scalar(raw, f"'{key}'")] + [_scalar(b, f"'{key}'") for b in block]
            fields[key] = " ".join(part for part in parts if part)
        else:
            fields[key] = _scalar(raw, f"'{key}'")
    if not fields:
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return fields, close + 2


# --- errors --------------------------------------------------------------------------------


def _name_errors(value: FieldValue, folder: Path) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return ["Field 'name' must be a non-empty string"]
    name = unicodedata.normalize("NFKC", value.strip())
    errors: list[str] = []
    if len(name) > MAX_NAME:
        errors.append(f"Skill name '{name}' exceeds {MAX_NAME} character limit ({len(name)} chars)")
    if name != name.lower():
        errors.append(f"Skill name '{name}' must be lowercase")
    if name.startswith("-") or name.endswith("-"):
        errors.append("Skill name cannot start or end with a hyphen")
    if "--" in name:
        errors.append("Skill name cannot contain consecutive hyphens")
    if not _NAME_CHARS.match(name.lower()):
        errors.append(
            f"Skill name '{name}' contains invalid characters. "
            "Only ASCII letters a-z, digits 0-9, and hyphens are allowed."
        )
    folder_name = unicodedata.normalize("NFKC", folder.name)
    if folder_name != name:
        errors.append(f"Directory name '{folder.name}' must match skill name '{name}'")
    return errors


def _field_errors(fields: dict[str, FieldValue], folder: Path) -> list[str]:
    errors: list[str] = []
    extra = sorted(set(fields) - set(ALLOWED_FIELDS))
    if extra:
        errors.append(
            f"Unexpected fields in frontmatter: {', '.join(extra)}. "
            f"Only {sorted(ALLOWED_FIELDS)} are allowed."
        )
    if "name" not in fields:
        errors.append("Missing required field in frontmatter: name")
    else:
        errors.extend(_name_errors(fields["name"], folder))
    description = fields.get("description")
    if "description" not in fields:
        errors.append("Missing required field in frontmatter: description")
    elif not isinstance(description, str) or not description.strip():
        errors.append("Field 'description' must be a non-empty string")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(
            f"Description exceeds {MAX_DESCRIPTION} character limit ({len(description)} chars)"
        )
    if "compatibility" in fields:
        compatibility = fields["compatibility"]
        if not isinstance(compatibility, str) or not compatibility.strip():
            errors.append("Field 'compatibility' must be a non-empty string")
        elif len(compatibility) > MAX_COMPATIBILITY:
            errors.append(
                f"Compatibility exceeds {MAX_COMPATIBILITY} character limit "
                f"({len(compatibility)} chars)"
            )
    if "metadata" in fields and not isinstance(fields["metadata"], dict):
        errors.append("Field 'metadata' must be a map of string keys to string values")
    for key in ("license", "allowed-tools"):
        if key in fields and not isinstance(fields[key], str):
            errors.append(f"Field '{key}' must be a string")
    return errors


# --- warnings ------------------------------------------------------------------------------


def _references(text: str) -> list[str]:
    found: list[str] = []
    for match in _LINK.finditer(text):
        target = match.group(1)
        if not _URL.match(target):
            found.append(target.split("#", 1)[0])
    for match in _PATH_TOKEN.finditer(text):
        found.append(match.group(1).rstrip("."))
    unique: list[str] = []
    for target in found:
        if target and target not in unique:
            unique.append(target)
    return unique


def _inside(folder: Path, target: str) -> Path | None:
    if target.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", target):
        return None
    root = folder.resolve()
    resolved = (root / target).resolve()
    return resolved if resolved == root or resolved.is_relative_to(root) else None


def _reference_warnings(folder: Path, text: str) -> list[str]:
    warnings: list[str] = []
    for target in _references(text):
        resolved = _inside(folder, target)
        if resolved is None:
            warnings.append(f"reference '{target}' points outside the skill folder")
            continue
        if not resolved.exists():
            warnings.append(f"referenced file '{target}' is missing")
            continue
        relative = resolved.relative_to(folder.resolve()).as_posix()
        is_asset = relative.split("/", 1)[0] == "assets"
        if resolved.is_file() and resolved.suffix == ".md" and not is_asset:
            if relative == "SKILL.md":
                continue
            # A chain is a reference file that points to another file of this skill. Mentions
            # of paths that are not files here (for example a target repository's folders) are
            # not references.
            nested = [
                target
                for target in _references(resolved.read_text(encoding="utf-8", errors="replace"))
                if (inner := _inside(folder, target)) is not None
                and inner.is_file()
                and inner != resolved
            ]
            if nested:
                warnings.append(
                    f"'{relative}' references {', '.join(repr(n) for n in nested[:3])}: keep file "
                    "references one level deep from SKILL.md (Agent Skills spec)"
                )
    return warnings


# --- entry points --------------------------------------------------------------------------


def validate_skill(folder: Path) -> SkillReport:
    folder = Path(folder)
    report = SkillReport(folder=folder)
    if not folder.exists():
        report.errors.append(f"Path does not exist: {folder}")
        return report
    if not folder.is_dir():
        report.errors.append(f"Not a directory: {folder}")
        return report
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        if (folder / "skill.md").is_file():
            skill_md = folder / "skill.md"
            report.warnings.append("rename skill.md to SKILL.md (the spec's exact file name)")
        else:
            report.errors.append("Missing required file: SKILL.md")
            return report
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    report.lines = len(text.splitlines())
    try:
        fields, body_start = parse_skill_frontmatter(text)
    except ValueError as exc:
        report.errors.append(f"Invalid frontmatter: {exc}")
        return report
    name = fields.get("name")
    report.name = name.strip() if isinstance(name, str) and name.strip() else None
    report.errors.extend(_field_errors(fields, folder))
    if report.lines > MAX_LINES:
        report.warnings.append(
            f"SKILL.md has {report.lines} lines, over 500 lines: move detail into references/"
        )
    body = "\n".join(text.lstrip("﻿").splitlines()[body_start - 1 :])
    report.warnings.extend(_reference_warnings(folder, body))
    return report


def validate_path(path: Path) -> list[SkillReport]:
    """Validate one skill folder, or every skill folder directly inside `path`."""
    path = Path(path)
    if not path.is_dir() or (path / "SKILL.md").is_file() or (path / "skill.md").is_file():
        report = validate_skill(path)
        report.name = report.name or path.name
        return [report]
    reports: list[SkillReport] = []
    for child in sorted(path.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith(".") or child.name in SKIP_DIRS:
            continue
        report = validate_skill(child)
        report.name = report.name or child.name
        reports.append(report)
    if not reports:
        reports.append(SkillReport(folder=path, name=path.name, errors=["no SKILL.md found"]))
    return reports
