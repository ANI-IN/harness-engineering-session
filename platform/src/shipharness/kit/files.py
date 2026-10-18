"""Copy the kit templates and the four course skills into a target repository, deterministically.

Every file is copied byte for byte. A file that already exists with other content is skipped and
reported, unless `force` is set. A file that already holds the same bytes is left alone, so a second
run writes nothing.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass, field
from pathlib import Path

from shipharness.config.prices import REPO_ROOT

KIT_DIR = REPO_ROOT / "use-in-your-repo" / "kit"
TEMPLATES = KIT_DIR / "templates"
SKILLS_DIR = REPO_ROOT / "use-in-your-repo" / "skills"
SKILL_NAMES = ("harness-setup", "assured-tests", "house-rules", "skill-template")
SKILL_FOLDERS = {
    "claude": (".claude/skills",),
    "agents": (".agents/skills",),
    "both": (".claude/skills", ".agents/skills"),
}
_SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


@dataclass
class InstallReport:
    written: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def _files(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and not _SKIP_PARTS.intersection(p.relative_to(root).parts)
        and p.suffix not in _SKIP_SUFFIXES
    )


def template_files(templates: Path = TEMPLATES) -> list[str]:
    """Paths of the kit templates, relative to the templates folder, sorted."""
    return _files(templates)


def plan(
    skills: str = "both", templates: Path = TEMPLATES, skills_dir: Path = SKILLS_DIR
) -> list[tuple[Path, str]]:
    """(source file, destination relative to the target) for every file, sorted by destination."""
    if skills not in SKILL_FOLDERS:
        raise ValueError(f"--skills must be claude, agents, or both, got {skills!r}")
    pairs = [(templates / rel, rel) for rel in template_files(templates)]
    for folder in SKILL_FOLDERS[skills]:
        for name in SKILL_NAMES:
            source = skills_dir / name
            if not (source / "SKILL.md").is_file():
                raise ValueError(f"skill not found: {source}")
            pairs += [(source / rel, f"{folder}/{name}/{rel}") for rel in _files(source)]
    return sorted(pairs, key=lambda pair: pair[1])


def install(
    target: Path,
    *,
    skills: str = "both",
    force: bool = False,
    templates: Path = TEMPLATES,
    skills_dir: Path = SKILLS_DIR,
) -> InstallReport:
    """Copy the kit into `target` (an existing directory)."""
    if not target.is_dir():
        raise ValueError(f"target directory not found: {target}")
    pairs = plan(skills, templates, skills_dir)
    report = InstallReport()
    for source, rel in pairs:
        dest = target / rel
        data = source.read_bytes()
        if dest.exists():
            if dest.is_file() and dest.read_bytes() == data:
                report.unchanged.append(rel)
                continue
            if not force or not dest.is_file():
                report.skipped.append(rel)
                continue
            report.overwritten.append(rel)
        else:
            report.written.append(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if source.suffix == ".sh" or source.stat().st_mode & stat.S_IXUSR:
            dest.chmod(0o755)
    return report
