from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import warnings

import pandas as pd
from pandas.api.types import is_numeric_dtype


OUTCOME_COLUMNS = {
    "actual_yield_percent", "actual_purity_percent",
    "failure_flag", "doubling_required",
}
NON_FEATURE_COLUMNS = {
    "feature_schema_version", "work_item_id", "project", "peptide",
    "sequence", "review_status", "review_revision", "included",
    "exclusion_reason", "reviewed_at", "issue_note", "note", "date",
    "run_id",
}


def _classification_values(series: pd.Series) -> pd.Series:
    mapping = {
        "true": True, "1": True, "yes": True, "y": True,
        "false": False, "0": False, "no": False, "n": False,
    }
    if series.dtype == object:
        converted = series.astype(str).str.strip().str.lower().map(mapping)
        if converted.notna().all():
            return converted.astype(bool)
    return series


def train_supervised(
    csv_path: str | Path,
    target: str,
    model_path: str | Path,
    task: str = "regression",
) -> dict[str, Any]:
    import joblib
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    df = pd.read_csv(csv_path)
    if "included" in df.columns:
        included = df["included"]
        if included.dtype == object:
            included = included.astype(str).str.lower().isin({"true", "1", "yes"})
        else:
            included = included.fillna(False).astype(bool)
        df = df[included]
    if target not in df.columns:
        raise ValueError(f"Target column not found: {target}")
    df = df.dropna(subset=[target]).copy()
    if len(df) < 5:
        raise ValueError("Need at least 5 included rows with target values for a first model.")
    if task == "regression":
        df[target] = pd.to_numeric(df[target], errors="coerce")
        df = df.dropna(subset=[target])
    elif task == "classification":
        df[target] = _classification_values(df[target])
        if df[target].nunique(dropna=True) < 2:
            raise ValueError("Classification requires at least two observed classes.")
    else:
        raise ValueError(f"Unsupported task: {task}")
    if len(df) < 5:
        raise ValueError("Need at least 5 valid included target values after type validation.")

    y = df[target]
    drop = (OUTCOME_COLUMNS | NON_FEATURE_COLUMNS) - {target}
    X = df.drop(columns=[target, *sorted(drop)], errors="ignore")
    X = X.replace([float("inf"), float("-inf")], pd.NA)
    X = X.dropna(axis=1, how="all")
    if X.empty:
        raise ValueError("No usable feature columns remain after review filtering.")
    num_cols = [column for column in X.columns if is_numeric_dtype(X[column])]
    cat_cols = [column for column in X.columns if column not in num_cols]
    transformers = []
    if cat_cols:
        transformers.append((
            "cat",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("encode", OneHotEncoder(handle_unknown="ignore")),
            ]),
            cat_cols,
        ))
    if num_cols:
        transformers.append((
            "num",
            Pipeline([("impute", SimpleImputer(strategy="median"))]),
            num_cols,
        ))
    pre = ColumnTransformer(transformers)
    model = (
        RandomForestClassifier(n_estimators=300, random_state=42)
        if task == "classification"
        else RandomForestRegressor(n_estimators=300, random_state=42)
    )
    pipe = Pipeline([("pre", pre), ("model", model)])
    stratify = None
    if task == "classification" and y.value_counts().min() >= 2:
        stratify = y
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=stratify,
    )
    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)
    metrics: dict[str, Any] = {
        "rows": len(df), "train_rows": len(X_train), "test_rows": len(X_test),
        "feature_count": len(X.columns), "target": target, "task": task,
    }
    if task == "classification":
        metrics["accuracy"] = float(accuracy_score(y_test, pred))
        metrics["class_count"] = int(y.nunique())
    else:
        metrics["mae"] = float(mean_absolute_error(y_test, pred))
        metrics["r2"] = float(r2_score(y_test, pred)) if len(y_test) > 1 else None
    bundle = {
        "pipeline": pipe,
        "feature_columns": list(X.columns),
        "target": target,
        "task": task,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    destination = Path(model_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    joblib.dump(bundle, temporary)
    temporary.replace(destination)
    return metrics


def predict_supervised(model_path: str | Path, rows: pd.DataFrame) -> Any:
    import joblib

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Setting the shape on a NumPy array has been deprecated",
            category=DeprecationWarning,
        )
        loaded = joblib.load(model_path)
    if isinstance(loaded, dict) and "pipeline" in loaded:
        pipeline = loaded["pipeline"]
        columns = list(loaded.get("feature_columns", []))
        frame = rows.copy()
        for column in columns:
            if column not in frame:
                frame[column] = pd.NA
        frame = frame[columns]
    else:
        pipeline = loaded
        frame = rows
    return pipeline.predict(frame)


def predict_supervised_details(model_path: str | Path, rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Return predictions plus genuine classifier probability when supported."""
    import joblib

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        loaded = joblib.load(model_path)
    pipeline = loaded["pipeline"] if isinstance(loaded, dict) and "pipeline" in loaded else loaded
    frame = rows.copy()
    columns = list(loaded.get("feature_columns", [])) if isinstance(loaded, dict) else []
    if columns:
        for column in columns:
            if column not in frame:
                frame[column] = pd.NA
        frame = frame[columns]
    predictions = pipeline.predict(frame)
    probabilities = pipeline.predict_proba(frame) if hasattr(pipeline, "predict_proba") else None
    classes = list(getattr(pipeline, "classes_", []))
    output = []
    for index, prediction in enumerate(predictions):
        value = prediction.item() if hasattr(prediction, "item") else prediction
        row = {"prediction": value, "confidence": None, "positive_probability": None}
        if probabilities is not None:
            values = probabilities[index]
            row["confidence"] = float(max(values))
            positive_index = next((i for i, cls in enumerate(classes) if cls is True or str(cls).lower() in {"true", "1", "yes"}), None)
            if positive_index is not None:
                row["positive_probability"] = float(values[positive_index])
        output.append(row)
    return output


def detect_anomalies(csv_path: str | Path, out_path: str | Path) -> pd.DataFrame:
    from sklearn.ensemble import IsolationForest

    df = pd.read_csv(csv_path)
    if "included" in df.columns:
        mask = df["included"]
        if mask.dtype == object:
            mask = mask.astype(str).str.lower().isin({"true", "1", "yes"})
        else:
            mask = mask.fillna(False).astype(bool)
        df = df[mask].copy()
    num = df.select_dtypes(include="number").drop(columns=list(OUTCOME_COLUMNS), errors="ignore").fillna(0)
    if num.empty:
        raise ValueError("No included numeric feature columns for anomaly detection.")
    model = IsolationForest(contamination="auto", random_state=42)
    score = model.fit_predict(num)
    result = df.copy()
    result["anomaly_flag"] = score
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    result.to_csv(temporary, index=False, encoding="utf-8-sig")
    temporary.replace(destination)
    return result


__all__ = ["detect_anomalies", "predict_supervised", "predict_supervised_details", "train_supervised"]
