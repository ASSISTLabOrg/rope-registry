# rope-registry

Shared JSON Schema contract for `model_manifest.json`, the per-model manifest
that [rope-framework](https://github.com/ASSISTLabOrg/ROPE_Framework)'s
forecast pipeline loads from each `data/models/<label>/` directory. This repo
holds the contract as data so rope-framework (consumer) and [rope-dev-tools](https://github.com/ASSISTLabOrg/rope-dev-tools) (producer — model-export tooling) validate manifests against one shared source of truth instead of two hand-maintained copies drifting
apart.

## Layout

```
schemas/manifest-envelope.schema.json   shared top-level manifest fields
schemas/kinds/<kind>.schema.json        per-kind nested block shape
kinds.json                              index of known kinds + stability status
tests/json_test.py                      validates schemas + fixtures
tests/fixtures/                         example valid/invalid manifests
```

## How manifests are validated

A manifest is checked in two separate steps — there is no single combined
schema with `$ref` composing them:

1. Validate the whole manifest document's top-level fields against
   `schemas/manifest-envelope.schema.json`.
2. Validate `manifest[manifest.kind]` against the schema named for that kind
   in `kinds.json` (e.g. `schemas/kinds/ensemble_fusion_decoder.schema.json`).

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
