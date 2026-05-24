from __future__ import annotations
from pathlib import Path
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def train_supervised(csv_path: str | Path, target: str, model_path: str | Path, task: str = "regression") -> dict:
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=[target])
    if len(df) < 5:
        raise ValueError("Need at least 5 rows with target values for a first model.")
    y = df[target]
    X = df.drop(columns=[target])
    # Remove free-text columns that are not useful at first pass.
    drop_cols = [c for c in X.columns if c.lower() in {"issue_note", "note", "date", "run_id"}]
    X = X.drop(columns=drop_cols, errors="ignore")
    cat_cols = [c for c in X.columns if X[c].dtype == "object"]
    num_cols = [c for c in X.columns if c not in cat_cols]
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols), ("num", "passthrough", num_cols)])
    model = RandomForestClassifier(n_estimators=200, random_state=42) if task == "classification" else RandomForestRegressor(n_estimators=200, random_state=42)
    pipe = Pipeline([("pre", pre), ("model", model)])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)
    metrics = {"rows": len(df), "target": target, "task": task}
    if task == "classification":
        metrics["accuracy"] = float(accuracy_score(y_test, pred))
    else:
        metrics["mae"] = float(mean_absolute_error(y_test, pred))
        metrics["r2"] = float(r2_score(y_test, pred)) if len(y_test) > 1 else None
    joblib.dump(pipe, model_path)
    return metrics


def detect_anomalies(csv_path: str | Path, out_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    num = df.select_dtypes(include="number").fillna(0)
    if num.empty:
        raise ValueError("No numeric columns for anomaly detection.")
    model = IsolationForest(contamination="auto", random_state=42)
    score = model.fit_predict(num)
    result = df.copy()
    result["anomaly_flag"] = score
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    return result
