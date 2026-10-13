# Pepforge V5 optional simulation / prediction backends

Pepforge V5 keeps its desktop/core package usable without large scientific runtimes. Optional backends are detected at runtime. If a backend is missing, Pepforge reports an unavailable/configuration-required state and does **not** replace it with fabricated poses, trajectories, energies, affinity, or structures.

## 1. Core scientific Python packages

From the Pepforge source directory:

```bash
python -m pip install -r requirements-simulation.txt
```

This optional set includes OpenMM, MDAnalysis and MDTraj. The exact platform/GPU build should be selected according to each project's installation guidance when needed.

Check status:

```bash
python pepforge_cli.py v5-backend-status
python scripts/v5_native_smoke.py
```

## 2. HADDOCK3 docking

HADDOCK3 is an external optional docking engine. Install HADDOCK3 separately so the `haddock3` command is available on `PATH`.

Pepforge then performs real subprocess execution and records the detected executable/version, workflow configuration, stdout/stderr, score tables and verified pose artifacts.

```bash
python pepforge_cli.py v5-backend-status
python pepforge_cli.py v5-psb-simulate \
  --psb-meta <PSB_METADATA_JSON> \
  --receptor <RECEPTOR_PDB_OR_MMCIF> \
  --output-dir <OUT>
```

For `hotspot` or `manual` mode provide receptor residues such as `A:10;A:24`.

## 3. OpenMM production MD

When OpenMM is installed, the V5 pipeline can run the canonical-standard route:

- parameterization readiness gate
- solvent/ions
- minimization
- equilibration
- independent production replicates
- DCD/checkpoint/state/final PDB output
- compatible restart/resume
- MDTraj analysis and replicate comparison

Non-standard/modified residues that are not explicitly parameterized are stopped as `PARAMETERIZATION_REQUIRED` rather than silently canonicalized.

The one-click PSB GUI has `Run OpenMM MD after docking`; CLI uses `--run-md`.

## 4. ESM-2 embedding / Pepforge ranker

```bash
python -m pip install -r requirements-esm.txt
```

The lightweight default embedding model is `facebook/esm2_t6_8M_UR50D`. Embeddings are optional features, not folding probabilities.

Train only from an explicitly labelled CSV:

```bash
python pepforge_cli.py v5-train-ranker \
  --csv labelled_rows.csv \
  --output-dir ranker_out \
  --target label \
  --features energy,severe_steric_clashes,mean_rmsd_A,docking_engine_score \
  --sequence-column sequence \
  --row-id-column row_id
```

Add `--use-esm` only when the ESM dependencies/model are available. Sequence-grouped cross-validation is used when a sequence column is supplied.

## 5. ESMFold receptor prediction

Install the optional predictor stack:

```bash
python -m pip install -r requirements-predictors.txt
```

Status and run:

```bash
python pepforge_cli.py v5-predictor-status
python pepforge_cli.py v5-predict-esmfold \
  --sequence ACDEFG... \
  --output-dir receptor_prediction
```

The PSB GUI can also select `Receptor source = ESMFold`. A predicted receptor is then passed to the same docking pipeline. The predicted PDB remains model output, not experimental validation.

## 6. AlphaFold 3 external adapter

Pepforge does not distribute AlphaFold 3 model parameters or databases. Configure a separately installed AF3 environment and provide:

- `run_alphafold.py` path
- model directory
- database directory

Example:

```bash
python pepforge_cli.py v5-predict-af3 \
  --sequence ACDEFG... \
  --output-dir af3_out \
  --run-script /path/to/run_alphafold.py \
  --model-dir /path/to/models \
  --db-dir /path/to/databases
```

Pepforge writes the AF3 JSON input, runs the actual external process, preserves logs, harvests an actual mmCIF result and converts it to PDB for docking. AF3 is an optional advanced adapter rather than a required desktop dependency.

## 7. PyMOL

Docking results are exported as individual complex PDB files plus a generated `.pml` script grouping the peptide-model / pose hierarchy. PyMOL is not required to perform the core export; install it separately to open the review bundle interactively.

## Scientific claim guard

- docking score != measured affinity
- predicted structure != experimentally validated structure
- trajectory population != folding probability
- short MD != equilibrium proof
- RMSD stability != function
- cluster occupancy != binding affinity
- autocorrelation/ESS diagnostic != convergence certificate
