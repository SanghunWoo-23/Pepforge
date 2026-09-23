from __future__ import annotations

from pathlib import Path

import pandas as pd

from apps.hotspot_finder.sequence_hotspot_finder.engine import analyze_input
from apps.hotspot_finder.sequence_hotspot_finder.ranking import rank_hotspot_regions

ROOT = Path(__file__).resolve().parents[1]


def _synthetic_scored_df() -> pd.DataFrame:
    seq = "ACDEFGHIKLMNPQRSTVWYACDEFGHIK"
    rows = []
    for idx, aa in enumerate(seq, start=1):
        charged = 1.0 if aa in "KRDE" else 0.0
        aromatic = 1.0 if aa in "FWY" else 0.0
        rows.append(
            {
                "record_name": "input",
                "model_position": idx,
                "model_token": aa,
                "hotspot_score": min(1.0, 0.1 + 0.08 * charged + 0.12 * aromatic + idx / 100.0),
                "aromatic_flag": aromatic,
                "positive_flag": 1.0 if aa in "KR" else 0.0,
                "negative_flag": 1.0 if aa in "DE" else 0.0,
                "polar_flag": 1.0 if aa in "STNQYCHDEKR" else 0.0,
                "special_flag": 1.0 if aa in "CGP" else 0.0,
                "abs_charge": charged,
                "hydrophobicity_norm": 0.55,
            }
        )
    return pd.DataFrame(rows)


def test_region_ranker_produces_numbered_nonempty_regions():
    ranked = rank_hotspot_regions(_synthetic_scored_df(), top_n=6, window_size=9, overlap=3)
    assert not ranked.empty
    assert list(ranked["rank"]) == list(range(1, len(ranked) + 1))
    assert ranked["region_sequence"].astype(str).str.len().min() >= 1
    assert ranked["region_start"].le(ranked["center_position"]).all()
    assert ranked["center_position"].le(ranked["region_end"]).all()
    assert ranked["priority_score"].between(0, 1).all()
    assert ranked["claim_guard"].str.contains("not a binding probability", case=False).all()


def test_engine_exports_ranked_region_csv(tmp_path: Path):
    seq = "MKWVTFISLLLLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVK"
    result = analyze_input(
        seq,
        token_db_path=ROOT / "apps" / "hotspot_finder" / "data" / "token_db.csv",
        sidechain_mod_db_path=ROOT / "apps" / "hotspot_finder" / "data" / "sidechain_mod_db.csv",
        outdir=tmp_path,
        config={"use_esm": False, "top_n": 10, "ranking_window_size": 15, "ranking_overlap": 5},
    )
    ranked = result["ranked_regions_df"]
    assert not ranked.empty
    assert Path(result["ranked_regions_csv"]).exists()
    assert {"rank", "region_sequence", "priority_score", "hotspot_residues"}.issubset(ranked.columns)


def test_workflow_uses_readonly_rank_dropdown_and_embedded_pde_handoff():
    src = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'text="Run Hot Spot + Rank"' in src
    assert 'state="readonly"' in src
    assert 'text="PDE target sequence"' in src
    assert 'text="Run PDE"' in src
    assert "self.pde_target_var.set(sequence)" in src
    assert "hotspot_ranked_regions" in src
    assert "Create selected_hotspots_for_design.csv" not in src
    assert 'text="Open selected in PDE"' not in src


def test_pde_accepts_workflow_selected_target_sequence():
    src = (ROOT / "apps" / "peptide_design_engine" / "Python" / "desktop_gui.py").read_text(encoding="utf-8")
    assert 'PEPFORGE_WORKFLOW_TARGET_SEQUENCE' in src
    assert 'self.var_targets = tk.StringVar(value=workflow_target)' in src


def test_psb_primary_build_button_is_neutral_and_named_build_structure():
    src = (ROOT / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert '("Build Structure", self.export)' in src
    assert '"Build Top 5 Structures"' not in src
    assert 'style="Accent.TButton" if idx == 1 else "TButton"' not in src
