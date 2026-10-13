from __future__ import annotations

"""Small supervised Pepforge ranker for PSB/docking evidence tables.

This is deliberately *not* a folding model.  It combines optional ESM sequence
embeddings with numeric PSB/MD/docking features after an explicitly labelled
training target exists.  Runtime project data are never silently added to a
training set.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence
import csv
import hashlib
import json

import joblib
import numpy as np

RANKER_VERSION = "5.0.0-rc2"


@dataclass(frozen=True)
class RankerTrainingConfig:
    n_estimators: int = 300
    random_state: int = 20260923
    min_training_rows: int = 12
    cv_folds: int = 5


def conformer_numeric_features(row: dict[str, Any]) -> dict[str, float]:
    """Extract conservative numeric PSB features without inventing missing data."""
    keys = (
        "energy", "severe_steric_clashes", "nonbonded_vdw_overlaps",
        "minimum_nonbonded_vdw_ratio", "resolved_backbone_positions",
        "helical_basin_fraction", "beta_extended_fraction", "PPII_fraction",
        "turn_like_fraction", "alpha_i_i4_contacts", "helix310_i_i3_contacts",
        "nonlocal_backbone_contacts", "beta_turn_CA_i_i3_contacts",
        # V5 MD/docking evidence columns when explicitly provided.
        "mean_rmsd_A", "mean_rg_A", "mean_rmsf_A", "contact_persistence_mean",
        "hbond_persistence_mean", "docking_engine_score", "dockbench_contact_count",
        "dockbench_clash_count", "interface_bsa_A2",
    )
    out: dict[str, float] = {}
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            out[key] = float(value)
        except Exception:
            continue
    return out


def assemble_feature_vector(
    numeric_features: dict[str, float],
    *,
    embedding: Sequence[float] | np.ndarray | None = None,
    feature_order: Sequence[str] | None = None,
) -> tuple[np.ndarray, list[str]]:
    if feature_order is None:
        feature_names = sorted(numeric_features)
    else:
        feature_names = list(feature_order)
    values = [float(numeric_features.get(name, np.nan)) for name in feature_names]
    if embedding is not None:
        emb = np.asarray(embedding, dtype=float).reshape(-1)
        values.extend(emb.tolist())
        feature_names.extend([f"esm_{i:04d}" for i in range(len(emb))])
    return np.asarray(values, dtype=float), feature_names


def _make_pipeline(config: RankerTrainingConfig):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestRegressor(
            n_estimators=int(config.n_estimators),
            random_state=int(config.random_state),
            n_jobs=-1,
        )),
    ])


def _validate_training_matrix(X: np.ndarray, y: Sequence[float], feature_names: Sequence[str], cfg: RankerTrainingConfig, target_name: str) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(X, dtype=float)
    targets = np.asarray(list(y), dtype=float)
    if matrix.ndim != 2:
        raise ValueError("X must be a 2D feature matrix.")
    if len(targets) != matrix.shape[0]:
        raise ValueError("X/y row count mismatch.")
    if matrix.shape[0] < int(cfg.min_training_rows):
        raise ValueError(f"At least {cfg.min_training_rows} explicitly labeled rows are required; got {matrix.shape[0]}.")
    if matrix.shape[1] != len(feature_names):
        raise ValueError("feature_names length does not match X columns.")
    if not str(target_name or "").strip():
        raise ValueError("target_name is required so model semantics are auditable.")
    if not np.all(np.isfinite(targets)):
        raise ValueError("Training target contains non-finite values.")
    return matrix, targets


def train_ranker(
    X: np.ndarray,
    y: Sequence[float],
    feature_names: Sequence[str],
    output_dir: str | Path,
    *,
    target_name: str,
    config: RankerTrainingConfig | None = None,
) -> dict[str, str]:
    """Train a small RandomForest advisory ranker from explicitly supplied labels."""
    cfg = config or RankerTrainingConfig()
    matrix, targets = _validate_training_matrix(X, y, feature_names, cfg, target_name)
    pipeline = _make_pipeline(cfg)
    pipeline.fit(matrix, targets)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "pepforge_ranker.joblib"
    meta_path = out / "pepforge_ranker.json"
    joblib.dump(pipeline, model_path)
    metadata = {
        "version": RANKER_VERSION,
        "model_type": "RandomForestRegressor",
        "target_name": str(target_name),
        "training_rows": int(matrix.shape[0]),
        "feature_count": int(matrix.shape[1]),
        "feature_names": list(feature_names),
        "training_config": asdict(cfg),
        "validation": "NOT_RUN_BY_train_ranker_USE_train_validate_ranker_FOR_CV",
        "claim_guard": (
            "Pepforge ranker output is an advisory model score for the declared supervised target. "
            "It is not folding probability, docking affinity, Kd, biological activity, or experimental validation unless the target itself is a documented measurement and the model is separately validated."
        ),
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"model": str(model_path), "metadata": str(meta_path)}


def _rankdata(values: np.ndarray) -> np.ndarray:
    """Average-rank implementation sufficient for Spearman diagnostics."""
    x = np.asarray(values, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i + 1
        while j < len(x) and x[order[j]] == x[order[i]]:
            j += 1
        avg = (i + j - 1) / 2.0 + 1.0
        ranks[order[i:j]] = avg
        i = j
    return ranks


def _spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    if len(y_true) < 2:
        return None
    a, b = _rankdata(y_true), _rankdata(y_pred)
    if float(np.std(a)) <= 1e-12 or float(np.std(b)) <= 1e-12:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def audit_supervised_dataset(
    X: np.ndarray,
    y: Sequence[float],
    *,
    groups: Sequence[str] | None = None,
    row_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return transparent supervised-dataset readiness diagnostics."""
    matrix = np.asarray(X, dtype=float)
    targets = np.asarray(list(y), dtype=float)
    rows = int(matrix.shape[0]) if matrix.ndim == 2 else 0
    features = int(matrix.shape[1]) if matrix.ndim == 2 else 0
    missing_fraction = float(np.mean(~np.isfinite(matrix))) if rows and features else 0.0
    unique_targets = int(len(np.unique(targets[np.isfinite(targets)]))) if targets.size else 0
    ids = list(row_ids or [])
    duplicate_row_ids = sorted({x for x in ids if ids.count(x) > 1}) if ids else []
    group_values = [str(x) for x in groups] if groups is not None else []
    unique_groups = len(set(group_values)) if group_values else 0
    issues: list[str] = []
    if duplicate_row_ids:
        issues.append("duplicate_row_ids")
    if unique_targets < 2:
        issues.append("target_has_no_variation")
    if groups is not None and unique_groups < 2:
        issues.append("insufficient_unique_groups_for_grouped_cv")
    return {
        "rows": rows,
        "features": features,
        "missing_feature_fraction": round(missing_fraction, 6),
        "unique_target_values": unique_targets,
        "unique_groups": unique_groups if groups is not None else None,
        "duplicate_row_ids": duplicate_row_ids,
        "issues": issues,
        "status": "READY_FOR_INTERNAL_CV" if not issues else "REVIEW_REQUIRED",
        "claim_guard": "Dataset readiness diagnostics do not establish domain representativeness, external validity, or production fitness.",
    }


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | None]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    try:
        r2 = float(r2_score(y_true, y_pred))
    except Exception:
        r2 = None
    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "spearman_rank_correlation": _spearman(y_true, y_pred),
    }


def train_validate_ranker(
    X: np.ndarray,
    y: Sequence[float],
    feature_names: Sequence[str],
    output_dir: str | Path,
    *,
    target_name: str,
    groups: Sequence[str] | None = None,
    row_ids: Sequence[str] | None = None,
    config: RankerTrainingConfig | None = None,
    dataset_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cross-validate then fit a final advisory ranker.

    If sequence/group identifiers are supplied, GroupKFold is used so conformers
    from the same peptide do not leak across train/test folds.  No threshold is
    used to proclaim the model "validated"; metrics are reported for human review.
    """
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import GroupKFold, KFold

    cfg = config or RankerTrainingConfig()
    matrix, targets = _validate_training_matrix(X, y, feature_names, cfg, target_name)
    n = matrix.shape[0]
    identifiers = list(row_ids) if row_ids is not None else [f"row_{i+1:05d}" for i in range(n)]
    if len(identifiers) != n:
        raise ValueError("row_ids length mismatch.")

    group_values = None if groups is None else np.asarray([str(x) for x in groups], dtype=object)
    if group_values is not None and len(group_values) != n:
        raise ValueError("groups length mismatch.")
    dataset_audit = audit_supervised_dataset(matrix, targets, groups=groups, row_ids=identifiers)
    if dataset_audit.get("duplicate_row_ids"):
        raise ValueError("row_ids must be unique for auditable training lineage.")
    if group_values is not None and len(set(group_values.tolist())) >= 2:
        folds = min(int(cfg.cv_folds), len(set(group_values.tolist())))
        splitter = GroupKFold(n_splits=max(2, folds))
        splits = splitter.split(matrix, targets, group_values)
        cv_mode = "GroupKFold"
    else:
        folds = min(int(cfg.cv_folds), n)
        if folds < 2:
            raise ValueError("At least two folds are required for cross-validation.")
        splitter = KFold(n_splits=folds, shuffle=True, random_state=int(cfg.random_state))
        splits = splitter.split(matrix, targets)
        cv_mode = "KFold"

    predictions = np.full(n, np.nan, dtype=float)
    baseline_predictions = np.full(n, np.nan, dtype=float)
    fold_ids = np.zeros(n, dtype=int)
    for fold_idx, (train_idx, test_idx) in enumerate(splits, 1):
        model = _make_pipeline(cfg)
        model.fit(matrix[train_idx], targets[train_idx])
        predictions[test_idx] = model.predict(matrix[test_idx])
        baseline_predictions[test_idx] = float(np.mean(targets[train_idx]))
        fold_ids[test_idx] = fold_idx
    if not np.all(np.isfinite(predictions)) or not np.all(np.isfinite(baseline_predictions)):
        raise RuntimeError("Cross-validation did not produce a prediction for every training row.")

    model_metrics = _regression_metrics(targets, predictions)
    baseline_metrics = _regression_metrics(targets, baseline_predictions)
    mae = float(model_metrics["mae"])
    rmse = float(model_metrics["rmse"])
    r2 = model_metrics["r2"]
    spearman = model_metrics["spearman_rank_correlation"]

    final_model = _make_pipeline(cfg)
    final_model.fit(matrix, targets)
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "pepforge_ranker.joblib"
    meta_path = out / "pepforge_ranker.json"
    cv_path = out / "cross_validation_predictions.csv"
    card_path = out / "MODEL_CARD.md"
    joblib.dump(final_model, model_path)

    with cv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row_id", "fold", "target", "prediction", "baseline_prediction", "residual", "group"])
        writer.writeheader()
        for i in range(n):
            writer.writerow({
                "row_id": identifiers[i], "fold": int(fold_ids[i]), "target": float(targets[i]),
                "prediction": float(predictions[i]), "baseline_prediction": float(baseline_predictions[i]),
                "residual": float(targets[i] - predictions[i]),
                "group": "" if group_values is None else str(group_values[i]),
            })

    rf = final_model.named_steps.get("model")
    importances = []
    if hasattr(rf, "feature_importances_"):
        importances = sorted(
            [{"feature": name, "importance": float(value)} for name, value in zip(feature_names, rf.feature_importances_)],
            key=lambda x: x["importance"], reverse=True,
        )
    metadata = {
        "version": RANKER_VERSION,
        "model_type": "RandomForestRegressor",
        "target_name": str(target_name),
        "training_rows": int(n),
        "feature_count": int(matrix.shape[1]),
        "feature_names": list(feature_names),
        "training_config": asdict(cfg),
        "dataset_audit": dataset_audit,
        "cross_validation": {
            "mode": cv_mode, "folds": int(folds), **model_metrics,
        },
        "naive_train_mean_baseline": baseline_metrics,
        "baseline_comparison": {
            "rmse_improvement_over_train_mean": float(baseline_metrics["rmse"] - model_metrics["rmse"]),
            "mae_improvement_over_train_mean": float(baseline_metrics["mae"] - model_metrics["mae"]),
            "interpretation": "Positive values mean the model beat the fold-wise training-mean baseline on this internal CV only.",
        },
        "promotion_status": "RESEARCH_ONLY_EXTERNAL_VALIDATION_REQUIRED",
        "feature_importance": importances,
        "dataset_provenance": dataset_provenance or {},
        "files": {"model": str(model_path), "cv_predictions": str(cv_path), "model_card": str(card_path)},
        "claim_guard": (
            "Cross-validation metrics describe this labelled dataset and split strategy only. "
            "They do not establish biological validity, transferability to new peptide chemistry, affinity, or folding probability."
        ),
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    card_path.write_text(
        "# Pepforge Ranker Model Card\n\n"
        f"- Target: `{target_name}`\n"
        f"- Training rows: {n}\n"
        f"- Features: {matrix.shape[1]}\n"
        f"- CV: {cv_mode}, {folds} folds\n"
        f"- MAE: {mae:.6g}\n"
        f"- RMSE: {rmse:.6g}\n"
        f"- R²: {r2 if r2 is not None else 'unavailable'}\n"
        f"- Spearman: {spearman if spearman is not None else 'unavailable'}\n"
        f"- Train-mean baseline RMSE: {baseline_metrics['rmse']:.6g}\n"
        f"- Internal CV status: RESEARCH_ONLY_EXTERNAL_VALIDATION_REQUIRED\n\n"
        "## Intended use\nAdvisory ranking for the explicitly declared supervised target.\n\n"
        "## Not valid claims\nThis model is not a folding probability model, an experimental affinity/Kd measurement, or proof of biological activity.\n",
        encoding="utf-8",
    )
    return {"model": str(model_path), "metadata": str(meta_path), "cv_predictions": str(cv_path), "model_card": str(card_path), "metrics": metadata["cross_validation"]}


def train_validate_ranker_from_csv(
    csv_path: str | Path,
    output_dir: str | Path,
    *,
    target_column: str,
    feature_columns: Sequence[str] | None = None,
    sequence_column: str | None = None,
    row_id_column: str | None = None,
    use_esm: bool = False,
    esm_config: Any | None = None,
    config: RankerTrainingConfig | None = None,
) -> dict[str, Any]:
    """Build a labelled training matrix from CSV and run grouped CV/final fit.

    Numeric features are either explicitly named or auto-detected.  When ESM is
    requested, only rows whose sequence can be represented without silently
    erasing D/non-natural/linker chemistry are embedded.
    """
    import pandas as pd
    from peptiforg_core.esm_peptide_embedding import prepare_sequence_for_esm, embed_canonical_sequences

    source = Path(csv_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    df = pd.read_csv(source)
    if target_column not in df.columns:
        raise ValueError(f"Target column not found: {target_column}")
    target = pd.to_numeric(df[target_column], errors="coerce")
    valid = target.notna()
    df = df.loc[valid].reset_index(drop=True)
    target = target.loc[valid].reset_index(drop=True)
    if len(df) == 0:
        raise ValueError("No rows contain a numeric supervised target.")

    excluded = {target_column}
    if sequence_column:
        excluded.add(sequence_column)
    if row_id_column:
        excluded.add(row_id_column)
    if feature_columns is None:
        cols = []
        for col in df.columns:
            if col in excluded:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if int(numeric.notna().sum()) > 0:
                cols.append(str(col))
    else:
        cols = [str(c) for c in feature_columns]
    if not cols and not use_esm:
        raise ValueError("No numeric feature columns were available.")
    matrix = np.column_stack([pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float) for c in cols]) if cols else np.empty((len(df), 0), dtype=float)
    feature_names = list(cols)

    groups = None
    esm_meta: dict[str, Any] | None = None
    if sequence_column:
        if sequence_column not in df.columns:
            raise ValueError(f"Sequence column not found: {sequence_column}")
        groups = [str(x) for x in df[sequence_column].tolist()]
    if use_esm:
        if not sequence_column:
            raise ValueError("sequence_column is required when use_esm=True.")
        canonical: list[str] = []
        for raw in df[sequence_column].astype(str):
            prep = prepare_sequence_for_esm(raw)
            if prep.status not in {"CANONICAL_SEQUENCE_READY", "CANONICAL_BACKBONE_WITH_UNMODELED_MODIFIERS"}:
                raise ValueError(f"ESM training row cannot be represented safely: {raw!r} -> {prep.status}")
            canonical.append(prep.canonical_sequence)
        unique = list(dict.fromkeys(canonical))
        embedded = embed_canonical_sequences(unique, config=esm_config)
        lookup = {seq: embedded["embeddings"][i] for i, seq in enumerate(unique)}
        emb_matrix = np.vstack([lookup[s] for s in canonical]).astype(float)
        matrix = np.concatenate([matrix, emb_matrix], axis=1)
        feature_names.extend([f"esm_{i:04d}" for i in range(emb_matrix.shape[1])])
        esm_meta = {k: v for k, v in embedded.items() if k != "embeddings"}

    row_ids = [str(x) for x in df[row_id_column].tolist()] if row_id_column else [f"row_{i+1:05d}" for i in range(len(df))]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    provenance = {
        "source_csv": str(source), "source_sha256": digest,
        "target_column": target_column, "numeric_feature_columns": cols,
        "sequence_column": sequence_column, "row_id_column": row_id_column,
        "esm": esm_meta,
    }
    return train_validate_ranker(
        matrix, target.to_numpy(dtype=float), feature_names, output_dir,
        target_name=target_column, groups=groups, row_ids=row_ids, config=config,
        dataset_provenance=provenance,
    )


def predict_ranker(model_path: str | Path, X: np.ndarray) -> np.ndarray:
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(path)
    model = joblib.load(path)
    matrix = np.asarray(X, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("X must be a 2D feature matrix.")
    return np.asarray(model.predict(matrix), dtype=float)


__all__ = [
    "RANKER_VERSION", "RankerTrainingConfig", "conformer_numeric_features",
    "assemble_feature_vector", "audit_supervised_dataset", "train_ranker", "train_validate_ranker",
    "train_validate_ranker_from_csv", "predict_ranker",
]
