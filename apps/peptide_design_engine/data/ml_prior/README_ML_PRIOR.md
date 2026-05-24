# Pepforge ML Prior Data Folder

This folder contains the optional PDB/interface-derived prior scaffold.

## Files

- `pdb_interface_prior_sample.csv`  
  A small human-readable sample table. It is a placeholder/statistical prior format, not a validated binding model.

## CSV columns

```text
type,key,score,source,note
```

Supported `type` values:

```text
motif
residue
pair
composition
```

## Interpretation

The prior score is intended for candidate prioritization only.
It should be described as:

```text
PDB/interface-derived statistical prior
structure-informed candidate prioritization
hypothesis-generating ML prior score
```

Avoid describing it as:

```text
validated binding predictor
experimental affinity predictor
docking replacement
```

## Future extension

A future training pipeline may replace this CSV with features derived from:

- PDB protein-peptide complexes
- protein-protein interface residue contact maps
- BioLiP-style interaction annotations
- AF3/PRODIGY-derived labels
- internal experimental peptide screening data
