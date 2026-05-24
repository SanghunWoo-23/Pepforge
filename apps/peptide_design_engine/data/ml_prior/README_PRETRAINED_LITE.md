# Pepforge Pretrained-Lite ML Prior

This folder contains a small **pretrained-lite** ML prior baseline for Pepforge.

Important scientific limitation:

- This is **not** a validated binding-affinity model.
- This is **not** a full PDB-scale trained protein-peptide model.
- This is a lightweight, local, reproducible baseline trained from bundled pseudo-interface-prior features and heuristic labels.
- It exists so the engine can already load an actual model file and produce an optional `ml_prior_score`.
- Future versions can replace this model with PDB-derived protein-peptide interface training data.

Included files:

```text
peptide_ml_prior_training_data.csv
pepforge_ml_prior_baseline.joblib
train_ml_prior_baseline.py
predict_ml_prior.py
ML_PRIOR_MODEL_CARD.txt
```

Validation on the internal synthetic/heuristic split:

```text
R2  = 0.889
MAE = 0.040
Train size = 1287
Test size  = 322
```

Recommended wording:

```text
PDB/interface-inspired pretrained-lite prior
structure-informed candidate prioritization scaffold
hypothesis-generating ML prior score
```

Avoid claiming:

```text
validated binding prediction
experimental affinity prediction
docking replacement
```
