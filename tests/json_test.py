import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def _load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pipeline_kinds():
    return _load_json(REPO_ROOT / "pipeline_kinds.json")


@pytest.fixture(scope="module")
def envelope_schema():
    return _load_json(SCHEMAS_DIR / "manifest-envelope.schema.json")


@pytest.fixture(scope="module")
def kind_schema():
    return _load_json(SCHEMAS_DIR / "kinds" / "stacked_ensemble.schema.json")


def test_pipeline_kinds_json_is_valid_array(pipeline_kinds):
    assert isinstance(pipeline_kinds, list)
    assert len(pipeline_kinds) > 0
    for entry in pipeline_kinds:
        assert set(entry.keys()) == {"kind", "schema", "status"}
        assert (REPO_ROOT / entry["schema"]).is_file()


def test_pipeline_kinds_json_kinds_have_unique_names(pipeline_kinds):
    names = [entry["kind"] for entry in pipeline_kinds]
    assert len(names) == len(set(names))


def test_envelope_schema_is_legal_jsonschema(envelope_schema):
    Draft202012Validator.check_schema(envelope_schema)


def test_kind_schema_is_legal_jsonschema(kind_schema):
    Draft202012Validator.check_schema(kind_schema)


def test_envelope_schema_examples_validate(envelope_schema):
    validator = Draft202012Validator(envelope_schema)
    for example in envelope_schema["examples"]:
        validator.validate(example)


def test_kind_schema_examples_validate(kind_schema):
    validator = Draft202012Validator(kind_schema)
    for example in kind_schema["examples"]:
        validator.validate(example)


def test_valid_manifest_fixture_validates_against_both_schemas(envelope_schema, kind_schema):
    manifest = _load_json(FIXTURES_DIR / "valid_manifest.json")
    Draft202012Validator(envelope_schema).validate(manifest)
    Draft202012Validator(kind_schema).validate(manifest["stacked_ensemble"])


def test_invalid_envelope_missing_field_fails(envelope_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_envelope_missing_field.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope_schema).validate(manifest)


def test_invalid_envelope_wrong_type_fails(envelope_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_envelope_wrong_type.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope_schema).validate(manifest)


def test_invalid_kind_missing_field_fails(kind_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_kind_missing_field.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(manifest["stacked_ensemble"])


def test_invalid_kind_bad_enum_fails(kind_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_kind_bad_enum.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(manifest["stacked_ensemble"])


def test_valid_manifest_with_validation_fixture_validates(envelope_schema, kind_schema):
    manifest = _load_json(FIXTURES_DIR / "valid_manifest_with_validation.json")
    Draft202012Validator(envelope_schema).validate(manifest)
    Draft202012Validator(kind_schema).validate(manifest["stacked_ensemble"])


def test_invalid_envelope_missing_validated_fails(envelope_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_envelope_missing_validated.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope_schema).validate(manifest)


def test_invalid_envelope_validation_bad_type_fails(envelope_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_envelope_validation_bad_type.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope_schema).validate(manifest)


def test_invalid_envelope_validated_true_no_validation_fails(envelope_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_envelope_validated_true_no_validation.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(envelope_schema).validate(manifest)


def test_validated_false_without_validation_object_is_allowed(envelope_schema):
    """Exercises the if/then conditional in the direction that must NOT fail:
    validated:false with no validation object (freshly trained, not yet benchmarked)."""
    manifest = _load_json(FIXTURES_DIR / "valid_manifest.json")
    assert manifest["validated"] is False
    assert "validation" not in manifest
    Draft202012Validator(envelope_schema).validate(manifest)
