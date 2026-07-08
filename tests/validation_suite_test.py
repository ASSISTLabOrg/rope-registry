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
def check_kinds():
    return _load_json(REPO_ROOT / "check_kinds.json")


@pytest.fixture(scope="module")
def suite_schema():
    return _load_json(SCHEMAS_DIR / "validation-suite.schema.json")


@pytest.fixture(scope="module")
def report_schema():
    return _load_json(SCHEMAS_DIR / "validation-report.schema.json")


def _check_kind_schema(kind_name: str, check_kinds: list) -> dict:
    for entry in check_kinds:
        if entry["kind"] == kind_name:
            return _load_json(REPO_ROOT / entry["schema"])
    raise KeyError(f"unknown check kind: {kind_name}")


# ---------------------------------------------------------------------------
# check_kinds.json shape
# ---------------------------------------------------------------------------

def test_check_kinds_json_is_valid_array(check_kinds):
    assert isinstance(check_kinds, list)
    assert len(check_kinds) > 0
    for entry in check_kinds:
        assert set(entry.keys()) == {"kind", "schema", "status"}
        assert (REPO_ROOT / entry["schema"]).is_file()


def test_check_kinds_json_kinds_have_unique_names(check_kinds):
    names = [entry["kind"] for entry in check_kinds]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Schema legality + examples
# ---------------------------------------------------------------------------

def test_suite_schema_is_legal_jsonschema(suite_schema):
    Draft202012Validator.check_schema(suite_schema)


def test_report_schema_is_legal_jsonschema(report_schema):
    Draft202012Validator.check_schema(report_schema)


@pytest.mark.parametrize("kind_name", ["lonlat_density_plot", "rmse_timeseries", "satellite_lineout"])
def test_check_schema_is_legal_jsonschema(kind_name, check_kinds):
    schema = _check_kind_schema(kind_name, check_kinds)
    Draft202012Validator.check_schema(schema)


def test_suite_schema_examples_validate(suite_schema):
    validator = Draft202012Validator(suite_schema)
    for example in suite_schema["examples"]:
        validator.validate(example)


def test_report_schema_examples_validate(report_schema):
    validator = Draft202012Validator(report_schema)
    for example in report_schema["examples"]:
        validator.validate(example)


@pytest.mark.parametrize("kind_name", ["lonlat_density_plot", "rmse_timeseries", "satellite_lineout"])
def test_check_schema_examples_validate(kind_name, check_kinds):
    schema = _check_kind_schema(kind_name, check_kinds)
    validator = Draft202012Validator(schema)
    for example in schema["examples"]:
        validator.validate(example)


# ---------------------------------------------------------------------------
# Fixture: valid_validation_suite.json — each check's own fields (minus
# id/kind) validate against its kind's schema, resolved via check_kinds.json.
# ---------------------------------------------------------------------------

def test_valid_validation_suite_fixture_validates(suite_schema, check_kinds):
    suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    Draft202012Validator(suite_schema).validate(suite)
    for check in suite["checks"]:
        kind_schema = _check_kind_schema(check["kind"], check_kinds)
        fields = {k: v for k, v in check.items() if k not in ("id", "kind")}
        Draft202012Validator(kind_schema).validate(fields)


def test_valid_validation_report_fixture_validates(report_schema):
    report = _load_json(FIXTURES_DIR / "valid_validation_report.json")
    Draft202012Validator(report_schema).validate(report)


# ---------------------------------------------------------------------------
# Invalid fixtures — JSON-Schema-catchable
# ---------------------------------------------------------------------------

def test_invalid_suite_missing_required_field_fails(suite_schema):
    suite = _load_json(FIXTURES_DIR / "invalid_suite_missing_required_field.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(suite_schema).validate(suite)


def test_invalid_check_params_bad_altitude_fails(check_kinds):
    suite = _load_json(FIXTURES_DIR / "invalid_check_params.json")
    check = next(c for c in suite["checks"] if c["id"] == "check_bad_altitude")
    kind_schema = _check_kind_schema(check["kind"], check_kinds)
    fields = {k: v for k, v in check.items() if k not in ("id", "kind")}
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(fields)


def test_invalid_check_params_missing_truth_csv_fails(check_kinds):
    suite = _load_json(FIXTURES_DIR / "invalid_check_params.json")
    check = next(c for c in suite["checks"] if c["id"] == "check_missing_truth_csv")
    kind_schema = _check_kind_schema(check["kind"], check_kinds)
    fields = {k: v for k, v in check.items() if k not in ("id", "kind")}
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(fields)


def test_invalid_check_params_bad_threshold_shape_fails(check_kinds):
    suite = _load_json(FIXTURES_DIR / "invalid_check_params.json")
    check = next(c for c in suite["checks"] if c["id"] == "check_bad_threshold_shape")
    kind_schema = _check_kind_schema(check["kind"], check_kinds)
    fields = {k: v for k, v in check.items() if k not in ("id", "kind")}
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(fields)


def test_invalid_report_wrong_type_fails(report_schema):
    report = _load_json(FIXTURES_DIR / "invalid_report_wrong_type.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(report_schema).validate(report)


# ---------------------------------------------------------------------------
# Cross-checks — NOT jsonschema.ValidationError checks. Whole-document,
# cross-referencing rules (duplicate ids, unknown kinds) that JSON Schema
# cannot express as a local constraint. Enforced here as plain Python
# assertions instead — this is now a much smaller set than before, since
# checks no longer share a data_refs/applies_to/time-shape convention to
# cross-check against.
# ---------------------------------------------------------------------------

def _duplicate_check_ids(suite: dict) -> bool:
    ids = [c["id"] for c in suite["checks"]]
    return len(ids) != len(set(ids))


def _unknown_check_kinds(suite: dict, check_kinds: list) -> list:
    known = {entry["kind"] for entry in check_kinds}
    return [check["id"] for check in suite["checks"] if check["kind"] not in known]


def test_duplicate_check_ids_rejected(check_kinds):
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert not _duplicate_check_ids(valid_suite)

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _duplicate_check_ids(broken_suite)


def test_unknown_check_kind_rejected(check_kinds):
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert _unknown_check_kinds(valid_suite, check_kinds) == []

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _unknown_check_kinds(broken_suite, check_kinds) != []
