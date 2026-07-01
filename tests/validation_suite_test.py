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
# Fixture: valid_validation_suite.json
# ---------------------------------------------------------------------------

def test_valid_validation_suite_fixture_validates(suite_schema, check_kinds):
    suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    Draft202012Validator(suite_schema).validate(suite)
    for check in suite["checks"]:
        kind_schema = _check_kind_schema(check["kind"], check_kinds)
        Draft202012Validator(kind_schema).validate(check["params"])


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
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(check["params"])


def test_invalid_check_params_missing_truth_ref_fails(check_kinds):
    suite = _load_json(FIXTURES_DIR / "invalid_check_params.json")
    check = next(c for c in suite["checks"] if c["id"] == "check_missing_truth_ref")
    kind_schema = _check_kind_schema(check["kind"], check_kinds)
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(check["params"])


def test_invalid_check_params_bad_threshold_shape_fails(check_kinds):
    suite = _load_json(FIXTURES_DIR / "invalid_check_params.json")
    check = next(c for c in suite["checks"] if c["id"] == "check_bad_threshold_shape")
    kind_schema = _check_kind_schema(check["kind"], check_kinds)
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(check["params"])


def test_invalid_report_wrong_type_fails(report_schema):
    report = _load_json(FIXTURES_DIR / "invalid_report_wrong_type.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(report_schema).validate(report)


# ---------------------------------------------------------------------------
# Cross-checks — NOT jsonschema.ValidationError checks. These are whole-document,
# cross-referencing rules (duplicate ids, applies_to resolution, data_refs
# presence, kind-registry membership) that JSON Schema cannot express as a
# local constraint — same category as the decoder-altitude-tiling constraint
# already documented as unenforceable in ensemble_fusion_decoder.schema.json.
# Enforced here as plain Python assertions instead.
# ---------------------------------------------------------------------------

def _duplicate_case_ids(suite: dict) -> bool:
    ids = [c["id"] for c in suite["cases"]]
    return len(ids) != len(set(ids))


def _unknown_applies_to_ids(suite: dict) -> list:
    case_ids = {c["id"] for c in suite["cases"]}
    missing = []
    for check in suite["checks"]:
        for case_id in check.get("applies_to", []):
            if case_id not in case_ids:
                missing.append((check["id"], case_id))
    return missing


def _unknown_check_kinds(suite: dict, check_kinds: list) -> list:
    known = {entry["kind"] for entry in check_kinds}
    return [check["id"] for check in suite["checks"] if check["kind"] not in known]


def _missing_data_refs(suite: dict) -> list:
    """For every check with a params.truth_ref, every case it resolves to (via
    applies_to, defaulting to all cases) must supply that key in data_refs."""
    cases_by_id = {c["id"]: c for c in suite["cases"]}
    all_case_ids = list(cases_by_id.keys())
    missing = []
    for check in suite["checks"]:
        truth_ref = check["params"].get("truth_ref")
        if truth_ref is None:
            continue
        resolved_ids = check.get("applies_to", all_case_ids)
        for case_id in resolved_ids:
            case = cases_by_id.get(case_id)
            if case is None:
                continue  # caught separately by _unknown_applies_to_ids
            if truth_ref not in case.get("data_refs", {}):
                missing.append((check["id"], case_id, truth_ref))
    return missing


def test_duplicate_case_ids_rejected():
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert not _duplicate_case_ids(valid_suite)

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _duplicate_case_ids(broken_suite)


def test_unknown_applies_to_case_rejected():
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert _unknown_applies_to_ids(valid_suite) == []

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _unknown_applies_to_ids(broken_suite) != []


def test_unknown_check_kind_rejected(check_kinds):
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert _unknown_check_kinds(valid_suite, check_kinds) == []

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _unknown_check_kinds(broken_suite, check_kinds) != []


def test_checks_data_refs_present_on_applicable_cases():
    valid_suite = _load_json(FIXTURES_DIR / "valid_validation_suite.json")
    assert _missing_data_refs(valid_suite) == []

    broken_suite = _load_json(FIXTURES_DIR / "invalid_suite_cross_checks.json")
    assert _missing_data_refs(broken_suite) != []
