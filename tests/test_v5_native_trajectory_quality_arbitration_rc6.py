from pathlib import Path
import numpy as np

from peptiforg_core.quality_arbitration_v1 import arbitrate_candidates
from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.native_trajectory_analysis_v1 import analyze_native_frames
from peptiforg_core.native_mechanics_v1 import run_native_mechanics, NativeMechanicsConfig


def test_quality_arbitration_prefers_pass_over_richer_fail():
    r=arbitrate_candidates([
        {"name":"native","native":True,"richness":30,"quality_gate":{"status":"PASS"}},
        {"name":"optional","native":False,"richness":300,"quality_gate":{"status":"FAIL"}},
    ])
    assert r["status"]=="SELECTED"
    assert r["selected"]["name"]=="native"


def test_quality_arbitration_prefers_richer_when_same_quality():
    r=arbitrate_candidates([
        {"name":"native","native":True,"richness":30,"quality_gate":{"status":"PASS"}},
        {"name":"optional","native":False,"richness":100,"quality_gate":{"status":"PASS"}},
    ])
    assert r["selected"]["name"]=="optional"


def test_native_trajectory_analysis_from_pdb_frames(tmp_path: Path):
    base=export_native_backbone("EEMQRR",tmp_path/"base")
    p=Path(base["pdb"])
    text=p.read_text()
    frames=[]
    for i in range(4):
        fp=tmp_path/f"f{i}.pdb"
        # rigid translations should align away to near-zero RMSD
        lines=[]
        for line in text.splitlines():
            if line.startswith(("ATOM  ","HETATM")):
                x=float(line[30:38])+i*0.2
                y=float(line[38:46])-i*0.1
                z=float(line[46:54])+i*0.05
                line=line[:30]+f"{x:8.3f}{y:8.3f}{z:8.3f}"+line[54:]
            lines.append(line)
        fp.write_text("\n".join(lines)+"\n")
        frames.append(fp)
    r=analyze_native_frames(frames,tmp_path/"analysis",clusters=2)
    assert r["status"]=="COMPLETED"
    assert r["frame_count"]==4
    assert r["max_rmsd_A"] < 1e-3
    assert Path(r["clusters_csv"]).exists()


def test_native_mechanics_emits_native_trajectory_analysis(tmp_path: Path):
    base=export_native_backbone("EEMQRR",tmp_path/"base")
    r=run_native_mechanics(base["pdb"],tmp_path/"mech",config=NativeMechanicsConfig(steps=4,save_every=2))
    ta=r["native_trajectory_analysis"]
    assert ta["status"]=="COMPLETED"
    assert ta["frame_count"]>=3
    assert Path(ta["frame_metrics_csv"]).exists()
