from pathlib import Path
import json

from peptiforg_core.native_docking_v1 import NativeDockingConfig, run_native_docking


def _write_pdb(path: Path, chain: str, offset=(0.0,0.0,0.0)):
    ox,oy,oz=offset
    atoms=[
        ("N","ALA",1,0,0,0,"N"),("CA","ALA",1,1.45,0,0,"C"),("C","ALA",1,2.4,1.0,0,"C"),("O","ALA",1,2.2,2.2,0,"O"),
        ("N","LYS",2,3.5,0.6,0,"N"),("CA","LYS",2,4.6,1.4,0,"C"),("C","LYS",2,5.8,0.6,0,"C"),("O","LYS",2,6.0,-0.6,0,"O"),("NZ","LYS",2,4.8,4.4,0,"N"),
        ("N","PHE",3,6.8,1.4,0,"N"),("CA","PHE",3,8.0,0.8,0,"C"),("C","PHE",3,9.0,1.8,0,"C"),("O","PHE",3,8.9,3.0,0,"O"),
        ("CG","PHE",3,8.0,-1.8,0,"C"),("CD1","PHE",3,9.1,-2.5,0,"C"),("CD2","PHE",3,6.9,-2.5,0,"C"),("CE1","PHE",3,9.1,-3.9,0,"C"),("CE2","PHE",3,6.9,-3.9,0,"C"),("CZ","PHE",3,8.0,-4.6,0,"C"),
    ]
    lines=[]
    for i,(atom,resn,resi,x,y,z,el) in enumerate(atoms,1):
        lines.append(f"ATOM  {i:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {x+ox:8.3f}{y+oy:8.3f}{z+oz:8.3f}  1.00  0.00          {el:>2s}")
    lines += ["TER","END"]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def test_native_docking_runs_without_external_backend(tmp_path):
    receptor=tmp_path/"receptor.pdb"; peptide=tmp_path/"peptide.pdb"
    _write_pdb(receptor,"A")
    _write_pdb(peptide,"P",offset=(20,20,20))
    cfg=NativeDockingConfig(poses=3,anchor_count=4,rotations_per_anchor=5,max_candidates=20,local_refine_steps=1)
    result=run_native_docking(receptor,peptide,tmp_path/"out",config=cfg)
    assert result["status"] == "COMPLETED"
    assert result["engine"] == "Pepforge Native Docking v1"
    assert result["evidence_grade"] == "EXPERIMENTAL_NATIVE"
    assert 1 <= result["selected_pose_count"] <= 3
    assert "binding free energy" in result["claim_guard"]
    for pose in result["poses"]:
        assert Path(pose["pose_pdb"]).exists()
        assert Path(pose["interaction_evidence_csv"]).exists()


def test_native_docking_manual_requires_residues(tmp_path):
    receptor=tmp_path/"r.pdb"; peptide=tmp_path/"p.pdb"
    _write_pdb(receptor,"A"); _write_pdb(peptide,"P",offset=(20,20,20))
    cfg=NativeDockingConfig(mode="manual",poses=1,anchor_count=2,rotations_per_anchor=2)
    try:
        run_native_docking(receptor,peptide,tmp_path/"o",config=cfg)
    except ValueError as e:
        assert "requires binding_residues" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_native_docking_manual_residue_mode(tmp_path):
    receptor=tmp_path/"r.pdb"; peptide=tmp_path/"p.pdb"
    _write_pdb(receptor,"A"); _write_pdb(peptide,"P",offset=(20,20,20))
    cfg=NativeDockingConfig(mode="manual",poses=2,anchor_count=2,rotations_per_anchor=3,max_candidates=6)
    result=run_native_docking(receptor,peptide,tmp_path/"o",config=cfg,binding_residues=["A:2"])
    assert result["status"] == "COMPLETED"
    assert result["binding_residues"] == ["A:2"]
