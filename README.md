# rope-registry

Shared JSON Schema contract for `model_manifest.json` and validation suites, used by [rope-framework](https://github.com/ASSISTLabOrg/rope-framework) (consumer) and [rope-dev-tools](https://github.com/ASSISTLabOrg/rope-dev-tools) (producer).

## Layout

```
schemas/manifest-envelope.schema.json   shared top-level manifest fields
schemas/kinds/<kind>.schema.json        per-kind nested block shape
schemas/ic/<kind>.schema.json           per-IC-kind params shape (nested inside a kind's "ic" block)
kinds.json                              index of known model kinds + stability status
ic_kinds.json                           index of known IC kinds + stability status

schemas/validation-suite.schema.json    trivial checks[] envelope (each check is just {id, kind, ...})
schemas/checks/<kind>.schema.json       per-check-kind field shape — independent of every other kind
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

`validated` (boolean) is required on every manifest, set manually by a human. If `validated` is `true`, `validation` is required (`if`/`then` conditional): `suite_content_version`, `validated_at`, `report_file`, `summary` (every check's own output, keyed by check id — see "Validation suites" below). `validated: false` with no `validation` object is valid.

## Initial condition (IC) block

A model kind's schema (e.g. `stacked_ensemble.schema.json`) has an `ic` property: `{"kind": ..., "params": {...}}`, resolved against `ic_kinds.json`.

Current kind: `ic_lookup_table` — `params.grid_axes` (driver columns used as grid axes) and `params.file` (lookup-table artifact filename, lives in the model's `exported_dir`, supersedes the global `paths.ic_csv` config path in `docs/data-sources.md`). Status `"stable"` in `ic_kinds.json`.

### Adding a new IC kind

1. Add `schemas/ic/<new_kind>.schema.json`.
2. Add an entry to `ic_kinds.json` with `"status": "draft"`.
3. Flip to `"stable"` once the consuming code implements the kind.

## Validation suites

A validation suite is a **flat list of checks** — no grid, no cases, no cross-referencing. Each check is just `{"id": ..., "kind": ..., ...whatever fields that kind needs}`. Kinds are not required to agree with each other on field names, time representation, or output shape — `lonlat_density_plot` might use `time_point`/`time_window_hours`; `rmse_timeseries` uses `start`/`end`. Each `kind` maps to exactly one function in `rope-dev-tools`, and that kind's own schema (resolved via `check_kinds.json`) validates everything on the check object *besides* `id`/`kind`.

Checks validate in two stages: the suite envelope (`schemas/validation-suite.schema.json` — just requires every check have `id` + `kind`), then the check's remaining fields against `schemas/checks/<kind>.schema.json`, resolved via `check_kinds.json`.

Check kinds today:

- `lonlat_density_plot` — lon/lat density map at given altitudes, at a single `time_point` (forecasting a `time_window_hours`-long window ending there). Plot-only.
- `rmse_timeseries` — RMSE against a `truth_csv` file over `start`/`end`.
- `satellite_lineout` — trace plot + RMSE-along-track against a `satellite_track_csv` file over `start`/`end`.

Each of `truth_csv`/`satellite_track_csv` is a plain path (resolved relative to the suite JSON's own directory) — there is no shared "data_refs" indirection layer; every kind that needs a truth-data file just names that field itself.

### Report output is generic too

A validation report's `results[]` entries are `{"id", "kind", "output"}` — `output` is whatever that kind's function returned, any JSON-serializable value, no shape shared across kinds (a plot-only kind might return `{"plots": [...]}`; a metric kind might return `{"value", "unit", "passed"}`). A dict output containing `"passed": false` is treated as a check failure by CLI tooling; anything else is informational only.

### `content_version` vs `schema_version`

`schema_version` tracks document shape. `content_version` tracks content (`checks`), bumped on any content edit. A manifest's `validation.suite_content_version` is compared against a suite's current `content_version`. Only comparable between suites sharing the same `schema_version`.

### Plot file location

Plots live under `plots/` inside the model's `exported_dir`, listed wherever a check's own `output` references them. Not duplicated in the manifest.

### Adding a new check kind

Exactly two steps — nothing else needs to change:

1. Write the function in `rope-dev-tools` (whatever fields it needs, whatever it returns) and register it under a kind name.
2. Add `schemas/checks/<new_kind>.schema.json` describing those same fields here, plus an entry to `check_kinds.json` with `"status": "draft"`. Flip to `"stable"` once the function is implemented and in use.

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
