#!/usr/bin/env python3
"""
Train a simple supervised hotspot classifier from a feature CSV.

Input CSV must contain:
- label column, default: is_hotspot
- numeric feature columns

Example:
python scripts/train_supervised_model.py \
  --train-csv examples/example_training_labels.csv \
  --model-out outputs/supervised_model.joblib
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

DEFAULT_FEATURES = [
    "rule_score",
    "esm_embedding_score",
    "esm_unpredictability_score",
    "esm_mutation_sensitivity",
    "conservation_score",
    "structure_score",
]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train-csv", required=True)
    p.add_argument("--model-out", required=True)
    p.add_argument("--label-col", default="is_hotspot")
    p.add_argument("--features", nargs="*", default=DEFAULT_FEATURES)
    args = p.parse_args()

    df = pd.read_csv(args.train_csv)
    missing = [c for c in [args.label_col] + args.features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[args.features].apply(pd.to_numeric, errors="coerce")
    y = df[args.label_col].astype(int)

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced"))
    ])
    model.fit(X, y)

    if len(set(y)) > 1 and len(y) >= 6:
        cv = min(3, y.value_counts().min())
        if cv >= 2:
            scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
            print("CV ROC-AUC:", scores.mean(), "+/-", scores.std())

    out = Path(args.model_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": args.features, "label_col": args.label_col}, out)
    print("Saved model:", out)

if __name__ == "__main__":
    main()
