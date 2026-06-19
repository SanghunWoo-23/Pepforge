
# =========================================================
# Peptide Design Engine - VERIFIED COLAB RUN
# =========================================================
from IPython.display import display, Markdown
import datetime
from pathlib import Path
import zipfile
import numpy as np

LAST_RESULTS = {}

def _try_pandas_table(rows, n=10):
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        priority = [
            "rank", "sequence", "clean_sequence",
            "binding_target_hotspot_sequence",
            "binding_target_hotspot_range",
            "binding_target_hotspot_start",
            "binding_target_hotspot_end",
            "binding_target_hotspot_chain",
            "binding_target_hotspot_source",
            "peptide_to_target_hotspot",
            "all_target_hotspots_used",
            "all_target_hotspot_ranges",
            "hotspot_status",
            "target_hotspot_sequences",
            "hotspot_peptide_map",
            "best_hotspot",
            "total_score", "length", "residue_length", "category",
            "has_label", "has_base_chem", "has_tag", "nterm_tokens"
        ]
        cols = [c for c in priority if c in df.columns] + [c for c in df.columns if c not in priority]
        return df[cols].head(n)
    except Exception:
        return rows[:n]

def _plot_progress(progress):
    try:
        import matplotlib.pyplot as plt
        gens = [p["generation"] for p in progress]
        best = [p["best_score"] for p in progress]
        mean = [p["mean_score"] for p in progress]
        valid = [p["valid_ratio"] for p in progress]
        plt.figure(figsize=(7,4))
        plt.plot(gens, best, label="best")
        plt.plot(gens, mean, label="mean")
        plt.xlabel("Generation")
        plt.ylabel("Score")
        plt.title("Evolution Progress")
        plt.grid(True)
        plt.legend()
        plt.show()

        plt.figure(figsize=(7,4))
        plt.plot(gens, valid, label="valid ratio")
        plt.xlabel("Generation")
        plt.ylabel("Valid ratio")
        plt.title("Validation Ratio")
        plt.grid(True)
        plt.show()
    except Exception as e:
        print("Plot skipped:", e)

def _plot_scores(rows):
    try:
        import matplotlib.pyplot as plt
        scores = [float(r["total_score"]) for r in rows]
        lengths = [float(r["length"]) for r in rows]
        plt.figure(figsize=(7,4))
        plt.hist(scores, bins=20)
        plt.xlabel("Total score")
        plt.ylabel("Count")
        plt.title("Score Distribution")
        plt.grid(True)
        plt.show()

        plt.figure(figsize=(7,4))
        plt.scatter(lengths, scores)
        plt.xlabel("Unified LENGTH")
        plt.ylabel("Total score")
        plt.title("Length vs Score")
        plt.grid(True)
        plt.show()
    except Exception as e:
        print("Plot skipped:", e)

def run_pipeline(b):
    output.clear_output()
    with output:
        cfg = build_config()
        print("[RUN] START VERIFIED LENGTH-ONLY PIPELINE")
        print(f"Length mode: {cfg['LEN_MODE']} | RANGE: {cfg['MIN_LENGTH']}-{cfg['MAX_LENGTH']} | FIX: {cfg['FIX_LENGTH']}")
        print("Normalized length settings are applied before engine execution.")
        print(f"Length count: {cfg['LENGTH_COUNT_MODE']} | Binder: {cfg['BINDER_MODE']}")
        print(f"Docking stage: {cfg['DOCKING_STAGE']} | Docking engine: {cfg['DOCKING_ENGINE']}")

        rows, progress, paths = run(cfg, verbose=True)

        print("[OK] DONE")
        print(f"Hotspot status: {CONFIG.get('_HOTSPOT_STATUS', '')}")

        # Explicit hotspot display for Colab users.
        hs = []
        try:
            hs = CONFIG.get("_EXTRACTED_HOTSPOTS", [])
        except Exception:
            hs = []
        if hs:
            print("\n[TARGET] Extracted target hotspots used for design")
            for i, h in enumerate(hs, 1):
                print(f"{i}. {h.get('motif','')} | range={h.get('chain','')}:{h.get('start','')}-{h.get('end','')} | source={h.get('source','')} | score={h.get('score','')}")
            print("\n[LINK] Peptide-hotspot mapping columns are included in results_top.csv:")
            print("- target_hotspot_sequences")
            print("- hotspot_peptide_map")
            print("- best_hotspot")
            print("- hotspot_source_sequence_used")
            print("- hotspot_peptide_pairs.csv")
            print("- hotspot_debug_visualization.csv")
            print("- binding_target_hotspot")
            print("- peptide_to_target_hotspot")
            print("- hotspot_status")
        else:
            print("\n[TARGET] No extracted hotspots found. If you want automatic hotspot extraction, turn Auto hotspot ON and provide ProteinSeq/PDB, or paste a protein sequence into Targets.")

        print("\n[TOP] Top candidates")
        display(_try_pandas_table(rows, cfg.get("FINAL_TOPK", 10)))

        print("\n[PLOTS] Plots")
        _plot_progress(progress)
        _plot_scores(rows)

        print("\n[FILES] Saved files:")
        for k, v in paths.items():
            print(f"- {k}: {v}")

        LAST_RESULTS.clear()
        LAST_RESULTS.update({"rows": rows, "progress": progress, "paths": paths, "config": cfg})

        try:
            from google.colab import files
            files.download(paths["zip"])
        except Exception:
            pass

run_button.on_click(run_pipeline)
