"""Library templates must be valid in their own formats.

The reference course shipped a feature-list template that its own skill's
schema rejected. This test is the guard against that class of drift: the
canonical template must always validate against the canonical schema.
"""

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "library" / "templates"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads((TEMPLATES / "feature_list.schema.json").read_text(encoding="utf-8"))


def test_schema_itself_is_valid(schema):
    jsonschema.Draft202012Validator.check_schema(schema)

def test_feature_list_template_validates(schema):
    instance = json.loads((TEMPLATES / "feature_list.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(instance)


def test_passing_without_evidence_is_rejected(schema):
    instance = {
        "project": "x",
        "updated": "2026-08-27",
        "features": [
            {
                "id": "a",
                "title": "A",
                "behavior": "does A",
                "verification": "./verify.sh a",
                "status": "passing",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_unknown_status_is_rejected(schema):
    instance = {
        "project": "x",
        "updated": "2026-08-27",
        "features": [
            {
                "id": "a",
                "title": "A",
                "behavior": "does A",
                "verification": "./verify.sh a",
                "status": "done",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_all_json_templates_parse():
    for path in TEMPLATES.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def _is_declared_seeded_defect(path):
    """A fixture may violate the canonical dialect only when it lives under a
    unit's fixtures/ and that unit's SPEC.md declares its directory in a
    Seeded defects section; anything else is a real dialect drift."""
    if "fixtures" not in path.parts:
        return False
    for parent in path.parents:
        spec = parent / "SPEC.md"
        if spec.is_file():
            text = spec.read_text(encoding="utf-8")
            return "Seeded defects" in text and path.parent.name in text
    return False


def test_every_fixture_feature_list_validates(schema):
    """Curriculum fixtures named feature_list.json must be real instances of
    the canonical artifact, not lookalikes in a divergent dialect. The one
    escape is a deliberately broken fixture declared as a seeded defect in
    its unit's SPEC.md (e.g. a stale workspace a doctor must catch)."""
    found = sorted(REPO_ROOT.glob("lectures/**/feature_list.json")) + sorted(
        REPO_ROOT.glob("projects/**/feature_list.json")
    )
    assert found, "expected at least one fixture feature_list.json in the curriculum"
    validated = 0
    for path in found:
        instance = json.loads(path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft202012Validator(schema).validate(instance)
            validated += 1
        except jsonschema.ValidationError:
            if not _is_declared_seeded_defect(path):
                raise
    assert validated, "every curriculum feature_list.json was exempted; that cannot be right"


def test_init_sh_is_executable():
    mode = (TEMPLATES / "init.sh").stat().st_mode
    assert mode & 0o111, "library/templates/init.sh must be executable"
