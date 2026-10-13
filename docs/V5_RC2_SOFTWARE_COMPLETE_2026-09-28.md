# Pepforge V5.0.0 RC2 — Software Complete / Native Validation Pending

## Implemented through RC2
- Existing V4 public functionality and chemistry/lineage contracts preserved.
- PFEE environment-aware search planning, candidate-pool audit, RMSD-diverse representative selection.
- PFEE adaptive diversity resampling using real ETKDG coordinate generation, optimization, re-analysis and re-ranking.
- Offline / Auto / Online Enhanced local-resource policy.
- HADDOCK3 real adapter path, verified scored-pose harvesting only, DockBench/PyMOL integration.
- OpenMM canonical route with explicit modified-chemistry parameterization block, replicates and restart support.
- MDTraj trajectory analysis and replicate diagnostics.
- Optional ESM/ESMFold/AF3 adapters with explicit unavailable/configuration states.
- Supervised ranker with grouped CV, dataset audit, naive baseline comparison, model card and research-only promotion state unless externally validated.
- Aggregate V5 release-readiness report that keeps native scientific blockers explicit.

## RC2 validation in this build environment
- V5-focused + selected compatibility regression: 70 passed / 0 failed.
- Release gate: 25 passed / 0 failed.
- Python compile: 348 files / 0 errors.
- Real PSB smoke (EEMQRR): 32 usable candidates, 5 representatives, minimum observed pairwise RMSD 1.37 A, no diversity fallback.
- Full pytest was attempted but exceeded the environment execution limit at 14%; no failures were observed before termination.

## Not yet valid to claim
RC2 is software-complete in this environment, not a natively validated scientific release. HADDOCK3 and OpenMM are not installed here, no production ranker dataset/model was provided, and target Windows/WSL fresh-unzip native smoke has not run. No missing backend is replaced with fabricated output.
