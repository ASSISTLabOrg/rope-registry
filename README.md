# rope-registry

Shared JSON Schema contract for `model_manifest.json`, used by [rope-framework](https://github.com/ASSISTLabOrg/rope-framework) (consumer) and [rope-dev-tools](https://github.com/ASSISTLabOrg/rope-dev-tools) (producer). Validation-suite/check-kind validation used to live here too — it's now plain Python inside `rope-dev-tools` (function signatures + inline checks), since suites are internal, hand-authored config only `rope-dev-tools` itself ever reads, not a cross-repo contract.

## Layout

```
schemas/manifest-envelope.schema.json   shared top-level manifest fields (incl. the "ic" block)
schemas/kinds/<kind>.schema.json        per-kind nested block shape
schemas/ic/<kind>.schema.json           per-IC-kind params shape (nested inside the top-level "ic" block)
pipeline_kinds.json                     index of known model kinds + stability status
ic_kinds.json                           index of known IC kinds + stability status

tests/json_test.py                      validates manifest schemas + fixtures
tests/ic_block_test.py                  validates the IC block + ic_kinds.json + fixtures
tests/fixtures/                         example valid/invalid documents
```

## How manifests are validated

Three steps:

1. Validate the whole document's top-level fields (including `ic`) against `schemas/manifest-envelope.schema.json`.
2. Validate `manifest[manifest.kind]` against `schemas/kinds/<kind>.schema.json`, resolved via `pipeline_kinds.json`.
3. Validate `manifest.ic.params` against `schemas/ic/<kind>.schema.json`, resolved via `ic_kinds.json`.

### `validated` and `validation`

`validated` (boolean) is required on every manifest, set manually by a human. If `validated` is `true`, `validation` is required (`if`/`then` conditional): `suite_content_version`, `validated_at`, `report_file`, `summary` (every check's own output, keyed by check id — check kinds and their validation live in `rope-dev-tools`, not here). `validated: false` with no `validation` object is valid.

## Initial condition (IC) block

The manifest envelope (`schemas/manifest-envelope.schema.json`) has a top-level `ic` property: `{"kind": ..., "params": {...}}`, resolved against `ic_kinds.json`. It's kind-agnostic — sibling to `driver_columns`/`driver_source`/`grid`, not nested inside any model kind's own block — since IC sourcing is a cross-kind concern, the same shape of problem as model-backend selection.

Current kind: `ic_lookup_table` — `params.grid_axes` (driver columns used as grid axes) and `params.file` (lookup-table artifact filename, lives in the model's `exported_dir`, supersedes the global `paths.ic_csv` config path in `docs/data-sources.md`). Status `"stable"` in `ic_kinds.json`.

### Adding a new IC kind

1. Add `schemas/ic/<new_kind>.schema.json`.
2. Add an entry to `ic_kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once the consuming code implements the kind.

### Kind registries

`pipeline_kinds.json`, `ic_kinds.json` are independent — a `kind` string is only unique within its own family.

## Consuming this repo

rope-framework and rope-dev-tools pull this in via CMake's `FetchContent` (or an equivalent file fetch for non-CMake tooling), pinned to a git tag. Each consumer pins independently.

## Adding a new kind

1. Add `schemas/kinds/<new_kind>.schema.json`.
2. Add an entry to `pipeline_kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once rope-framework's `pipeline_registry.cpp` implements the kind.

rope-framework has a drift-detection test asserting compiled `known_kinds()` matches the `"stable"` entries here.

## Running tests locally

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## License

MPL-2.0, see [LICENSE](LICENSE).
