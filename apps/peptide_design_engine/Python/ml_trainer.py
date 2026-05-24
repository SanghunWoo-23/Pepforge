#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight continual-learning surrogate for Peptide Design Engine.

No scikit-learn or xgboost dependency is required. The model is a transparent
ridge-regression surrogate saved as JSON, suitable for EXE packaging and small
datasets. It is not a final biological validation model; use it to prioritize
new candidates from accumulated AF3/PRODIGY/experimental labels.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

AA = "ACDEFGHIKLMNPQRSTVWY"
HYDRO = set("AVILMFWY")
POS = set("KRH")
NEG = set("DE")
POLAR = set("STNQYC")
AROM = set("FWYH")
FEATURE_NAMES = [
    "bias", "length", "hydro_frac", "pos_frac", "neg_frac", "polar_frac", "arom_frac",
    "charge", "gly_frac", "pro_frac", "cys_frac", "acidic_frac", "basic_frac",
]


def read_csv(path: str | Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(x: Any) -> float | None:
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def clean_sequence(seq: str) -> str:
    return "".join(c for c in str(seq).upper() if c in AA)


def sequence_features(seq: str) -> List[float]:
    s = clean_sequence(seq)
    n = max(1, len(s))
    return [
        1.0,
        len(s) / 50.0,
        sum(c in HYDRO for c in s) / n,
        sum(c in POS for c in s) / n,
        sum(c in NEG for c in s) / n,
        sum(c in POLAR for c in s) / n,
        sum(c in AROM for c in s) / n,
        (sum(c in POS for c in s) - sum(c in NEG for c in s)) / 10.0,
        s.count("G") / n,
        s.count("P") / n,
        s.count("C") / n,
        sum(c in "DE" for c in s) / n,
        sum(c in "KRH" for c in s) / n,
    ]


def choose_sequence(row: Dict[str, Any]) -> str:
    return str(row.get("clean_sequence") or row.get("sequence") or row.get("peptide_sequence") or "")


def train_from_csv(training_db: str, models_dir: str = "models", label_col: str = "experimental_binding", alpha: float = 1.0) -> str:
    rows = read_csv(training_db)
    X, y, used = [], [], []
    for r in rows:
        label = to_float(r.get(label_col))
        seq = choose_sequence(r)
        if label is None or not clean_sequence(seq):
            continue
        X.append(sequence_features(seq))
        y.append(label)
        used.append(r.get("candidate_id", ""))
    if len(X) < 3:
        raise ValueError(f"Need at least 3 labeled rows for '{label_col}', found {len(X)}.")
    Xn = np.asarray(X, dtype=float)
    yn = np.asarray(y, dtype=float)
    y_mean = float(np.mean(yn))
    y_std = float(np.std(yn) or 1.0)
    yz = (yn - y_mean) / y_std
    reg = alpha * np.eye(Xn.shape[1])
    reg[0, 0] = 0.0
    coef = np.linalg.solve(Xn.T @ Xn + reg, Xn.T @ yz)
    pred = Xn @ coef * y_std + y_mean
    rmse = float(np.sqrt(np.mean((pred - yn) ** 2)))
    model = {
        "model_type": "ridge_regression_json_v1",
        "label_col": label_col,
        "feature_names": FEATURE_NAMES,
        "coef": coef.tolist(),
        "y_mean": y_mean,
        "y_std": y_std,
        "train_rows": len(X),
        "train_rmse": rmse,
        "notes": "Lightweight surrogate for ranking; not experimental proof.",
    }
    out = Path(models_dir)
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "surrogate_model.json"
    model_path.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(model_path)


def load_model(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def predict_sequence(seq: str, model: Dict[str, Any]) -> float:
    x = np.asarray(sequence_features(seq), dtype=float)
    coef = np.asarray(model["coef"], dtype=float)
    return float((x @ coef) * float(model.get("y_std", 1.0)) + float(model.get("y_mean", 0.0)))


def rerank_rows(rows: List[Dict[str, Any]], model_path: str | Path, blend_weight: float = 0.25) -> List[Dict[str, Any]]:
    model = load_model(model_path)
    if not rows:
        return []
    preds = [predict_sequence(r.get("clean_sequence") or r.get("sequence") or "", model) for r in rows]
    p_min, p_max = min(preds), max(preds)
    s_max = max([float(r.get("total_score") or 0) for r in rows] + [1.0])
    out = []
    for r, p in zip(rows, preds):
        rr = dict(r)
        pred_norm = 0.5 if math.isclose(p_max, p_min) else (p - p_min) / (p_max - p_min)
        base_norm = float(rr.get("total_score") or 0) / s_max
        rr["trained_ml_label"] = model.get("label_col", "")
        rr["trained_ml_prediction"] = p
        rr["trained_ml_prediction_norm"] = pred_norm
        rr["trained_ml_blended_score"] = (1.0 - blend_weight) * base_norm + blend_weight * pred_norm
        out.append(rr)
    out.sort(key=lambda x: float(x.get("trained_ml_blended_score") or 0), reverse=True)
    for i, r in enumerate(out, 1):
        r["trained_ml_rank"] = i
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--training-db", default="data/training_data.csv")
    ap.add_argument("--models-dir", default="models")
    ap.add_argument("--label", default="experimental_binding")
    args = ap.parse_args()
    print(train_from_csv(args.training_db, args.models_dir, args.label))
