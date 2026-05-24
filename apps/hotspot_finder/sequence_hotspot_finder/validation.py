from __future__ import annotations
import json
import pandas as pd

TOKEN_REQUIRED = {"token", "class", "model_token", "charge", "hydrophobicity", "notes"}
ALLOWED_CLASSES = {
    "natural_L_amino_acid", "D_amino_acid", "non_natural_amino_acid", "linker",
    "N_terminal_modification", "C_terminal_modification", "label", "unknown"
}
ALLOWED_MODEL_CHARS = set("ACDEFGHIKLMNPQRSTVWYX")


def validate_token_db(df: pd.DataFrame) -> list[str]:
    msgs = []
    missing = TOKEN_REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"token_db.csv missing required columns: {sorted(missing)}")
    if df["token"].isna().any() or (df["token"].astype(str).str.len() == 0).any():
        raise ValueError("token_db.csv contains empty token values.")
    dups = df[df["token"].duplicated()]["token"].astype(str).tolist()
    if dups:
        raise ValueError(f"token_db.csv has duplicate token entries: {dups[:10]}")
    bad_classes = sorted(set(df["class"].astype(str)) - ALLOWED_CLASSES)
    if bad_classes:
        msgs.append(f"Warning: non-standard token classes found: {bad_classes}")
    for col in ["charge", "hydrophobicity"]:
        pd.to_numeric(df[col], errors="raise")
    for tok, mt in zip(df["token"].astype(str), df["model_token"].fillna("").astype(str)):
        if mt and not set(mt).issubset(ALLOWED_MODEL_CHARS):
            msgs.append(f"Warning: token {tok} has non-canonical model_token '{mt}'.")
    return msgs


def validate_sidechain_mod_db(df: pd.DataFrame) -> list[str]:
    req = {"mod", "class", "charge_delta", "hydrophobicity_delta", "bulkiness_delta", "hotspot_bonus", "notes"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"sidechain_mod_db.csv missing required columns: {sorted(missing)}")
    for col in ["charge_delta", "hydrophobicity_delta", "bulkiness_delta", "hotspot_bonus"]:
        pd.to_numeric(df[col], errors="raise")
    if df["mod"].duplicated().any():
        raise ValueError("sidechain_mod_db.csv contains duplicate mod values.")
    return []


def validate_config(cfg: dict) -> list[str]:
    msgs = []
    cfg.setdefault("window_size", 900)
    cfg.setdefault("overlap", 150)
    cfg.setdefault("batch_size", 4)
    if int(cfg["window_size"]) <= int(cfg["overlap"]):
        raise ValueError("window_size must be greater than overlap.")
    if int(cfg["window_size"]) > 1000:
        msgs.append("Warning: window_size > 1000 may exceed safe ESM context in Colab. It will be clamped if safe_window_limit is enabled.")
    if int(cfg["batch_size"]) <= 0:
        raise ValueError("batch_size must be positive.")
    if int(cfg.get("top_n", 30)) <= 0:
        raise ValueError("top_n must be positive.")
    weights = cfg.get("weights", {})
    if weights and sum(float(v) for v in weights.values()) <= 0:
        raise ValueError("Sum of weights must be positive.")
    return msgs


def validate_domain_csv(df: pd.DataFrame) -> None:
    req = {"record_name", "domain_name", "start", "end"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"domain CSV missing required columns: {sorted(missing)}")
    if (pd.to_numeric(df["start"], errors="coerce") < 1).any():
        raise ValueError("domain CSV start must be >= 1.")
    if (pd.to_numeric(df["end"], errors="coerce") < pd.to_numeric(df["start"], errors="coerce")).any():
        raise ValueError("domain CSV end must be >= start.")


def validate_position_csv(df: pd.DataFrame, name: str) -> None:
    req = {"record_name", "position"}
    if name == "conservation":
        req.add("conservation_score")
    if name == "supervised":
        req.add("supervised_score")
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"{name} CSV missing required columns: {sorted(missing)}")
    pd.to_numeric(df["position"], errors="raise")
