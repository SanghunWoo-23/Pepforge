#!/usr/bin/env python3
"""
Predict supervised_score for a hotspot full CSV.

Example:
python scripts/predict_supervised_score.py \
  --model outputs/supervised_model.joblib \
  --features-csv outputs/hotspot_full_xxx.csv \
  --out outputs/supervised_features.csv
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import joblib

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--features-csv", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    bundle = joblib.load(args.model)
    model = bundle["model"]
    features = bundle["features"]

    df = pd.read_csv(args.features_csv)
    missing = [c for c in ["record_name", "model_position"] + features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[features].apply(pd.to_numeric, errors="coerce")
    if hasattr(model, "predict_proba"):
        score = model.predict_proba(X)[:, 1]
    else:
        score = model.predict(X)

    out_df = pd.DataFrame({
        "record_name": df["record_name"],
        "position": df["model_position"],
        "supervised_score": score
    })
    out_df = out_df.dropna(subset=["position"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    print("Saved supervised features:", out)

if __name__ == "__main__":
    main()
