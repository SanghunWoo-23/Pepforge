from __future__ import annotations

import json
from pathlib import Path

from peptiforg_core.psb_v5_orchestrator import prepare_psb_docking_plan


def _pdb(path: Path, chain: str = "A") -> Path:
    path.write_text(
        f"ATOM      1  CA  ALA {chain}   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n",
        encoding="utf-8",
    )
    return path


def test_prepare_plan_creates_five_jobs_but_no_fake_poses(tmp_path: Path):
    models = []
    top = []
    for rank in range(1, 6):
        p = _pdb(tmp_path / f"pep_rank{rank}.pdb", chain="P")
        models.append(str(p))
        top.append({"rank": rank, "conf_id": rank + 10, "family": "coil_mixed", "energy": float(rank), "severe_steric_clashes": 0})
    meta = tmp_path / "pep.json"
    meta.write_text(json.dumps({
        "input": "EEMQRR",
        "top5_conformer_pdb_paths": models,
        "conformation_analysis": {"top_conformers": top},
    }), encoding="utf-8")
    receptor = _pdb(tmp_path / "receptor.pdb")
    result = prepare_psb_docking_plan(meta, receptor, tmp_path / "run", pose_limit_per_model=5)
    plan = json.loads(Path(result["run_plan_json"]).read_text(encoding="utf-8"))
    assert len(plan["models"]) == 5
    assert len(plan["jobs"]) == 5
    assert all(job["status"] == "PREPARED_NOT_RUN" for job in plan["jobs"])
    assert all(job["requested_pose_limit"] == 5 for job in plan["jobs"])
    assert not list((tmp_path / "run").rglob("*pose*.pdb"))
    lineage = json.loads(Path(result["lineage_json"]).read_text(encoding="utf-8"))
    assert len(lineage["records"]) == 5
    assert all(not row["pose_id"] for row in lineage["records"])


def test_guided_mode_requires_residues(tmp_path: Path):
    p = _pdb(tmp_path / "pep_rank1.pdb", chain="P")
    meta = tmp_path / "pep.json"
    meta.write_text(json.dumps({
        "input": "AAAA",
        "top5_conformer_pdb_paths": [str(p)],
        "conformation_analysis": {"top_conformers": [{"rank": 1, "conf_id": 1, "family": "alpha_helix_like"}]},
    }), encoding="utf-8")
    receptor = _pdb(tmp_path / "receptor.pdb")
    try:
        prepare_psb_docking_plan(meta, receptor, tmp_path / "run", binding_site_mode="hotspot")
    except ValueError as exc:
        assert "requires at least one binding-site residue" in str(exc)
    else:
        raise AssertionError("hotspot mode should require residue restraints")
