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
def ic_kinds():
    return _load_json(REPO_ROOT / "ic_kinds.json")


@pytest.fixture(scope="module")
def envelope_schema():
    return _load_json(SCHEMAS_DIR / "manifest-envelope.schema.json")


@pytest.fixture(scope="module")
def kind_schema():
    return _load_json(SCHEMAS_DIR / "kinds" / "stacked_ensemble.schema.json")


@pytest.fixture(scope="module")
def ic_lookup_table_schema():
    return _load_json(SCHEMAS_DIR / "ic" / "ic_lookup_table.schema.json")


def _ic_kind_schema(kind_name: str, ic_kinds: list) -> dict:
    for entry in ic_kinds:
        if entry["kind"] == kind_name:
            return _load_json(REPO_ROOT / entry["schema"])
    raise KeyError(f"unknown ic kind: {kind_name}")


# ---------------------------------------------------------------------------
# ic_kinds.json shape
# ---------------------------------------------------------------------------

def test_ic_kinds_json_is_valid_array(ic_kinds):
    assert isinstance(ic_kinds, list)
    assert len(ic_kinds) > 0
    for entry in ic_kinds:
        assert set(entry.keys()) == {"kind", "schema", "status"}
        assert (REPO_ROOT / entry["schema"]).is_file()


def test_ic_kinds_json_kinds_have_unique_names(ic_kinds):
    names = [entry["kind"] for entry in ic_kinds]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Schema legality + examples
# ---------------------------------------------------------------------------

def test_ic_lookup_table_schema_is_legal_jsonschema(ic_lookup_table_schema):
    Draft202012Validator.check_schema(ic_lookup_table_schema)


def test_ic_lookup_table_schema_examples_validate(ic_lookup_table_schema):
    validator = Draft202012Validator(ic_lookup_table_schema)
    for example in ic_lookup_table_schema["examples"]:
        validator.validate(example)


# ---------------------------------------------------------------------------
# Three-stage resolution: envelope -> manifest[kind] -> manifest[kind].ic.params
# ---------------------------------------------------------------------------

def test_valid_manifest_ic_block_resolves_and_validates(envelope_schema, kind_schema, ic_kinds):
    manifest = _load_json(FIXTURES_DIR / "valid_manifest.json")
    Draft202012Validator(envelope_schema).validate(manifest)

    kind_block = manifest["stacked_ensemble"]
    Draft202012Validator(kind_schema).validate(kind_block)

    ic_block = kind_block["ic"]
    ic_schema = _ic_kind_schema(ic_block["kind"], ic_kinds)
    Draft202012Validator(ic_schema).validate(ic_block["params"])


def test_invalid_kind_missing_ic_fails(kind_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_kind_missing_ic.json")
    with pytest.raises(ValidationError):
        Draft202012Validator(kind_schema).validate(manifest["stacked_ensemble"])


def test_invalid_ic_missing_grid_axes_fails(ic_lookup_table_schema):
    manifest = _load_json(FIXTURES_DIR / "invalid_ic_missing_grid_axes.json")
    ic_block = manifest["stacked_ensemble"]["ic"]
    with pytest.raises(ValidationError):
        Draft202012Validator(ic_lookup_table_schema).validate(ic_block["params"])


def test_invalid_ic_bad_kind_rejected(kind_schema, ic_kinds):
    manifest = _load_json(FIXTURES_DIR / "invalid_ic_bad_kind.json")
    kind_block = manifest["stacked_ensemble"]
    # Passes JSON Schema — "kind" is just a string at this level.
    Draft202012Validator(kind_schema).validate(kind_block)
    # Fails the pytest-level cross-check against ic_kinds.json, same situation
    # as an unknown manifest.kind or check.kind value.
    known_kinds = {entry["kind"] for entry in ic_kinds}
    assert kind_block["ic"]["kind"] not in known_kinds
