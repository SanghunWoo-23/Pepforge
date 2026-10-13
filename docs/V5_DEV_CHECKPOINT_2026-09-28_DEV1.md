# Pepforge V5.0.0 DEV1 — PSB / Docking Workbench / lightweight AI checkpoint

## Baseline

Frozen source baseline: Pepforge V4.0.0 Public Source Final R14 (2026-09-22).
The original transfer bundle checksum was verified before creating this working copy.

## User target translated into the V5 pipeline

```text
Peptide construct
 -> generate/sample N conformers
 -> PSB quality filtering/ranking
 -> up to 5 peptide models
 -> receptor PDB/mmCIF
 -> real docking independently for every retained peptide model
 -> up to 5 verified poses per model
 -> up to 25 real complex structures
 -> Docking Workbench interaction review
 -> PyMOL review package
 -> optional selected-complex MD/trajectory workflow
```

The default future UI should expose this as one orchestrated action while retaining Advanced PSB and Advanced Docking Workbench controls.

## DEV1 implemented

### 1. PSB V5 orchestration core

Added `peptiforg_core/psb_v5_orchestrator.py`.

- Reads real existing PSB ranked PDB artifacts from PSB metadata JSON.
- Validates receptor PDB/mmCIF input.
- Copies audited inputs into a run folder.
- Creates one real *prepared job record* per PSB model.
- Carries candidate -> PSB structure lineage.
- Records requested pose limit (default 5/model).
- Does **not** create pose PDBs or scores before an actual docking engine runs.
- Exports JSON/CSV run plan and PyMOL lineage review template.

### 2. Optional small ESM-2 embedding adapter

Added `peptiforg_core/esm_peptide_embedding.py` and `requirements-esm.txt`.

Default model reference: `facebook/esm2_t6_8M_UR50D` through Hugging Face Transformers.

Chemistry policy:
- canonical L sequence: allowed;
- terminal/non-residue modifier: canonical backbone can be embedded only with an explicit "modifier not represented" disclosure;
- D residue, non-natural residue, linker or side-chain-modified residue: direct ESM embedding is blocked rather than silently canonicalized.

No fallback/random embedding is generated if dependencies/model weights are unavailable.

### 3. Lightweight Pepforge ranker foundation

Added `peptiforg_core/psb_ai_ranker.py`.

- Extracts numeric PSB conformer evidence.
- Can append a sequence embedding to feature vectors.
- Implements a small supervised `RandomForestRegressor` advisory model.
- Requires an explicit labeled target and a minimum number of labeled rows.
- Output is an advisory score for the declared target, never a folding probability/Kd/activity claim.

Important design fact: an ESM sequence embedding is identical across conformers of the same peptide. Therefore ESM alone cannot rank conformers from one sequence. The ranker must combine it with conformer-specific geometry/MD/docking evidence and becomes most useful across many peptide sequences.

## Validation

- New DEV1 + selected V4 PSB/Docking regression: 26 passed / 0 failed.
- Release-gate/source-integrity targeted regression: 17 passed / 0 failed.
- Python `compileall`: clean.
- A full 463-test run was started and showed no failure in the completed portion, but exceeded the execution window before completion; it is not recorded as a completed full regression.

## Next implementation order

1. Real docking backend interface + availability/version detection.
2. HADDOCK3 reference adapter (or another validated protein-peptide backend if Windows/runtime constraints require it).
3. Real pose artifact validation and per-model Top-5 pose parsing.
4. Reuse Docking Workbench interaction analysis as an internal service.
5. PyMOL 5 x 5 complex review exporter.
6. OpenMM canonical-system backend with hard parameterization gate.
7. MD trajectory analysis and then one-click PSB workflow UI.
8. Build/train Pepforge AI ranker only after an explicit training dataset/target contract is established.
