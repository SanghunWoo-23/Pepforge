from __future__ import annotations
from pathlib import Path
import shutil
import pandas as pd
import numpy as np
from .io_utils import read_fasta_or_sequence, load_json, save_json, load_optional_csv, timestamp, write_text, write_run_summary, package_outputs
from .validation import validate_token_db, validate_sidechain_mod_db, validate_config, validate_domain_csv, validate_position_csv
from .parser import parse_sequence
from .scoring import add_rule_features, merge_external_features, compute_final_score


def load_config(config_path: str | Path | None = None, config: dict | None = None) -> dict:
    if config is not None:
        cfg = dict(config)
    elif config_path is not None:
        cfg = load_json(config_path)
    else:
        cfg = {}
    defaults = {
        "use_esm": False, "esm_model": "esm2_t6_8M_UR50D", "device": "auto",
        "window_size": 900, "overlap": 150, "safe_window_limit": 1000, "clamp_window_size": True,
        "batch_size": 4, "use_masked_marginal": True, "use_mutation_sensitivity": True,
        "max_mutation_scan_length": 2500, "top_n": 30, "merge_position_mode": "model_position",
        "weights": {"rule_score":0.42, "esm_embedding_score":0.12, "esm_unpredictability_score":0.18,
                    "esm_mutation_sensitivity":0.18, "conservation_score":0.05, "structure_score":0.05,
                    "supervised_score":0.0},
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)
    return cfg


def analyze_records(records: dict[str, str], config: dict, token_db: pd.DataFrame, sidechain_mod_db: pd.DataFrame | None = None,
                    domains_df: pd.DataFrame | None = None, structure_df: pd.DataFrame | None = None,
                    conservation_df: pd.DataFrame | None = None, supervised_df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    logs = {"records": {}, "warnings": []}
    validate_token_db(token_db)
    if sidechain_mod_db is not None:
        validate_sidechain_mod_db(sidechain_mod_db)
    logs["warnings"].extend(validate_config(config))
    if domains_df is not None and not domains_df.empty:
        validate_domain_csv(domains_df)
    if structure_df is not None and not structure_df.empty:
        validate_position_csv(structure_df, "structure")
    if conservation_df is not None and not conservation_df.empty:
        validate_position_csv(conservation_df, "conservation")
    if supervised_df is not None and not supervised_df.empty:
        validate_position_csv(supervised_df, "supervised")

    all_dfs = []
    for name, seq in records.items():
        parsed, model_sequence = parse_sequence(seq, token_db)
        parsed.insert(0, "record_name", name)
        parsed.insert(1, "raw_sequence", seq)
        parsed.insert(2, "model_sequence", model_sequence)
        feat = add_rule_features(parsed, sidechain_db=sidechain_mod_db)
        if bool(config.get("use_esm", False)) and len(model_sequence) > 0:
            try:
                from .esm_features import compute_esm_features_for_model_sequence
                esm_df = compute_esm_features_for_model_sequence(model_sequence, config, domains_df=domains_df, record_name=name)
                feat = feat.merge(esm_df, how="left", on="model_position")
            except Exception as e:
                msg = f"ESM feature extraction failed for {name}: {type(e).__name__}: {e}. Continuing with rule-based scores."
                logs["warnings"].append(msg)
                feat["warning"] = feat["warning"].fillna("").astype(str) + " " + msg
        feat = merge_external_features(feat, conservation_df=conservation_df, structure_df=structure_df, supervised_df=supervised_df, merge_position_mode=config.get("merge_position_mode", "model_position"))
        scored = compute_final_score(feat, config)
        logs["records"][name] = {"input_length_chars": len(seq), "model_sequence_length": len(model_sequence), "tokens": len(parsed)}
        all_dfs.append(scored)
    full_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    if not full_df.empty and "hotspot_score" in full_df:
        top_n = int(config.get("top_n", 30))
        top_df = full_df[full_df["hotspot_score"].notna()].sort_values(["record_name", "hotspot_score"], ascending=[True, False]).groupby("record_name").head(top_n)
    else:
        top_df = pd.DataFrame()
    return full_df, top_df, logs


def analyze_input(user_input: str, config_path: str | Path | None = None, token_db_path: str | Path | None = None,
                  sidechain_mod_db_path: str | Path | None = None, outdir: str | Path = "outputs",
                  domains_path: str | Path | None = None, structure_features_path: str | Path | None = None,
                  conservation_features_path: str | Path | None = None, supervised_features_path: str | Path | None = None,
                  config: dict | None = None) -> dict:
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config_path, config)
    token_db_path = Path(token_db_path) if token_db_path is not None else Path("data/token_db.csv")
    token_db = pd.read_csv(token_db_path)
    sidechain_df = load_optional_csv(sidechain_mod_db_path)
    domains_df = load_optional_csv(domains_path)
    structure_df = load_optional_csv(structure_features_path)
    conservation_df = load_optional_csv(conservation_features_path)
    supervised_df = load_optional_csv(supervised_features_path)
    records = read_fasta_or_sequence(user_input)
    full_df, top_df, logs = analyze_records(records, cfg, token_db, sidechain_df, domains_df, structure_df, conservation_df, supervised_df)
    ts = timestamp()
    full_csv = outdir / f"hotspot_full_{ts}.csv"
    top_csv = outdir / f"hotspot_top_{ts}.csv"
    config_json = outdir / f"analysis_config_{ts}.json"
    input_used = outdir / f"input_used_{ts}.fasta"
    token_used = outdir / f"token_db_used_{ts}.csv"
    sidechain_used = outdir / f"sidechain_mod_db_used_{ts}.csv"
    summary_txt = outdir / f"run_summary_{ts}.txt"
    full_df.to_csv(full_csv, index=False, encoding="utf-8-sig")
    top_df.to_csv(top_csv, index=False, encoding="utf-8-sig")
    save_json(cfg, config_json)
    write_text(input_used, user_input)
    shutil.copy(token_db_path, token_used)
    if sidechain_mod_db_path and Path(sidechain_mod_db_path).exists():
        shutil.copy(sidechain_mod_db_path, sidechain_used)
    else:
        sidechain_used = None
    summary = {
        "timestamp": ts, "records": len(records), "use_esm": cfg.get("use_esm"), "esm_model": cfg.get("esm_model"),
        "window_size": cfg.get("window_size"), "overlap": cfg.get("overlap"), "batch_size": cfg.get("batch_size"),
        "merge_position_mode": cfg.get("merge_position_mode"), "warnings": " | ".join(logs.get("warnings", [])) or "none"
    }
    write_run_summary(summary_txt, summary)
    files = {
        Path(full_csv).name: full_csv, Path(top_csv).name: top_csv, Path(config_json).name: config_json,
        Path(input_used).name: input_used, Path(token_used).name: token_used,
        "run_summary.txt": summary_txt,
    }
    if sidechain_used: files[Path(sidechain_used).name] = sidechain_used
    for label, p in [("domains_used.csv", domains_path), ("structure_features_used.csv", structure_features_path), ("conservation_features_used.csv", conservation_features_path), ("supervised_features_used.csv", supervised_features_path)]:
        if p and Path(p).exists(): files[label] = p
    zip_path = outdir / f"hotspot_result_package_{ts}.zip"
    package_outputs(zip_path, files)
    return {"full_df": full_df, "top_df": top_df, "logs": logs, "full_csv": str(full_csv), "top_csv": str(top_csv), "config_json": str(config_json), "zip_path": str(zip_path)}
