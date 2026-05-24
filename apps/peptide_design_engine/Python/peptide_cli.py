#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peptide Design Engine — EXE-ready CLI
- Preserves the original engine and outputs.
- Adds stable preset layering, target-mode shortcut, continual-learning CSV import,
  lightweight ML training, and optional trained-model reranking.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import peptide_engine as eng

try:
    import data_manager
    import ml_trainer
except Exception:  # optional helpers; CLI still works without them
    data_manager = None
    ml_trainer = None
try:
    import external_parsers
except Exception:
    external_parsers = None


def parse_targets(text: str) -> List[List[str]]:
    import re
    return [list(x.strip()) for x in re.split(r"[\n,;|/]+", str(text)) if x.strip()]


def apply_preset(name: str | None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if name == "fast":
        cfg.update({
            "LEN_MODE": "RANDOM", "MIN_LENGTH": 10, "MAX_LENGTH": 12, "FIX_LENGTH": 12,
            "POP": 100, "GEN": 8, "FINAL_TOPK": 10,
            "USE_D": False, "USE_NON_NAT": False, "USE_LINKER": False,
            "USE_TAG": False, "USE_BASE_CHEM": False, "USE_LABEL": False,
            "MOTIF_LOCK": False, "USE_OPTIONAL_ML": False,
            "AUTO_HOTSPOT": False, "PREPARE_PSEUDODOCKING_COLAB": False,
        })
    elif name == "paper":
        cfg.update({
            "LEN_MODE": "RANDOM", "MIN_LENGTH": 12, "MAX_LENGTH": 15, "FIX_LENGTH": 14,
            "POP": 200, "GEN": 20, "FINAL_TOPK": 25,
            "DESIGN_MODE": "BRIDGE_LINKER", "BINDER_MODE": "BALANCED",
            "USE_D": False, "USE_NON_NAT": False, "USE_LINKER": True,
            "USE_TAG": False, "USE_BASE_CHEM": False, "USE_LABEL": False,
            "USE_OPTIONAL_ML": False, "AUTO_HOTSPOT": False,
        })
    elif name == "exploration":
        cfg.update({
            "LEN_MODE": "RANDOM", "MIN_LENGTH": 12, "MAX_LENGTH": 20, "FIX_LENGTH": 16,
            "POP": 300, "GEN": 30, "FINAL_TOPK": 50,
            "USE_D": True, "USE_NON_NAT": True, "USE_LINKER": True,
            "USE_TAG": True, "USE_BASE_CHEM": True, "USE_LABEL": True,
            "USE_OPTIONAL_ML": True, "ML_RERANK_WEIGHT": 0.20,
        })
    elif name == "hotspot_only":
        cfg.update({
            "LEN_MODE": "RANDOM", "MIN_LENGTH": 12, "MAX_LENGTH": 15, "FIX_LENGTH": 14,
            "POP": 200, "GEN": 20, "FINAL_TOPK": 25,
            "DESIGN_MODE": "MULTI_TARGET_BINDER", "BINDER_MODE": "BALANCED",
            "USE_D": False, "USE_NON_NAT": False, "USE_LINKER": False,
            "USE_TAG": False, "USE_BASE_CHEM": False, "USE_LABEL": False,
            "MOTIF_LOCK": False, "LOCKED_MOTIFS": [], "LOCKED_MOTIF_POS": [],
            "MOTIF_POSITION_MODE": "FREE", "MOTIF_POSITION_MAP": {},
            "AUTO_HOTSPOT": True, "HOTSPOT_SOURCE": "SEQUENCE",
            "HOTSPOT_WINDOW": 6, "HOTSPOT_TOPK": 5,
            "HOTSPOT_REPLACE_TARGETS": True, "HOTSPOT_LOCK_AS_MOTIF": False,
            "HOTSPOT_MIN_EXPOSURE": 0.35, "HOTSPOT_BINDING_WEIGHT": 0.80,
            "USE_OPTIONAL_ML": False, "PREPARE_PSEUDODOCKING_COLAB": False,
        })
    return cfg


def write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Peptide Design Engine — EXE-ready continual-learning CLI")
    p.add_argument("--config", default=None)
    p.add_argument("--target", default=None)
    p.add_argument("--preset", choices=["fast", "paper", "exploration", "hotspot_only"], default=None,
                   help="Apply a recommended preset before config and CLI overrides.")
    p.add_argument("--pop", type=int, default=None)
    p.add_argument("--gen", type=int, default=None)
    p.add_argument("--top-n", type=int, default=None)
    p.add_argument("--outdir", default=None)

    p.add_argument("--len-mode", choices=["RANDOM", "FIX"], default=None)
    p.add_argument("--fix-length", type=int, default=None)
    p.add_argument("--min-length", type=int, default=None)
    p.add_argument("--max-length", type=int, default=None)
    p.add_argument("--length-count-mode", choices=["TOKEN", "RESIDUE", "EXPANDED"], default=None)
    p.add_argument("--trim-to-length", action=argparse.BooleanOptionalAction, default=None)

    p.add_argument("--target-mode", choices=["SINGLE", "MULTI", "BRIDGE"], default=None,
                   help="Shortcut mapped to SINGLE_TARGET / MULTI_TARGET_BINDER / BRIDGE_LINKER.")
    p.add_argument("--design-mode", choices=["SINGLE_TARGET", "MULTI_TARGET_BINDER", "BRIDGE_LINKER"], default=None)
    p.add_argument("--binder-mode", choices=["BALANCED", "AFFINITY_FIRST", "DEVELOPABILITY", "DUAL_BINDER", "CYCLIC_PEPTIDE"], default=None)
    p.add_argument("--docking-stage", choices=["OFF", "FINAL_TOP_ONLY", "EVERY_N_GENERATIONS"], default=None)
    p.add_argument("--docking-engine", choices=["NONE", "CUSTOM", "ROSETTA", "VINA", "DIFFDOCK"], default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--bridge-anchor-len", type=int, default=None)
    p.add_argument("--docking-ready-mode", choices=["BASIC", "ADVANCED"], default=None)
    p.add_argument("--docking-ready-bonus-weight", type=float, default=None)
    p.add_argument("--max-param-tokens", type=int, default=None)

    p.add_argument("--use-optional-ml", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--ml-rerank-weight", type=float, default=None)
    p.add_argument("--trained-model", default=None,
                   help="Path to models/surrogate_model.json made by ml_trainer.py; used for post-run reranking.")
    p.add_argument("--trained-ml-weight", type=float, default=0.25,
                   help="Blend weight for trained-model reranking.")

    p.add_argument("--import-training-data", nargs="*", default=None,
                   help="One or more AF3/PRODIGY/docking/experimental CSV files to append into data/training_data.csv.")
    p.add_argument("--parse-af3-folder", default=None,
                   help="Parse an AF3 output folder into canonical CSV and append to training DB.")
    p.add_argument("--parse-prodigy", default=None,
                   help="Parse a PRODIGY txt/csv/log file or folder into canonical CSV and append to training DB.")
    p.add_argument("--candidate-map", default=None,
                   help="Optional candidate mapping CSV for matching AF3/PRODIGY filenames to candidate_id/sequence/target_id.")
    p.add_argument("--parsed-output-dir", default=None,
                   help="Directory for parsed_af3_latest.csv / parsed_prodigy_latest.csv. Defaults to training DB folder.")
    p.add_argument("--training-db", default="data/training_data.csv")
    p.add_argument("--train-ml", action="store_true",
                   help="Train lightweight ridge surrogate from training-db and save to models/.")
    p.add_argument("--ml-label", default="experimental_binding",
                   help="Training label column, e.g. experimental_binding, prodigy_delta_g, docking_score, hplc_purity.")
    p.add_argument("--models-dir", default="models")

    p.add_argument("--prepare-pseudodocking-colab", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--receptor-sequence", default=None)
    p.add_argument("--pseudodock-topk", type=int, default=None)

    p.add_argument("--auto-hotspot", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--hotspot-source", choices=["SEQUENCE", "PDB"], default=None)
    p.add_argument("--hotspot-sequence", default=None)
    p.add_argument("--hotspot-pdb-file", default=None)
    p.add_argument("--hotspot-window", type=int, default=None)
    p.add_argument("--hotspot-topk", type=int, default=None)
    p.add_argument("--hotspot-lock-as-motif", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--hotspot-replace-targets", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--motif-position-mode", choices=["FREE", "N_TERM", "CENTER", "C_TERM"], default=None)
    p.add_argument("--motif-position-map-json", default=None)
    p.add_argument("--no-run", action="store_true", help="Only import/train data; do not run peptide generation.")

    args = p.parse_args()

    # 1) Start from engine defaults, then preset, then config file, then CLI overrides.
    cfg: Dict[str, Any] = dict(eng.CONFIG)
    cfg.update(apply_preset(args.preset))
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg.update(json.load(f))

    if args.target:
        cfg["TARGETS"] = parse_targets(args.target)
    if args.pop is not None:
        cfg["POP"] = args.pop
    if args.gen is not None:
        cfg["GEN"] = args.gen
    if args.top_n is not None:
        cfg["FINAL_TOPK"] = args.top_n
    if args.seed is not None:
        cfg["SEED"] = args.seed
    if args.target_mode is not None:
        cfg["DESIGN_MODE"] = {"SINGLE": "SINGLE_TARGET", "MULTI": "MULTI_TARGET_BINDER", "BRIDGE": "BRIDGE_LINKER"}[args.target_mode]
        cfg["TARGET_MODE_LABEL"] = args.target_mode
    if args.design_mode:
        cfg["DESIGN_MODE"] = args.design_mode
    if args.bridge_anchor_len is not None:
        cfg["BRIDGE_ANCHOR_LEN"] = args.bridge_anchor_len
    if args.docking_ready_mode:
        cfg["DOCKING_READY_MODE"] = args.docking_ready_mode
    if args.docking_ready_bonus_weight is not None:
        cfg["DOCKING_READY_BONUS_WEIGHT"] = args.docking_ready_bonus_weight
    if args.max_param_tokens is not None:
        cfg["MAX_PARAM_TOKENS"] = args.max_param_tokens
    if args.use_optional_ml is not None:
        cfg["USE_OPTIONAL_ML"] = args.use_optional_ml
    if args.ml_rerank_weight is not None:
        cfg["ML_RERANK_WEIGHT"] = args.ml_rerank_weight
    if args.prepare_pseudodocking_colab is not None:
        cfg["PREPARE_PSEUDODOCKING_COLAB"] = args.prepare_pseudodocking_colab
    if args.receptor_sequence is not None:
        cfg["RECEPTOR_SEQUENCE"] = args.receptor_sequence
    if args.pseudodock_topk is not None:
        cfg["PSEUDODOCKING_TOPK"] = args.pseudodock_topk
    if args.len_mode:
        cfg["LEN_MODE"] = args.len_mode
    if args.fix_length is not None:
        cfg["FIX_LENGTH"] = args.fix_length
    if args.min_length is not None:
        cfg["MIN_LENGTH"] = args.min_length
    if args.max_length is not None:
        cfg["MAX_LENGTH"] = args.max_length
    if args.length_count_mode:
        cfg["LENGTH_COUNT_MODE"] = args.length_count_mode
        cfg["LENGTH_METRIC"] = args.length_count_mode
    if args.trim_to_length is not None:
        cfg["TRIM_TO_LENGTH"] = args.trim_to_length
    if args.binder_mode:
        cfg["BINDER_MODE"] = args.binder_mode
    if args.docking_stage:
        cfg["DOCKING_STAGE"] = args.docking_stage
    if args.docking_engine:
        cfg["DOCKING_ENGINE"] = args.docking_engine
    if args.auto_hotspot is not None:
        cfg["AUTO_HOTSPOT"] = args.auto_hotspot
    if args.hotspot_source is not None:
        cfg["HOTSPOT_SOURCE"] = args.hotspot_source
    if args.hotspot_sequence is not None:
        cfg["HOTSPOT_SEQUENCE"] = args.hotspot_sequence
    if args.hotspot_pdb_file is not None:
        cfg["HOTSPOT_PDB_TEXT"] = Path(args.hotspot_pdb_file).read_text(encoding="utf-8")
        cfg["HOTSPOT_SOURCE"] = "PDB"
    if args.hotspot_window is not None:
        cfg["HOTSPOT_WINDOW"] = args.hotspot_window
    if args.hotspot_topk is not None:
        cfg["HOTSPOT_TOPK"] = args.hotspot_topk
    if args.hotspot_lock_as_motif is not None:
        cfg["HOTSPOT_LOCK_AS_MOTIF"] = args.hotspot_lock_as_motif
    if args.hotspot_replace_targets is not None:
        cfg["HOTSPOT_REPLACE_TARGETS"] = args.hotspot_replace_targets
    if args.motif_position_mode is not None:
        cfg["MOTIF_POSITION_MODE"] = args.motif_position_mode
    if args.motif_position_map_json is not None:
        cfg["MOTIF_POSITION_MAP"] = json.loads(args.motif_position_map_json)

    parsed_inputs: List[str] = []
    parsed_dir = Path(args.parsed_output_dir) if args.parsed_output_dir else Path(args.training_db).parent
    parsed_dir.mkdir(parents=True, exist_ok=True)

    if args.parse_af3_folder:
        if external_parsers is None:
            raise RuntimeError("external_parsers.py could not be imported.")
        parsed_af3 = parsed_dir / "parsed_af3_latest.csv"
        result = external_parsers.parse_af3_folder(args.parse_af3_folder, parsed_af3, mapping_csv=args.candidate_map)
        parsed_inputs.append(str(parsed_af3))
        print(f"✅ AF3 parsed: {result['rows']} rows -> {result['output_csv']}")

    if args.parse_prodigy:
        if external_parsers is None:
            raise RuntimeError("external_parsers.py could not be imported.")
        parsed_prod = parsed_dir / "parsed_prodigy_latest.csv"
        result = external_parsers.parse_prodigy_path(args.parse_prodigy, parsed_prod, mapping_csv=args.candidate_map)
        parsed_inputs.append(str(parsed_prod))
        print(f"✅ PRODIGY parsed: {result['rows']} rows -> {result['output_csv']}")

    import_inputs = list(args.import_training_data or []) + parsed_inputs
    if import_inputs:
        if data_manager is None:
            raise RuntimeError("data_manager.py could not be imported.")
        result = data_manager.append_training_csvs(import_inputs, args.training_db)
        print(f"✅ training data updated: {result['training_db']} | added={result['added']} | total={result['total']}")

    if args.train_ml:
        if ml_trainer is None:
            raise RuntimeError("ml_trainer.py could not be imported.")
        model_path = ml_trainer.train_from_csv(args.training_db, args.models_dir, label_col=args.ml_label)
        print(f"✅ surrogate model saved: {model_path}")

    if args.no_run:
        return

    rows, progress, paths = eng.run(cfg, verbose=True, outdir=args.outdir)

    if args.trained_model:
        if ml_trainer is None:
            raise RuntimeError("ml_trainer.py could not be imported.")
        reranked = ml_trainer.rerank_rows(rows, args.trained_model, blend_weight=args.trained_ml_weight)
        rerank_path = Path(paths["output_dir"]) / "trained_ml_reranked_candidates.csv"
        write_rows(rerank_path, reranked[:int(cfg.get("FINAL_TOPK", 10))])
        paths["trained_ml_reranked_csv"] = str(rerank_path)
        # Rebuild output ZIP so trained-model reranking CSV is included.
        out_dir = Path(paths["output_dir"])
        zip_path = out_dir.with_suffix(".zip")
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for pp in out_dir.rglob("*"):
                if pp.is_file():
                    z.write(pp, pp.relative_to(out_dir))
        paths["zip"] = str(zip_path)
        rows = reranked

    print("\n✅ DONE")
    print(f"Output ZIP: {paths.get('zip', '')}")
    print("\n🏆 Top candidates")
    for r in rows[:int(cfg.get("FINAL_TOPK", 10))]:
        print(f"{int(r.get('rank', 0)):>3} | score={float(r.get('total_score', 0)):.3f} | length={r.get('length')} | valid={r.get('valid')} | dock={r.get('docking_ready_level','NA')} | {r.get('sequence','')}")


if __name__ == "__main__":
    main()
