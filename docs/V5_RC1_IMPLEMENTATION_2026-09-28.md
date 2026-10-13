# Pepforge V5.0.0 RC1 — implementation status (2026-09-28)

## Scope

V5 RC1 preserves the frozen V4.0.0 Public Source Final R14 behavior and adds a real-backend-ready PSB simulation pipeline.  No backend is reported as successful unless an actual engine/process and actual output artifacts are validated.

## End-to-end PSB workflow

```text
Peptide construct
  -> PSB N-conformer generation
  -> PSB structural filtering / clustering
  -> representative Top 5 peptide conformers
  -> receptor PDB/mmCIF (or optional external predictor output)
  -> HADDOCK3 protein-peptide docking per conformer
  -> verified Top 5 scored poses per conformer (max 25 complexes)
  -> DockBench interaction/contact export
  -> PyMOL PDB + PML review bundle
  -> optional OpenMM minimization/equilibration/independent production replicates
  -> MDTraj trajectory analysis
  -> RMSD / Rg / RMSF / contacts / explicit-H H-bonds / DSSP / drift / autocorrelation-ESS / clusters / medoids
```

The default UI path exposes this as `RUN FULL PSB SIMULATION`.  Advanced users can still use the existing Docking Workbench/import paths independently.

## Real docking boundary

- Detects an installed `haddock3` executable and records the detected engine/version information.
- Creates a real HADDOCK3 workflow for each selected PSB conformer.
- Supports blind docking and guided docking using explicit receptor residue AIR restraints.
- Accepts receptor PDB or mmCIF; mmCIF is explicitly converted to PDB before HADDOCK preparation.
- Captures stdout/stderr and preserves the run directory.
- A pose is accepted only when a real HADDOCK score table references a real PDB artifact.
- Missing HADDOCK3 is `BACKEND_UNAVAILABLE`; no fallback score or pose is fabricated.

## Real MD boundary

The OpenMM adapter is optional and runs only when OpenMM is installed.

- canonical/standard-residue readiness gate
- unsupported/non-standard residue -> `PARAMETERIZATION_REQUIRED`
- system preparation, solvation and ions
- energy minimization
- equilibration
- independent production replicates (default 3)
- DCD trajectory, checkpoint, state XML and final PDB
- compatible restart/resume from checkpoint and persisted system/topology
- completed replicate reuse rather than silently rerunning/merging data

Short simulation time, RMSD stability and cluster occupancy are never converted into equilibrium, folding-probability, affinity or functional claims.

## Trajectory evidence

MDTraj analysis now includes:

- RMSD and radius of gyration frame series
- RMSF
- receptor-peptide contact persistence
- explicit-hydrogen Baker-Hubbard-style H-bond persistence
- simplified DSSP secondary-structure fractions
- first-half vs second-half RMSD drift
- descriptive RMSD/Rg autocorrelation and effective-sample-size estimates
- clustering and medoid PDBs
- replicate-level agreement/disagreement summaries

Autocorrelation/ESS is a sampling diagnostic, not a convergence certificate.

## Pepforge AI ranker

The V5 ranker is deliberately smaller than an AlphaFold-class structure generator.

- optional ESM-2 sequence embeddings
- numeric PSB / MD / docking evidence features
- supervised RandomForest ranker
- requires an explicit numeric target; no unlabeled pseudo-target is invented
- sequence-grouped cross-validation when a sequence column is provided, preventing conformers of the same peptide from leaking across train/test folds
- writes CV predictions, MAE/RMSE/R2/Spearman diagnostics, feature importance, dataset SHA-256 and a model card
- training data are explicit inputs; local/private runtime results are never silently added to a public training set

The ranker score is advisory for its declared supervised target.  It is not folding probability, Kd, affinity or experimental activity unless an appropriate measured target was explicitly supplied and separately validated.

## Optional receptor predictors

### ESMFold

Pepforge provides an optional `transformers` adapter for `facebook/esmfold_v1`.  It generates a real predicted PDB only when the required runtime/model is available.  Otherwise the backend is reported unavailable.

### AlphaFold 3

Pepforge provides an external adapter that:

- writes AlphaFold 3 JSON input using the current `alphafold3` dialect contract used by this RC
- requires the user-provided AF3 run script, model directory and database directory
- launches the actual external process
- preserves stdout/stderr
- harvests an actual mmCIF output and converts it to PDB for the downstream docking pipeline

Pepforge does not redistribute AlphaFold 3 model parameters.

## CLI

```text
pepforge_cli.py v5-backend-status
pepforge_cli.py v5-predictor-status
pepforge_cli.py v5-predict-esmfold ...
pepforge_cli.py v5-predict-af3 ...
pepforge_cli.py v5-train-ranker ...
pepforge_cli.py v5-psb-simulate ...
```

## Release boundary

RC1 is software-complete for the above adapters and failure paths.  A scientific/native-backend release claim still requires documented native runs on the target installation environment with real HADDOCK3 and OpenMM.  The build container used for RC1 does not contain those two engines, so native scientific benchmark success is intentionally not claimed here.
