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


def test_every_fixture_feature_list_validates(schema):
    """Curriculum fixtures named feature_list.json must be real instances of
    the canonical artifact, not lookalikes in a divergent dialect."""
    found = sorted(REPO_ROOT.glob("lectures/**/feature_list.json")) + sorted(
        REPO_ROOT.glob("projects/**/feature_list.json")
    )
    assert found, "expected at least one fixture feature_list.json in the curriculum"
    for path in found:
        instance = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_init_sh_is_executable():
    mode = (TEMPLATES / "init.sh").stat().st_mode
    assert mode & 0o111, "library/templates/init.sh must be executable"
