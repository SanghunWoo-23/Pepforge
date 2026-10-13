from pathlib import Path
import numpy as np

from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.native_docking_benchmark_v1 import evaluate_complex_against_reference, benchmark_model_set
from peptiforg_core.native_mechanics_validation_v1 import finite_difference_force_check, validate_native_mechanics


def _merge_complex(a_pdb: str, p_pdb: str, out: Path, ligand_shift=(0.0,0.0,0.0)) -> str:
    lines=[]; serial=1
    for path,shift in [(a_pdb,(0,0,0)),(p_pdb,ligand_shift)]:
        for line in Path(path).read_text().splitlines():
            if not line.startswith(("ATOM","HETATM")):
                continue
            x=float(line[30:38])+shift[0]; y=float(line[38:46])+shift[1]; z=float(line[46:54])+shift[2]
            line=f"{line[:6]}{serial:5d}{line[11:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"
            lines.append(line); serial+=1
    out.write_text("\n".join(lines)+"\nEND\n")
    return str(out)


def test_reference_benchmark_identity_and_shift(tmp_path):
    r=export_native_backbone("AAAAAAAAAA",tmp_path/"r",chain="A")["pdb"]
    p=export_native_backbone("EEMQRR",tmp_path/"p",chain="P")["pdb"]
    ref=_merge_complex(r,p,tmp_path/"ref.pdb",ligand_shift=(0.0,4.0,0.0))
    same=_merge_complex(r,p,tmp_path/"same.pdb",ligand_shift=(0.0,4.0,0.0))
    far=_merge_complex(r,p,tmp_path/"far.pdb",ligand_shift=(7.0,4.0,0.0))
    m=evaluate_complex_against_reference(ref,same)
    assert m["fnat_like"] == 1.0
    assert m["lrmsd_A"] < 1e-6
    assert m["irmsd_A"] < 1e-6
    assert m["dockq_compatible"] > 0.999999
    m2=evaluate_complex_against_reference(ref,far)
    assert m2["lrmsd_A"] > 1.0
    s=benchmark_model_set(ref,[same,far],tmp_path/"bench")
    assert s["models_evaluated"] == 2
    assert s["best_dockq_compatible"] > 0.99


def test_native_force_is_negative_score_gradient(tmp_path):
    p=export_native_backbone("AAAA",tmp_path/"p",chain="P")["pdb"]
    r=finite_difference_force_check(p)
    assert r["status"] == "PASS"
    assert r["max_abs_force_error"] < 2e-4 or r["max_rel_force_error"] < 2e-4


def test_native_mechanics_validation_harness(tmp_path):
    p=export_native_backbone("AAAA",tmp_path/"p",chain="P")["pdb"]
    r=validate_native_mechanics(p,tmp_path/"validation")
    assert r["status"] == "PASS"
    assert r["validation_scope"] == "SOFTWARE_NUMERICAL_CONSISTENCY_ONLY"
