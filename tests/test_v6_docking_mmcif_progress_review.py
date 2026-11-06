"""Regression for user-facing direct docking: real poses, mmCIF receptor, truthful progress, shared viewer."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from peptiforg_core.v6_docking_inputs import prepare_structure_file
from peptiforg_core.native_docking_v1 import NativeDockingConfig
from peptiforg_core.v6_compute_pipeline import run_pipeline
from peptiforg_core.v6_docking_review_adapter import load_direct_docking_review
from tests.test_v5_native_docking_v1 import _write_pdb


def test_receptor_mmcif_real_coordinate_roundtrip(tmp_path):
    from Bio.PDB import MMCIFIO, PDBParser
    receptor = tmp_path / 'receptor.pdb'
    _write_pdb(receptor, 'A')
    structure = PDBParser(QUIET=True).get_structure('r', str(receptor))
    cif = tmp_path / 'receptor.mmcif'
    io = MMCIFIO(); io.set_structure(structure); io.save(str(cif))
    output = Path(prepare_structure_file(cif, tmp_path / 'converted', 'receptor'))
    assert output.is_file() and output.stat().st_size > 0
    from peptiforg_core.interface_quality import parse_pdb_atoms
    assert len(parse_pdb_atoms(output)) == len(parse_pdb_atoms(receptor))


def test_mmcif_through_actual_docking_and_results(tmp_path):
    from Bio.PDB import MMCIFIO, PDBParser
    receptor = tmp_path / 'receptor.pdb'
    peptide = tmp_path / 'peptide.pdb'
    _write_pdb(receptor, 'A')
    _write_pdb(peptide, 'P', offset=(20, 20, 20))
    io = MMCIFIO(); io.set_structure(PDBParser(QUIET=True).get_structure('r', str(receptor)))
    cif = tmp_path / 'receptor.cif'; io.save(str(cif))
    converted = prepare_structure_file(cif, tmp_path / 'input', 'receptor')
    messages = []
    report = run_pipeline(converted, peptide, tmp_path / 'results',
        config=NativeDockingConfig(poses=2, anchor_count=3, rotations_per_anchor=3,
          max_candidates=9, local_refine_steps=1), progress_callback=lambda pct, label: messages.append((pct, label)))
    assert report['status'] == 'DOCKING_COMPLETED_MD_NOT_REQUESTED', report
    assert Path(report['manifest']).is_file()
    normalized, info = load_direct_docking_review(report)
    assert info['verified_pose_count'] >= 1 and not info['error']
    assert len(normalized['poses']) == info['verified_pose_count']
    assert Path(normalized['poses'].iloc[0]['pose_pdb']).exists()
    assert messages[0][0] == 0.0
    assert any(0.10 < value < 0.88 for value, _ in messages), messages
    assert messages[-1][0] == 1.0
    assert all(0 <= value <= 1 for value, _ in messages)


def test_failed_report_never_claims_verified_poses(tmp_path):
    manifest = tmp_path / 'v6_compute_pipeline.json'
    manifest.write_text(json.dumps({'status': 'FAILED', 'error': 'mock error'}))
    result, info = load_direct_docking_review({'manifest': str(manifest), 'status': 'FAILED', 'error': 'mock error'})
    assert info == {'status': 'FAILED', 'verified_pose_count': 0, 'error': 'mock error'}
    assert result['poses'].empty


def test_gui_uses_queued_progress_and_result_adapter():
    gui = (Path(__file__).parents[1] / 'suite_gui' / 'pymol_structure_builder_gui.py').read_text()
    assert 'progress_callback=self._post_docking_progress' in gui
    assert 'self._drain_docking_progress()' in gui
    assert 'load_direct_docking_review(result)' in gui
    assert 'self.shared_native_result_panel.load_result(normalized' in gui
    assert 'No verified poses' in gui
