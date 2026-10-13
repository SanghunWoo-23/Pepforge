# Pepforge V5.0.0 — DEV3 PFEE Environment v1

## Scope

This checkpoint begins the P1 PFEE work on top of RC1 Native-Ready without changing the frozen V4 behavior contracts.

## Implemented

- Added `peptiforg_core.pfee_v1` as the first explicit PFEE module boundary.
- Normalizes pH, ionic strength, temperature and solvent/environment context.
- Adds a canonical-L-only Henderson–Hasselbalch charge proxy for search diagnostics.
- Modified/non-canonical chemistry is never converted into a canonical surrogate for charge estimation.
- A high absolute canonical charge proxy under low ionic strength can expand the ETKDG sampling multiplier by one step (capped), but does **not** change fold-family priority.
- `build_structure()` now records `pfee_search_plan` in PSB metadata and uses its sampling budget.
- Existing `evidence_guided_family_plan` remains intact and remains the family-priority source of truth in PFEE v1.

## Scientific boundary

PFEE v1 environment handling is a search-context heuristic, not constant-pH MD, explicit-solvent energetics, a protonation microstate solver, a free-energy model, or a folding-probability model.

The charge proxy is used only to decide whether to broaden conformer sampling. It is not used as an affinity score or as evidence that one fold is more probable than another.

## Validation

- New PFEE environment contract tests: 5 passed.
- PFEE + existing sequence-aware Top-5/helix regression batch: 11 passed.
- V5/PFEE focused integration batch (PFEE, PSB orchestration, OpenMM/trajectory contract, ESM ranker, docking exports/anchors): 17 passed.
- Direct `build_structure("EEMQRR")` smoke produced five ranked conformers and serialized the PFEE plan.
- A full-suite pytest run was attempted and exceeded the execution time limit after progressing without observed failures; no full-suite-pass claim is made for DEV3 in this environment.

## Next

1. Add PFEE torsion/state proposal abstraction so seed generation is no longer embedded only in the legacy PSB path.
2. Add explicit diversity-aware candidate pool staging before final Top-5 selection while preserving PDE intent semantics.
3. Keep native HADDOCK3/OpenMM target-machine benchmark as P0 release validation; DEV3 does not change that release boundary.
