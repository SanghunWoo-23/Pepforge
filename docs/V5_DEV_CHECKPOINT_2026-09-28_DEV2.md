# Pepforge V5.0.0 — DEV2 End-to-End Simulation Core

## Scope

DEV2 connects the frozen V4 PSB/DockBench baseline to real optional execution backends without fabricating unavailable results.

### Implemented pipeline

```text
PSB ranked conformers (default Top 5)
  -> per-model HADDOCK3 job preparation
  -> real HADDOCK3 subprocess when installed
  -> actual score-table/PDB validation
  -> Top poses per PSB model (default 5)
  -> DockBench coordinate-derived contact analysis
  -> PyMOL PDB/PML export
  -> optional OpenMM minimization/equilibration/production replicates
  -> MDTraj RMSD/Rg/RMSF/contact persistence/clustering/medoids
  -> candidate -> PSB -> pose -> MD/trajectory lineage
```

## Scientific state rules

- Missing HADDOCK3/OpenMM is `BACKEND_UNAVAILABLE`, never a fake result.
- A docking pose exists only if an actual score table refers to an actual non-empty PDB artifact.
- HADDOCK score is not experimental affinity/Kd and Top 1 is not asserted to be native.
- OpenMM standard route hard-blocks non-standard residue names as `PARAMETERIZATION_REQUIRED`.
- Short MD, RMSD stability and cluster occupancy are descriptive evidence, not convergence, folding probability or affinity.
- ESM is an optional sequence representation. Modified chemistry is not silently canonicalized.
- The Pepforge ranker is supervised infrastructure only; no unlabeled runtime data are turned into a production AI score.

## Optional backend installation

Core desktop requirements remain lightweight. `requirements-simulation.txt` contains the optional Python simulation/analysis stack. HADDOCK3 is installed separately in a compatible environment.

## Validation in this checkpoint

- New DEV2 HADDOCK/OpenMM/trajectory/full-pipeline tests: passed.
- V4 PSB structure/chemistry regressions: passed.
- Existing Docking Workbench regressions: passed.
- V2 bridge regressions: passed.
- V4 release gate / verify matrix / release-integrity tests used here: passed.

Real native HADDOCK3 and OpenMM scientific benchmark runs remain mandatory before the V5 package is called scientific-release-ready because those engines are not installed in the build container.
