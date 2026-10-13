# Pepforge V5 DEV4 — PFEE diversity + Offline-first resource manager

## Implemented

- PFEE candidate-pool accounting with explicit severe-clash rejection.
- Quality-preserving greedy RMSD separation for representative Top-5 selection.
- No forced one-per-family diversity; insufficiently separated sets fall back explicitly to established PSB quality order.
- Existing PDE requested-structure priority remains upstream of the PFEE representative pass.
- Interaction Only bypasses PFEE diversity preference and preserves structure-agnostic quality ranking.
- Offline-first local resource manifest (`Pepforge_LocalResources/manifests/installed_resources.json`).
- Execution modes: `offline`, `auto`, `online_enhanced`.
- PSB GUI exposes execution mode; offline ESMFold calls use local-files-only behavior.
- CLI adds `v5-resource-status` and execution-mode/resource-root controls.

## Scientific boundary

PFEE RMSD diversity is a search-quality criterion only. It is not a conformational population, folding probability, free energy, native-state assignment, affinity estimate, or experimental validation. Environment metadata does not become an invented constant-pH/solvent energy term.

## Validation

- Selected regression: **59 passed / 0 failed**.
- Release gate: **25 passed / 0 failed**, 346 Python files compiled, 0 compile errors, 0 stale hits, 0 bad artifacts.
- Real PSB smoke (`EEMQRR`, evidence_balanced): 24/24 usable candidates, 5 ranked PDB exports, PFEE representative status `threshold_met`, minimum observed pairwise RMSD 1.3274 Å for that run. This is a software/search smoke result, not a biological structure claim.

## Native validation still required before final V5 scientific release claim

- Real HADDOCK3 protein-peptide benchmark on target installation.
- Real OpenMM canonical complex three-replicate benchmark on target installation.
- Windows/WSL fresh-unzip backend installation smoke.
- Domain-appropriate labelled ranker dataset validation.
