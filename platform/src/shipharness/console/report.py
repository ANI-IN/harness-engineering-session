"""Screen 4 (A/B Report) data: ScoreRecords and experiments read from `exports/`.

Counts are shown as "9/10", never as percentages. Unreadable or incomplete files are counted and
skipped so one bad export cannot blank the screen.
"""

from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shipharness.ab.score import REFEREE_VERSION, evaluate_primary, primary_fields
from shipharness.console.labels import measure_label
from shipharness.layout import RepoRootNotFound, find_repo_root

ARM_ORDER = {"bare": 0, "harness": 1}
# The course's own score records, measured before class (trace links removed), shipped with the
# course; screen 4 always shows them, with new runs from exports/ next to them.
try:
    BEFORE_CLASS_DIR = find_repo_root(Path(__file__)) / "docs" / "evidence" / "scores"
except RepoRootNotFound:  # installed outside the repository: no bundled records
    BEFORE_CLASS_DIR = Path("docs") / "evidence" / "scores"
SECTIONS_FILE = "score-sections.json"  # ab id -> section (demo-N, final) of the bundled records
_REQUIRED = ("run_id", "arm", "variant", "passed_primary")


def safe_url(value: object) -> str | None:
    """Keep http(s) links only, so an export or event cannot inject a `javascript:` link."""
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return value
    return None


@dataclass
class Dot:
    run_id: str
    passed: bool
    recorded: bool
    sandboxed: bool
    before_class: bool = False  # from the course's own records, measured before class


@dataclass
class DotGroup:
    feature: str
    variant: str
    arm: str
    layers: str
    measure: str = ""  # a section demo's own measure ("files changed outside ..."); "" = dataset's
    dots: list[Dot] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(d.passed for d in self.dots)

    @property
    def count_label(self) -> str:
        return f"{self.passed}/{len(self.dots)}"

    @property
    def before(self) -> list[Dot]:
        return [d for d in self.dots if d.before_class]

    @property
    def new(self) -> list[Dot]:
        return [d for d in self.dots if not d.before_class]

    @property
    def split_label(self) -> str:
        """'8/8 before class' and, when there are new runs, '· 1/1 new'."""
        before, new = self.before, self.new
        text = f"{sum(d.passed for d in before)}/{len(before)} before class" if before else ""
        if new:
            text += (" · " if text else "") + f"{sum(d.passed for d in new)}/{len(new)} new"
        return text


@dataclass
class Bar:
    label: str
    passed: int
    total: int

    @property
    def count_label(self) -> str:
        return f"{self.passed}/{self.total}"


@dataclass
class CostRow:
    arm: str
    spent_usd: float
    verified: int

    @property
    def per_verified_usd(self) -> float | None:
        return self.spent_usd / self.verified if self.verified else None


@dataclass
class AgreementRow:
    arm: str
    agrees: int
    known: int

    @property
    def count_label(self) -> str:
        return f"{self.agrees}/{self.known}"


@dataclass
class Experiment:
    name: str
    url: str | None
    comparison_url: str | None
    split: str


@dataclass
class Report:
    groups: list[DotGroup] = field(default_factory=list)
    ablation: list[Bar] = field(default_factory=list)
    costs: list[CostRow] = field(default_factory=list)
    reviewer: list[AgreementRow] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    skipped: int = 0
    older: int = 0  # records of an earlier referee version, left out
    unsandboxed: int = 0
    recorded: int = 0
    single_arm: int = 0  # harness-in-action runs, left out of the bare-vs-harness comparison
    constructed: int = 0  # constructed examples (scripted steps), never counted
    before_class_runs: int = 0  # dots from the course's own records (BEFORE_CLASS_DIR)
    new_runs: int = 0  # dots from exports/ that are not among them

    @property
    def empty(self) -> bool:
        return not self.groups and not self.experiments

    @property
    def runs_per_arm(self) -> dict[str, int]:
        """Runs measured before class, per arm."""
        counts: dict[str, int] = defaultdict(int)
        for group in self.groups:
            counts[group.arm] += len(group.before)
        return dict(sorted(counts.items(), key=lambda kv: (ARM_ORDER.get(kv[0], 9), kv[0])))

    @property
    def before_label(self) -> str:
        """'Measured before class: 47 runs per arm'; per arm when the counts differ."""

        def runs(n: int) -> str:
            return f"{n} run{'s' if n != 1 else ''}"

        counts = {arm: n for arm, n in self.runs_per_arm.items() if n}
        if not counts:
            return "Measured before class: no runs"
        if len(set(counts.values())) == 1:
            return f"Measured before class: {runs(next(iter(counts.values())))} per arm"
        return "Measured before class: " + ", ".join(
            f"{arm} {runs(n)}" for arm, n in counts.items()
        )


def _read_json_dir(folder: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    if not folder.is_dir():
        return rows, skipped
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped += 1
            continue
        if isinstance(data, dict):
            rows.append(data)
        else:
            skipped += 1
    return rows, skipped


def exports_signature(exports_dir: Path) -> tuple[tuple[str, int, int], ...]:
    """Cheap change detector: (name, size, mtime_ns) of every scores/experiments file."""
    items: list[tuple[str, int, int]] = []
    for kind in ("scores", "experiments"):
        folder = Path(exports_dir) / kind
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append((f"{kind}/{path.name}", stat.st_size, stat.st_mtime_ns))
    return tuple(sorted(items))


def _layers_label(layers: object) -> str:
    if not isinstance(layers, list) or not layers:
        return "none (bare)"
    return " + ".join(str(layer) for layer in layers)


def _section_of(runs_dir: Path | None, ab_id: object, cache: dict[str, str | None]) -> str | None:
    """The section (demo-N, final) an A/B ran as, from its ab.json; None when unknown."""
    if runs_dir is None or not isinstance(ab_id, str) or "/" in ab_id or not ab_id:
        return None
    if ab_id not in cache:
        try:
            data = json.loads((Path(runs_dir) / ab_id / "ab.json").read_text(encoding="utf-8"))
            cache[ab_id] = data.get("section") if isinstance(data, dict) else None
        except (OSError, ValueError):
            cache[ab_id] = None
    return cache[ab_id]


def _section_verdict(record: dict[str, Any], measure: str) -> bool | None:
    """Passed under a section demo's own measure, from the record's fields (None: one missing)."""
    try:
        return evaluate_primary(measure, record)[1]
    except (KeyError, TypeError):
        return None


def _bundle_sections(bundle: Path | None) -> dict[str, str | None]:
    """ab id -> section for the bundled records (score-sections.json beside the folder)."""
    if bundle is None:
        return {}
    try:
        data = json.loads((Path(bundle).parent / SECTIONS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): (str(v) if v else None) for k, v in data.items()}


def load_report(
    exports_dir: Path,
    *,
    runs_dir: Path | None = None,
    before_class_dir: Path | None = None,
) -> Report:
    """Screen 4's data: the course's own records measured before class (`before_class_dir`; the
    console passes BEFORE_CLASS_DIR, `docs/evidence/scores/`), always shown, and the runs in
    `exports_dir/scores` that are not among them, added next to them as new dots. A record of a
    section demo that has its own measure (Section 3's demo on Feature 4: files outside the allowed
    paths) is judged by that measure, read from the record's fields; its section comes from the
    A/B's ab.json under `runs_dir`, or for bundled records from score-sections.json."""
    from shipharness.ab.demo import section_measure

    bundle = before_class_dir
    sections: dict[str, str | None] = _bundle_sections(bundle)
    exports_dir = Path(exports_dir)
    bundled, skipped_bundle = _read_json_dir(Path(bundle)) if bundle else ([], 0)
    for row in bundled:
        row["__before_class"] = True
    known = {str(r.get("run_id")) for r in bundled}
    exported, skipped = _read_json_dir(exports_dir / "scores")
    scores = bundled + [r for r in exported if str(r.get("run_id")) not in known]
    experiments, skipped_exp = _read_json_dir(exports_dir / "experiments")
    report = Report(skipped=skipped + skipped_exp + skipped_bundle)

    groups: dict[tuple[str, str, str, str], DotGroup] = {}
    by_run: dict[str, bool] = {}  # run_id -> passed, current-version records only
    spent: dict[str, float] = defaultdict(float)
    verified: dict[str, int] = defaultdict(int)
    agree: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in scores:
        if any(key not in record for key in _REQUIRED):
            report.skipped += 1
            continue
        if record.get("referee_version") != REFEREE_VERSION:
            report.older += 1  # scored before the current measurement rules
            continue
        if record.get("constructed"):
            report.constructed += 1  # scripted steps, not a model run (make example-N)
            continue
        if record.get("single_arm"):
            report.single_arm += 1  # no bare run to compare with (make show-N)
            continue
        before_class = bool(record.get("__before_class"))
        arm, variant = str(record["arm"]), str(record["variant"])
        feature = str(record.get("feature_id") or "?")
        passed = bool(record["passed_primary"])
        measure = section_measure(_section_of(runs_dir, record.get("ab_id"), sections), feature)
        label = ""
        if measure:
            own = _section_verdict(record, measure)
            if own is not None:
                passed = own
                label = "; ".join(measure_label(n) for n in primary_fields(measure))
        by_run[str(record["run_id"])] = passed
        layers = _layers_label(record.get("layers"))
        key = (feature, variant, arm, label)
        group = groups.setdefault(key, DotGroup(feature, variant, arm, layers, label))
        group.dots.append(
            Dot(
                str(record["run_id"]),
                passed,
                bool(record.get("recorded", False)),
                bool(record.get("sandboxed", True)),
                before_class,
            )
        )
        report.before_class_runs += before_class
        report.new_runs += not before_class
        with contextlib.suppress(TypeError, ValueError):
            spent[arm] += float(record.get("cost_usd") or 0) + float(
                record.get("review_cost_usd") or 0
            )
        verified[arm] += passed
        if record.get("reviewer_agrees") is not None:
            agree[arm][0] += bool(record["reviewer_agrees"])
            agree[arm][1] += 1
        report.unsandboxed += not bool(record.get("sandboxed", True))
        report.recorded += bool(record.get("recorded", False))

    def arm_key(arm: str) -> tuple[int, str]:
        return (ARM_ORDER.get(arm, 9), arm)

    report.groups = [
        groups[k] for k in sorted(groups, key=lambda k: (k[0], k[1], k[3], *arm_key(k[2])))
    ]
    # Ablation bars come only from experiments run as an ablation batch (metadata.batch
    # "ablation..."), one bar per layer configuration, counted over that experiment's runs.
    ablation: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # passed, total, n_layers
    for item in experiments:
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if not str(meta.get("batch", "")).startswith("ablation"):
            continue
        bar = ablation[_layers_label(meta.get("layers"))]
        bar[2] = len(meta.get("layers") or [])
        for run_id in item.get("rows") or []:
            if str(run_id) in by_run:
                bar[0] += by_run[str(run_id)]
                bar[1] += 1
    report.ablation = [
        Bar(label, v[0], v[1])
        for label, v in sorted(ablation.items(), key=lambda kv: (kv[1][2], kv[0]))
        if v[1]
    ]
    report.costs = [CostRow(arm, spent[arm], verified[arm]) for arm in sorted(spent, key=arm_key)]
    report.reviewer = [AgreementRow(arm, *agree[arm]) for arm in sorted(agree, key=arm_key)]
    for item in experiments:
        if "name" not in item:
            report.skipped += 1
            continue
        report.experiments.append(
            Experiment(
                str(item["name"]),
                safe_url(item.get("url")),
                safe_url(item.get("comparison_url")),
                str(item.get("split", "")),
            )
        )
    report.experiments.sort(key=lambda e: e.name)
    return report
