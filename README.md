# rope-registry

Shared JSON Schema contract for `model_manifest.json`, the per-model manifest
that [rope-framework](https://github.com/ASSISTLabOrg/ROPE_Framework)'s
forecast pipeline loads from each `data/models/<label>/` directory, and for
the validation suites used to benchmark those models. This repo holds both
contracts as data so rope-framework (consumer) and
[rope-dev-tools](https://github.com/ASSISTLabOrg/rope-dev-tools) (producer —
model-export and benchmarking tooling) validate against one shared source of
truth instead of hand-maintained copies drifting apart.

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

A manifest is checked in three separate steps — there is no single combined
schema with `$ref` composing them:

1. Validate the whole manifest document's top-level fields against
   `schemas/manifest-envelope.schema.json`. This includes a `validated`
   boolean (required on every manifest — see below) and an optional
   `validation` detail object.
2. Validate `manifest[manifest.kind]` against the schema named for that kind
   in `kinds.json` (e.g. `schemas/kinds/ensemble_fusion_decoder.schema.json`).
3. That kind-specific block contains its own `ic` sub-block (`{"kind": ...,
   "params": {...}}`) — validate `manifest[manifest.kind].ic.params` against
   the schema named for `ic.kind` in `ic_kinds.json` (e.g.
   `schemas/ic/ic_lookup_table.schema.json`). See "Initial condition (IC)
   block" below.

### `validated` and `validation`

Every manifest must include a `validated` boolean, set **manually by a human**
after reviewing that model's full `validation_report.json` (including any
plots) — no automated tooling (e.g. a future rope-dev-tools benchmarking
script) may ever write `true` to this field itself. If `validated` is `true`,
the schema requires a `validation` object be present (enforced via an
`if`/`then` conditional) so a "validated" claim always carries a pointer to
the evidence backing it up: `suite_content_version` (see "Validation suites"
below), `validated_at`, `report_file` (the report's filename, living
alongside the model's other artifacts in its `exported_dir`), and `summary`
(a generic named-scalar map for quick scanning, e.g.
`{"rmse_timeseries_case_003": 4.8e-13}` — key names are check-id/case-id
dependent by convention, not schema-enforced). A model can legitimately be
`validated: false` with no `validation` object at all (freshly trained, not
yet benchmarked).

## Initial condition (IC) block

The IC (initial-condition) mechanism — seeding the latent state at the start
of a forecast — is a first-class, independently-extensible pipeline block
nested inside a model kind's own schema (e.g.
`ensemble_fusion_decoder.schema.json`'s `ic` property), using the same
`{"kind": ..., "params": {...}}` pattern as the top-level manifest `kind` and
validation `checks[].kind`, just applied one level deeper (kind-within-kind).
This exists so a future neural-net-based IC generator can be added later as
pure schema-addition — a new `schemas/ic/<new_kind>.schema.json` +
`ic_kinds.json` entry — with **zero changes** to
`ensemble_fusion_decoder.schema.json` itself.

Today only one IC kind exists: `ic_lookup_table`, a static (F10, Kp)-indexed
lookup table of latent coefficients (bilinear interpolation, nearest-neighbour
fallback outside the grid hull — see `docs/data-sources.md`). Its `params`
are `grid_axes` (the driver columns used as grid axes, e.g. `["f10", "kp"]`)
and `file` (the lookup-table artifact's filename). Putting `file` here means
the IC table is a **per-model artifact**, bundled in the model's
`exported_dir` and referenced by the manifest, rather than purely the global
`paths.ic_csv` server-config path `docs/data-sources.md` currently documents
— different models may have different latent dimensions, so the table is
genuinely model-specific. (`docs/data-sources.md` and `rope.conf`'s
`paths.ic_csv` will need reconciling with this separately — not addressed by
this schema.)

`ic_lookup_table` is marked `"stable"` in `ic_kinds.json` immediately, since
the underlying lookup-table behavior is real and already running — "stable"
tracks whether the pipeline behavior is real, not whether manifest-schema
validation is wired into a consumer's loader (nothing does that yet, for any
kind or IC kind).

### Adding a new IC kind

1. Add `schemas/ic/<new_kind>.schema.json`.
2. Add an entry to `ic_kinds.json` with `"status": "draft"`.
3. Once the consuming code actually implements the kind, flip `"status"` to
   `"stable"`.

## Validation suites

A validation suite is a grid: **cases** (specific space-weather time windows
— start, end, description) crossed with **checks** (error metrics and/or
plots run against those windows). Both axes are independently extensible:
adding a new check *kind* (a new type of plot or metric) never touches case
data, and adding a new **case never requires a schema change at all** — the
case shape has no per-case kind/type field, so this holds by construction.

One caveat: a check that omits `applies_to` implicitly expands to cover any
newly-added case. If that new case doesn't supply the `data_refs` a check
needs, the suite will only fail to load (see cross-checks below), not fail
at case-authoring time — when adding a case, double-check existing checks'
`applies_to` scoping if the new case lacks data a given check requires.

Checks are validated the same two-stage way as manifest kinds: the whole
suite document's top-level fields (`schema_version`, `content_version`,
`cases`, `checks`) validate against `schemas/validation-suite.schema.json`;
each `checks[i].params` is then validated separately against
`schemas/checks/<kind>.schema.json`, resolved via `check_kinds.json`.

Three check kinds exist today, all `"draft"` in `check_kinds.json` since no
consumer implements them yet (flip to `"stable"` once a benchmarking tool
implements a kind end-to-end):

- `lonlat_density_plot` — a lon/lat density map at one or more altitudes.
  Pure visualization: no threshold, `value`/`unit`/`passed` are always
  `null` in results.
- `rmse_timeseries` — RMSE of model output against a reference/truth data
  source over a case's full duration.
- `satellite_lineout` — a trace plot of model vs. satellite-measured values
  along a satellite's track, plus a scalar RMSE-along-track.

Both `rmse_timeseries` and `satellite_lineout` take a `variable` param
(`"density"` or `"uncertainty"`, default `"density"`) so a future check can
score uncertainty calibration without a schema change, and an optional
`threshold` object (`{"max": ..., "min": ...}`, at least one required) —
pass requires `value <= max` (if present) and `value >= min` (if present),
so upper bound, lower bound, or a bounded range are all expressible with the
same field.

### The `data_refs` cross-check

A check's `params.truth_ref` names a key expected in a case's `data_refs`
map (not a path itself — the actual path is resolved per-case). Whether
every case in that check's resolved `applies_to` set actually supplies that
key spans two sibling array elements and isn't expressible as a local JSON
Schema rule — the same category as the already-documented "decoder altitude
stages must tile with no gaps" constraint in
`ensemble_fusion_decoder.schema.json`. This is enforced instead by (1) a
static pytest test in this repo
(`tests/validation_suite_test.py::test_checks_data_refs_present_on_applicable_cases`)
for fast dev-time feedback, and (2) a runtime pre-flight check in whatever
tool actually runs a suite, which must fail loudly before spending any
compute if a required ref turns out to be missing.

### `content_version` vs `schema_version`

`schema_version` tracks the JSON *shape* of the suite document;
`content_version` is a separate, human-bumped counter tracking the suite's
*content* (the actual `cases`/`checks`), incremented whenever that content
changes even though `schema_version` stays put. A manifest's
`validation.suite_content_version` is compared against a suite's current
`content_version` to detect whether a model was validated against a
since-changed suite. `content_version` is only meaningful for comparison
between two suite documents that share the same `schema_version` — if a
future `schema_version` bump ever happens, treat any `content_version`
comparison across that boundary as "needs re-validation", not as a
numerically comparable value.

### Plot file location

Plots produced by a check (e.g. `lonlat_density_plot`, `satellite_lineout`)
live under a `plots/` subfolder inside the model's `exported_dir` (e.g.
`plots/case_003_check_001_lonlat_400km.png`), not flat alongside the model's
own artifacts (`base_model_*.onnx` etc.) — this is a path convention, not a
schema constraint, since `validation-report.schema.json`'s `plots` entries
are already relative path strings. The manifest does **not** get its own
plot-paths list — the report's per-result `plots` arrays are the single
source of truth, so there's no second list that can drift out of sync when a
report is regenerated.

### Adding a new check kind

1. Add `schemas/checks/<new_kind>.schema.json`.
2. Add an entry to `check_kinds.json` with `"status": "draft"`.
3. Once a consuming tool actually implements dispatch for the kind, flip
   `"status"` to `"stable"`.

### A note on kind registries

`kinds.json`, `check_kinds.json`, and `ic_kinds.json` are independent
registries with no enforced namespacing between them — a `kind` string is
only guaranteed unique within its own family.

## Consuming this repo

rope-framework and rope-dev-tools pull this in via CMake's `FetchContent`
(or an equivalent file fetch for non-CMake tooling), pinned to a git tag —
the same pattern already used for `nlohmann_json`/`CLI11` in
rope-framework's `CMakeLists.txt`. Each consumer pins the tag independently
on its own schedule; a version bump is a deliberate, reviewed pin change.

## Adding a new kind

1. Add `schemas/kinds/<new_kind>.schema.json`.
2. Add an entry to `kinds.json` with `"status": "draft"`.
3. Once the consuming C++ dispatch (rope-framework's `pipeline_registry.cpp`)
   actually implements the kind, flip `"status"` to `"stable"`.

rope-framework has a drift-detection test asserting its compiled
`known_kinds()` exactly matches the `"stable"` entries here — don't mark a
kind `"stable"` until the consuming code is ready, or that test will fail.

## Running tests locally

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## License

MPL-2.0, see [LICENSE](LICENSE).
