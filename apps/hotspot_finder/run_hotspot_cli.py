#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from sequence_hotspot_finder.engine import analyze_input, load_config


def main():
    p = argparse.ArgumentParser(description="Sequence Hotspot Finder v1.0 CLI")
    p.add_argument("--input", required=True, help="Input FASTA/text file")
    p.add_argument("--outdir", default="outputs", help="Output directory")
    p.add_argument("--config", default="data/default_config.json", help="Config JSON")
    p.add_argument("--token-db", default="data/token_db.csv", help="Token DB CSV")
    p.add_argument("--sidechain-mod-db", default="data/sidechain_mod_db.csv", help="Side-chain modification DB CSV")
    p.add_argument("--domains", default=None, help="Optional domain CSV")
    p.add_argument("--structure-features", default=None, help="Optional structure feature CSV")
    p.add_argument("--conservation-features", default=None, help="Optional conservation CSV")
    p.add_argument("--supervised-features", default=None, help="Optional supervised score CSV with supervised_score column")
    p.add_argument("--no-esm", action="store_true", help="Disable ESM features")
    p.add_argument("--use-esm", action="store_true", help="Enable ESM features")
    p.add_argument("--model", default=None, help="ESM model name")
    p.add_argument("--window", type=int, default=None, help="Window size")
    p.add_argument("--overlap", type=int, default=None, help="Window overlap")
    p.add_argument("--batch-size", type=int, default=None, help="ESM batch size")
    p.add_argument("--merge-position-mode", choices=["model_position", "display_position", "original_position", "residue_position"], default=None)
    args = p.parse_args()

    cfg = load_config(args.config)
    if args.no_esm: cfg["use_esm"] = False
    if args.use_esm: cfg["use_esm"] = True
    if args.model: cfg["esm_model"] = args.model
    if args.window: cfg["window_size"] = args.window
    if args.overlap: cfg["overlap"] = args.overlap
    if args.batch_size: cfg["batch_size"] = args.batch_size
    if args.merge_position_mode: cfg["merge_position_mode"] = args.merge_position_mode

    text = Path(args.input).read_text(encoding="utf-8")
    result = analyze_input(
        user_input=text,
        config=cfg,
        token_db_path=args.token_db,
        sidechain_mod_db_path=args.sidechain_mod_db,
        outdir=args.outdir,
        domains_path=args.domains,
        structure_features_path=args.structure_features,
        conservation_features_path=args.conservation_features,
        supervised_features_path=args.supervised_features,
    )
    print("Analysis complete")
    print("Full CSV:", result["full_csv"])
    print("Top CSV :", result["top_csv"])
    print("ZIP     :", result["zip_path"])

if __name__ == "__main__":
    main()
