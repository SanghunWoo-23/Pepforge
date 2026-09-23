from pathlib import Path

from peptiforg_core.pymol_structure_builder import (
    _prepare_safe_output_dir,
    export_modified_peptide_coordinate_seed,
    export_modified_peptide_structure,
)
from peptiforg_core.structure_file_analyzer import analyze_structure_files
from spps_v4_gui import catalogs
from spps_v4_gui.calculation_context import canonical as calc_canonical


def test_unicode_output_dir_uses_ascii_stage(tmp_path):
    requested = tmp_path / "박봉이" / "구조출력"
    requested_dir, stage_dir, staged = _prepare_safe_output_dir(requested, namespace="ui_regression")
    assert requested_dir == requested
    assert requested_dir.exists()
    assert stage_dir.exists()
    assert staged is True
    assert str(stage_dir).isascii()


def test_coordinate_seed_export_survives_unicode_output_dir(tmp_path):
    outdir = tmp_path / "박봉이" / "도킹출력"
    paths = export_modified_peptide_coordinate_seed("Ac-EEMQRR-NH2", outdir, name="screening_peptide")
    sdf = Path(paths["sdf"])
    pdb = Path(paths["pdb"])
    assert sdf.exists() and sdf.stat().st_size > 0
    assert pdb.exists() and pdb.stat().st_size > 0
    assert sdf.parent == outdir
    assert pdb.parent == outdir


def test_psb_ranked_outputs_use_compact_rank_names(tmp_path):
    paths = export_modified_peptide_structure("LHPTEVLWFCN", tmp_path, name="LHPTEVLWFCN")
    top1 = Path(paths["top1_pdb"])
    assert top1.exists()
    assert top1.name.endswith("_rank1.pdb")
    assert "coil" not in top1.name.lower()
    assert "top1_canonical_view_pdb" not in paths


def test_structure_file_analysis_accepts_pdb_and_sdf_outputs(tmp_path):
    seed = export_modified_peptide_coordinate_seed("Ac-EEMQRR-NH2", tmp_path / "seed", name="screening_peptide")
    analysis = analyze_structure_files([seed["pdb"], seed["sdf"]], tmp_path / "analysis", name="screening_seed_structures")
    assert Path(analysis["summary_csv"]).exists()
    assert Path(analysis["summary_json"]).exists()
    assert analysis["file_count"] == 2
    assert analysis["model_count"] >= 2


def test_spps_ac2o_display_is_consistent():
    raw = "Acetic anhydride (Ac2O) for N-terminal acetylation"
    assert catalogs.canonical_unit_name(raw) == "Acetic anhydride (Ac2O)"
    assert calc_canonical(raw) == "Acetic anhydride (Ac2O)"


def test_workflow_shared_sequence_panel_remains_rectangular_and_redundant_runtime_panel_is_removed():
    import inspect
    from peptiforg_core.workflow_gui import WorkflowApp
    source = inspect.getsource(WorkflowApp._build)
    assert 'seqbox = tk.Frame' in source
    assert 'logbox = tk.Frame' not in source
    assert 'Evidence / Runtime Status' not in source
    assert source.count('highlightthickness=1') >= 1
    assert 'proj = ttk.LabelFrame' in source
    assert 'steps = ttk.LabelFrame' in source
