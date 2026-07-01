# rope-registry

Shared JSON Schema contract for `model_manifest.json` and validation suites, used by [rope-framework](https://github.com/ASSISTLabOrg/rope-framework) (consumer) and [rope-dev-tools](https://github.com/ASSISTLabOrg/rope-dev-tools) (producer).

## Layout

```
schemas/manifest-envelope.schema.json   shared top-level manifest fields
schemas/kinds/<kind>.schema.json        per-kind nested block shape
schemas/ic/<kind>.schema.json           per-IC-kind params shape (nested inside a kind's "ic" block)
kinds.json                              index of known model kinds + stability status
ic_kinds.json                           index of known IC kinds + stability status

schemas/validation-suite.schema.json    shared cases[] / checks[] envelope
schemas/checks/<kind>.schema.json       per-check-kind params shape
schemas/validation-report.schema.json   output shape of a suite run
check_kinds.json                        index of known check kinds + stability status

tests/json_test.py                      validates manifest schemas + fixtures
tests/ic_block_test.py                  validates the IC block + ic_kinds.json + fixtures
tests/validation_suite_test.py          validates validation-suite/report schemas + fixtures
tests/fixtures/                         example valid/invalid documents
```

## How manifests are validated

Three steps:

1. Validate the whole document's top-level fields against `schemas/manifest-envelope.schema.json`.
2. Validate `manifest[manifest.kind]` against `schemas/kinds/<kind>.schema.json`, resolved via `kinds.json`.
3. Validate `manifest[manifest.kind].ic.params` against `schemas/ic/<kind>.schema.json`, resolved via `ic_kinds.json`.

### `validated` and `validation`

`validated` (boolean) is required on every manifest, set manually by a human. If `validated` is `true`, `validation` is required (`if`/`then` conditional): `suite_content_version`, `validated_at`, `report_file`, `summary` (named-scalar map, e.g. `{"rmse_timeseries_case_003": 4.8e-13}`). `validated: false` with no `validation` object is valid.

## Initial condition (IC) block

A model kind's schema (e.g. `ensemble_fusion_decoder.schema.json`) has an `ic` property: `{"kind": ..., "params": {...}}`, resolved against `ic_kinds.json`.

Current kind: `ic_lookup_table` — `params.grid_axes` (driver columns used as grid axes) and `params.file` (lookup-table artifact filename, lives in the model's `exported_dir`, supersedes the global `paths.ic_csv` config path in `docs/data-sources.md`). Status `"stable"` in `ic_kinds.json`.

### Adding a new IC kind

1. Add `schemas/ic/<new_kind>.schema.json`.
2. Add an entry to `ic_kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once the consuming code implements the kind.

## Validation suites

A grid of **cases** (`id`, `description`, `start`, `end`, optional `data_refs`, optional `tags`) crossed with **checks** (`id`, `kind`, optional `applies_to`, `params`).

Checks validate in two stages: the suite envelope (`schemas/validation-suite.schema.json`), then `checks[i].params` against `schemas/checks/<kind>.schema.json`, resolved via `check_kinds.json`. `applies_to` restricts a check to the listed case ids; omitted means all cases.

Check kinds:

- `lonlat_density_plot` — lon/lat density map at given altitudes. `value`/`unit`/`passed` are always `null`.
- `rmse_timeseries` — RMSE against a `data_refs`-referenced truth source over a case's duration.
- `satellite_lineout` — trace plot + RMSE-along-track against a satellite track.

`rmse_timeseries`/`satellite_lineout` params: `truth_ref` (a `data_refs` key name), `variable` (`"density"` or `"uncertainty"`, default `"density"`), `threshold` (`{"max": ..., "min": ...}`, at least one required; pass requires `value <= max` and `value >= min`).

### The `data_refs` cross-check

Enforced by `tests/validation_suite_test.py::test_checks_data_refs_present_on_applicable_cases` and by whatever tool runs a suite at runtime — not by JSON Schema.

### `content_version` vs `schema_version`

`schema_version` tracks document shape. `content_version` tracks content (`cases`/`checks`), bumped on any content edit. A manifest's `validation.suite_content_version` is compared against a suite's current `content_version`. Only comparable between suites sharing the same `schema_version`.

### Plot file location

Plots live under `plots/` inside the model's `exported_dir`, listed in the report's `plots` array. Not duplicated in the manifest.

### Adding a new check kind

1. Add `schemas/checks/<new_kind>.schema.json`.
2. Add an entry to `check_kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once a consuming tool implements dispatch for the kind.

### Kind registries

`kinds.json`, `check_kinds.json`, `ic_kinds.json` are independent — a `kind` string is only unique within its own family.

## Consuming this repo

rope-framework and rope-dev-tools pull this in via CMake's `FetchContent` (or an equivalent file fetch for non-CMake tooling), pinned to a git tag. Each consumer pins independently.

## Adding a new kind

1. Add `schemas/kinds/<new_kind>.schema.json`.
2. Add an entry to `kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once rope-framework's `pipeline_registry.cpp` implements the kind.

rope-framework has a drift-detection test asserting compiled `known_kinds()` matches the `"stable"` entries here.

## Running tests locally

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## License

MPL-2.0, see [LICENSE](LICENSE).
