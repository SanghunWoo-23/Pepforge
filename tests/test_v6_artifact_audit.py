import json
from pathlib import Path
from peptiforg_core.v6_artifact_audit import audit_ensemble_run, _digest


def _mock_run(tmp_path):
    root = tmp_path / 'run'; root.mkdir()
    p = root / 'input_snapshots'; p.mkdir()
    a = p / 'receptor.pdb'; a.write_text('ATOM')
    b = p / 'modified_peptide.sdf'; b.write_text('SDF')
    data = {'schema':'pepforge.v6.ensemble_docking.v1','status':'PARTIAL_OR_FAILED',
            'inputs': {'receptor_snapshot': str(a), 'receptor_sha256': _digest(a),
                       'peptide_snapshot': str(b), 'peptide_sdf_sha256': _digest(b)},
            'runs': [], 'successful_conformers': 0,'failed_conformers': 0}
    (root / 'ensemble_docking_report.json').write_text(json.dumps(data))
    return root, a


def test_audit_good_hashes(tmp_path):
    root, _ = _mock_run(tmp_path)
    assert audit_ensemble_run(root)['status'] == 'PASS'


def test_audit_tampered_input(tmp_path):
    root, a = _mock_run(tmp_path)
    a.write_text('OTHER')
    assert audit_ensemble_run(root)['status'] == 'FAIL'


def test_audit_external_path_rejected(tmp_path):
    root, a = _mock_run(tmp_path)
    report = root / 'ensemble_docking_report.json'
    data = json.loads(report.read_text())
    data['inputs']['receptor_snapshot'] = str(tmp_path / 'external.pdb')
    report.write_text(json.dumps(data))
    assert audit_ensemble_run(root)['status'] == 'FAIL'
