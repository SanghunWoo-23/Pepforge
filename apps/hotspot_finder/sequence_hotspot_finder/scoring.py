from __future__ import annotations
import numpy as np
import pandas as pd

AROMATIC = set("FWY")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
POLAR = set("STNQYC")
SPECIAL = set("CGP")

AA_PRIOR = {
    "W": 1.00, "Y": 0.92, "F": 0.86, "R": 0.90, "K": 0.78, "H": 0.72,
    "D": 0.78, "E": 0.74, "C": 0.88, "P": 0.70, "M": 0.60,
    "N": 0.58, "Q": 0.58, "S": 0.54, "T": 0.54, "I": 0.52,
    "L": 0.52, "V": 0.50, "A": 0.38, "G": 0.34, "X": 0.15,
}


def minmax(s: pd.Series, fill: float = 0.0) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().sum() == 0:
        return pd.Series(fill, index=s.index)
    mn, mx = x.min(), x.max()
    if abs(mx - mn) < 1e-12:
        return pd.Series(fill, index=s.index)
    return (x - mn) / (mx - mn)


def apply_sidechain_mods(df: pd.DataFrame, sidechain_db: pd.DataFrame | None) -> pd.DataFrame:
    out = df.copy()
    out["sidechain_charge_delta"] = 0.0
    out["sidechain_hydrophobicity_delta"] = 0.0
    out["sidechain_bulkiness_delta"] = 0.0
    out["sidechain_hotspot_bonus"] = 0.0
    out["sidechain_notes"] = ""
    if sidechain_db is None or sidechain_db.empty or "sidechain_mod" not in out.columns:
        return out
    mod_map = {r["mod"]: r.to_dict() for _, r in sidechain_db.iterrows()}
    for idx, mod in out["sidechain_mod"].items():
        if pd.isna(mod) or mod == "":
            continue
        rec = mod_map.get(str(mod))
        if rec is None:
            out.at[idx, "warning"] = (str(out.at[idx, "warning"]) + " " if out.at[idx, "warning"] else "") + f"Unknown side-chain modification: {mod}."
            continue
        out.at[idx, "sidechain_charge_delta"] = float(rec.get("charge_delta", 0) or 0)
        out.at[idx, "sidechain_hydrophobicity_delta"] = float(rec.get("hydrophobicity_delta", 0) or 0)
        out.at[idx, "sidechain_bulkiness_delta"] = float(rec.get("bulkiness_delta", 0) or 0)
        out.at[idx, "sidechain_hotspot_bonus"] = float(rec.get("hotspot_bonus", 0) or 0)
        out.at[idx, "sidechain_notes"] = rec.get("notes", "")
    return out


def add_rule_features(df: pd.DataFrame, sidechain_db: pd.DataFrame | None = None) -> pd.DataFrame:
    out = apply_sidechain_mods(df, sidechain_db)
    mt = out["model_token"].fillna("").astype(str).str[0].replace("", "X")
    out["base_aa"] = mt
    out["abs_charge"] = (pd.to_numeric(out["charge"], errors="coerce").fillna(0.0) + out["sidechain_charge_delta"]).abs()
    out["hydrophobicity_adjusted"] = pd.to_numeric(out["hydrophobicity"], errors="coerce").fillna(0.0) + out["sidechain_hydrophobicity_delta"]
    out["hydrophobicity_norm"] = ((out["hydrophobicity_adjusted"] + 4.5) / 9.0).clip(0, 1)
    out["aromatic_flag"] = mt.apply(lambda x: int(x in AROMATIC))
    out["positive_flag"] = mt.apply(lambda x: int(x in POSITIVE))
    out["negative_flag"] = mt.apply(lambda x: int(x in NEGATIVE))
    out["polar_flag"] = mt.apply(lambda x: int(x in POLAR))
    out["special_flag"] = mt.apply(lambda x: int(x in SPECIAL))
    out["residue_importance_prior"] = mt.map(AA_PRIOR).fillna(0.15)
    out["chemical_bulkiness_score"] = (pd.to_numeric(out.get("bulkiness", 0), errors="coerce").fillna(0.0) + out["sidechain_bulkiness_delta"]).clip(lower=0) / 5.0
    out["chemical_bulkiness_score"] = out["chemical_bulkiness_score"].clip(0, 1)
    # terminal proximity among scored/model residues
    max_pos = pd.to_numeric(out["model_position"], errors="coerce").max()
    if pd.isna(max_pos) or max_pos <= 1:
        out["terminal_proximity"] = 0.0
    else:
        pos = pd.to_numeric(out["model_position"], errors="coerce")
        pos_norm = (pos - 1) / max(1, max_pos - 1)
        out["terminal_proximity"] = np.maximum(1.0 - pos_norm, pos_norm).fillna(0.0)
    out["rule_score"] = (
        0.32*out["residue_importance_prior"] +
        0.14*out["abs_charge"].clip(0,1) +
        0.12*out["aromatic_flag"] +
        0.08*out["polar_flag"] +
        0.07*out["special_flag"] +
        0.07*out["hydrophobicity_norm"] +
        0.06*out["chemical_bulkiness_score"] +
        0.04*out["terminal_proximity"] +
        pd.to_numeric(out.get("hotspot_bonus", 0), errors="coerce").fillna(0.0) +
        out["sidechain_hotspot_bonus"] -
        pd.to_numeric(out.get("hotspot_penalty", 0), errors="coerce").fillna(0.0)
    ).clip(0, 1)
    # annotation only tokens not scored
    ann = out["class"].isin(["N_terminal_modification", "C_terminal_modification", "label"])
    out.loc[ann, "rule_score"] = np.nan
    return out


def merge_external_features(df: pd.DataFrame, conservation_df=None, structure_df=None, supervised_df=None, merge_position_mode="model_position") -> pd.DataFrame:
    out = df.copy()
    key_col = merge_position_mode if merge_position_mode in out.columns else "model_position"
    def _merge_position_table(out_df, ext_df, suffix):
        ext = ext_df.copy()
        ext["position"] = pd.to_numeric(ext["position"], errors="coerce")
        merged = out_df.merge(ext, how="left", left_on=["record_name", key_col], right_on=["record_name", "position"], suffixes=("", suffix))
        pos_col = f"position{suffix}"
        if pos_col in merged:
            merged = merged.drop(columns=[pos_col])
        elif "position" in merged and key_col != "position":
            merged = merged.drop(columns=["position"])
        return merged
    if conservation_df is not None and not conservation_df.empty:
        out = _merge_position_table(out, conservation_df, "_cons")
    if structure_df is not None and not structure_df.empty:
        out = _merge_position_table(out, structure_df, "_struct")
    if supervised_df is not None and not supervised_df.empty:
        out = _merge_position_table(out, supervised_df, "_sup")
    return out


def compute_structure_score(df: pd.DataFrame) -> pd.Series:
    parts = []
    if "solvent_accessibility" in df:
        parts.append(minmax(df["solvent_accessibility"], 0.0))
    if "relative_ASA" in df:
        parts.append(minmax(df["relative_ASA"], 0.0))
    if "interface_probability" in df:
        parts.append(minmax(df["interface_probability"], 0.0))
    if "disorder_score" in df:
        parts.append(0.5 * minmax(df["disorder_score"], 0.0))
    if not parts:
        return pd.Series(0.0, index=df.index)
    return sum(parts) / len(parts)


def compute_final_score(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    for col in ["esm_embedding_score", "esm_unpredictability_score", "esm_mutation_sensitivity", "conservation_score", "supervised_score"]:
        if col not in out:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    out["structure_score"] = compute_structure_score(out)
    w = config.get("weights", {}) or {}
    defaults = {
        "rule_score": 0.42, "esm_embedding_score": 0.12, "esm_unpredictability_score": 0.18,
        "esm_mutation_sensitivity": 0.18, "conservation_score": 0.05, "structure_score": 0.05,
        "supervised_score": 0.0,
    }
    defaults.update({k: float(v) for k, v in w.items()})
    total_w = sum(v for v in defaults.values() if v > 0) or 1.0
    score = pd.Series(0.0, index=out.index)
    for col, weight in defaults.items():
        if col not in out:
            out[col] = 0.0
        vals = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        score += (weight / total_w) * vals
    ann = out["class"].isin(["N_terminal_modification", "C_terminal_modification", "label"])
    out["hotspot_score"] = score.clip(0, 1)
    out.loc[ann, "hotspot_score"] = np.nan
    scored = out["hotspot_score"].notna()
    out.loc[scored, "hotspot_rank"] = out.loc[scored, "hotspot_score"].rank(ascending=False, method="dense").astype(int)
    out.loc[~scored, "hotspot_rank"] = np.nan
    out["confidence"] = "low"
    out.loc[out["hotspot_score"] >= 0.50, "confidence"] = "medium"
    out.loc[out["hotspot_score"] >= 0.75, "confidence"] = "high"
    out.loc[ann, "confidence"] = "annotation_only"
    out["reason"] = out.apply(make_reason, axis=1)
    return out


def make_reason(r) -> str:
    if r.get("confidence") == "annotation_only":
        return f"{r.get('class')}; annotation only, not scored as amino-acid hotspot"
    if r.get("is_linker", 0) == 1:
        return "linker/spacer; usually lower hotspot priority"
    parts = []
    if r.get("aromatic_flag", 0): parts.append("aromatic")
    if r.get("positive_flag", 0): parts.append("positive/charged")
    if r.get("negative_flag", 0): parts.append("negative/charged")
    if r.get("polar_flag", 0): parts.append("polar")
    if r.get("special_flag", 0): parts.append("C/G/P-like special residue")
    if r.get("is_d_form", 0): parts.append("D-form mapped to base AA")
    if r.get("is_non_natural", 0): parts.append("non-natural mapped to closest AA")
    if r.get("is_sidechain_modified", 0): parts.append(f"side-chain modified: {r.get('sidechain_mod')}")
    if r.get("esm_mutation_sensitivity", 0) >= 0.7: parts.append("high ESM mutation sensitivity")
    if r.get("esm_unpredictability_score", 0) >= 0.7: parts.append("high masked-marginal unpredictability")
    if r.get("conservation_score", 0) >= 0.7: parts.append("high conservation")
    if r.get("structure_score", 0) >= 0.7: parts.append("structure feature support")
    return "; ".join(parts) if parts else "low sequence-only hotspot signal"
