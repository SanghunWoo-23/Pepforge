> Superseded for the latest workflow-refined integration by `SPPS_V5_WORKFLOW_REFINED_VALIDATION_2026-09-01.md`. This file records the earlier SPPS V5 integration checkpoint.

# Pepforge V4.0.0 — SPPS Planner V5.0.0 Integration Validation

Date: 2026-09-01
Status: validated development snapshot; Pepforge V4.0.0 remains work in progress and is **not** the final GitHub V4.0.0 release.

## Integration scope

- Pepforge suite version remains `4.0.0`.
- Embedded Public/Data-Sanitized synthesis component is SPPS Planner `5.0.0`.
- Existing internal Python namespace `spps_v4_gui` is retained only for backward import compatibility.
- SPPS V5 Public decision-support, empirical cleavage, model-registry, issue/workup and synchronized engine paths are integrated.
- LOT Number controls and Batch Manager are not exposed on the Pepforge operator surface.
- Private/local experimental history, private seeds, user-local ML data, lot/batch records are not bundled.
- Pepforge result-bundle export behavior remains active.

## Cys rule contract

- Positive manual cleavage-equivalent override: use exactly as entered.
- Otherwise, Cys present: `TFA eq = 100 × Cys count`, with no peptide-length addition.
- Cys-free: use the public-safe length baseline.
- This equivalents rule does not itself choose scavenger/cocktail composition; cocktail choice remains evidence/SOP driven.

## Regression/validation results

The root and application test files were executed in bounded chunks because several PSB/structure tests are computationally heavier when run as one process.

- Test collection: 273 tests.
- Result across the complete collected set: **272 passed, 1 skipped, 0 unresolved failures**.
- Added/adapted SPPS V5 regression group: 29 passed, 1 skipped.
- Existing selected SPPS/integration/source-integrity group: 62 passed, 1 skipped.
- PSB helix geometry: 2/2 passed.
- PDE intent-aware PSB selection: 4/4 passed.
- Result-bundle contract: 6/6 passed.
- Structure/simulation upgrade: 5/5 passed.
- Runtime validation: 2/2 passed.
- Full-package audit: 2/2 passed.
- Regression audit: 2/2 passed.
- Release integrity: 2/2 passed.
- Release verify matrix: 14/14 checks passed.
- Release gate: 23/23 checks passed; 254 Python files compiled; 0 compile errors; 0 stale-name findings; 0 packaging-artifact findings.
- Additional Hot Spot Finder application tests: 5/5 passed.

## Public boundary checks

- `apps/spps_planner_app/data/actual_runs.csv` contains the header only.
- `apps/spps_planner_app/data/experimental_seed/` contains the Public README only.
- Active Pepforge suite version is `4.0.0`; embedded SPPS engine/UI metadata is `5.0.0`.
- No active Pepforge `4.0.1` suite-version marker was found in current release-facing metadata.
- Batch implementation modules may remain as dormant compatibility source, but the Batch tab and LOT controls are not built/exposed by the integrated Pepforge UI.

## Claim boundary

These checks validate software integration, packaging, source integrity and regression behavior. They do not establish experimental peptide yield, affinity, native structure, MD convergence, or biological efficacy.
