from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

"""Low-spec peptide simulation and validation bridge utilities for Pepforge v2.1.0.

This module intentionally does not claim to replace Vina, OpenMM, GROMACS, AMBER,
or experimental binding assays.  It provides CPU-light conformer screening,
structure sanity metrics, parameter-requirement reporting, and external-validation
package templates so a modified peptide can be inspected locally and later moved
to an all-atom workflow.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List
import csv
import json
import shutil
import tempfile
import math
import re

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolDescriptors
except Exception:  # pragma: no cover
    Chem = None
    AllChem = None
    rdMolDescriptors = None

from pepforge_structure_tool.pepforge_core import build_structure, describe_parse, VERSION as STRUCTURE_TOOL_VERSION
from pepforge_structure_tool.pymol_script import make_pymol_pml

BRIDGE_VERSION = "2.1.0"

PARAMETER_CLASSES = {
    "std_aa": ("standard amino acid", "usually covered by standard protein force fields after residue/protonation review"),
    "d_std_aa": ("D-form residue", "requires D-residue topology/chirality review"),
    "non_natural_aa": ("non-natural amino acid", "requires non-standard residue parameters or curated template"),
    "linker": ("linker/spacer", "requires linker topology and partial charges for all-atom MD"),
    "label": ("chemical label", "requires small-molecule/dye parameters and charge validation"),
    "chemical": ("chemical modifier", "requires small-molecule/lipid-like parameters and charge validation"),
    "sidechain_label_aa": ("side-chain modified residue", "requires residue-linker-label parameterization"),
    "n_terminal": ("N-terminal cap", "requires correct terminal patch/parameter check"),
    "c_terminal": ("C-terminal cap", "requires correct terminal patch/parameter check"),
    "c_terminal_atom": ("C-terminal atom", "requires terminal-state consistency check"),
}


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "modified_peptide")).strip("_") or "modified_peptide"


def _mol_from_sdf(path: str | Path):
    if Chem is None:
        raise RuntimeError("RDKit is not available; low-spec conformer metrics require RDKit.")
    suppl = Chem.SDMolSupplier(str(path), removeHs=False)
    mols = [m for m in suppl if m is not None]
    if not mols:
        raise RuntimeError(f"No molecule could be read from {path}")
    return mols


def _conformer_coords(mol, conf_id: int = 0):
    conf = mol.GetConformer(conf_id)
    return [(float(conf.GetAtomPosition(i).x), float(conf.GetAtomPosition(i).y), float(conf.GetAtomPosition(i).z)) for i in range(mol.GetNumAtoms())]


def _distance(a, b) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


def _nonbonded_clash_count(mol, conf_id: int = 0, cutoff: float = 1.15) -> int:
    coords = _conformer_coords(mol, conf_id)
    bonded = set()
    for bond in mol.GetBonds():
        i, j = int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx())
        bonded.add((min(i, j), max(i, j)))
    count = 0
    heavy = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
    for ix, i in enumerate(heavy):
        for j in heavy[ix+1:]:
            if (min(i, j), max(i, j)) in bonded:
                continue
            # Ignore 1-3 interactions to reduce false positives in small fragments.
            try:
                if len(Chem.GetShortestPath(mol, i, j)) <= 3:
                    continue
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
            if _distance(coords[i], coords[j]) < cutoff:
                count += 1
    return count


def _end_to_end_distance(mol, conf_id: int = 0) -> float | None:
    heavy = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
    if len(heavy) < 2:
        return None
    coords = _conformer_coords(mol, conf_id)
    return _distance(coords[heavy[0]], coords[heavy[-1]])


def _radius_of_gyration(mol, conf_id: int = 0) -> float | None:
    if rdMolDescriptors is None:
        return None
    try:
        return float(rdMolDescriptors.CalcRadiusOfGyration(mol, confId=conf_id))
    except Exception:
        return None


def _estimate_flexibility(tokens: List[Dict[str, Any]], heavy_atoms: int) -> float:
    linker_count = sum(1 for t in tokens if t.get("kind") == "linker")
    mod_count = sum(1 for t in tokens if t.get("kind") in {"label", "chemical", "sidechain_label_aa"})
    residue_like = sum(1 for t in tokens if t.get("kind") in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"})
    return round(0.08 * max(0, residue_like - 3) + 0.35 * linker_count + 0.25 * mod_count + 0.003 * max(0, heavy_atoms - 60), 3)


def _claim_status(evidence_grade: str) -> str:
    if evidence_grade in {"A", "B"}:
        return "strong screening candidate; external all-atom/experimental validation required"
    if evidence_grade == "C":
        return "review candidate; inspect geometry, contacts, and parameter requirements"
    return "low-confidence screening result; do not make quantitative binding claims"


def compute_structure_evidence(meta: Dict[str, Any], conformer_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    tokens = list(meta.get("tokens") or [])
    warnings = list(meta.get("warnings") or [])
    nonstandard = [t for t in tokens if t.get("kind") in {"d_std_aa", "non_natural_aa", "linker", "label", "chemical", "sidechain_label_aa"}]
    best = conformer_rows[0] if conformer_rows else {}
    clash = float(best.get("internal_clash_count") or 0)
    rg = best.get("radius_of_gyration_A")
    end = best.get("end_to_end_distance_A")
    heavy_atoms = int(meta.get("heavy_atoms") or 0)
    flexibility_penalty = _estimate_flexibility(tokens, heavy_atoms)

    score = 100.0
    score -= 9.0 * clash
    score -= 4.0 * len(warnings)
    score -= 2.0 * len(nonstandard)
    score -= 12.0 * flexibility_penalty
    if rg is None or end is None:
        score -= 8.0
    if heavy_atoms > 120:
        score -= 5.0
    score = max(0.0, min(100.0, score))

    if score >= 82:
        grade = "A"
    elif score >= 68:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"

    return {
        "bridge_version": BRIDGE_VERSION,
        "structure_tool_version": STRUCTURE_TOOL_VERSION,
        "evidence_grade": grade,
        "structure_readiness_score_0_100": round(score, 2),
        "claim_status": _claim_status(grade),
        "predicted_binding_claim_allowed": "No. This report supports screening/evidence grading only, not final Kd or true nM binder claims.",
        "recommended_next_step": "Use exported validation package for external docking/all-atom MD or experimental validation when quantitative claims are required.",
        "nonstandard_token_count": len(nonstandard),
        "warning_count": len(warnings),
        "best_internal_clash_count": int(clash),
        "flexibility_penalty": flexibility_penalty,
        "heavy_atoms": heavy_atoms,
        "formula": meta.get("formula"),
        "exact_mw": meta.get("exact_mw"),
    }


def conformer_metric_rows(sdf_path: str | Path, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    mols = _mol_from_sdf(sdf_path)
    energy_map: Dict[int, Any] = {}
    for row in (meta.get("conformer_summary") or {}).get("energies") or []:
        try:
            energy_map[int(row.get("conf_id"))] = row.get("energy")
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    rows: List[Dict[str, Any]] = []
    for idx, mol in enumerate(mols, start=1):
        conf_id = 0
        rg = _radius_of_gyration(mol, conf_id)
        e2e = _end_to_end_distance(mol, conf_id)
        heavy = int(sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1))
        clash = _nonbonded_clash_count(mol, conf_id)
        energy = energy_map.get(idx - 1)
        rows.append({
            "conformer_rank": idx,
            "source_conf_id": idx - 1,
            "mmff_or_uff_energy": energy if energy is not None else "",
            "radius_of_gyration_A": round(rg, 3) if rg is not None else "",
            "end_to_end_distance_A": round(e2e, 3) if e2e is not None else "",
            "heavy_atoms": heavy,
            "internal_clash_count": clash,
            "compactness_index": round((rg or 0.0) / math.sqrt(max(1, heavy)), 4) if rg is not None else "",
            "interpretation": "lower clash count and reasonable compactness are preferred for screening-ready conformers",
        })
    rows.sort(key=lambda r: (int(r.get("internal_clash_count") or 999), float(r.get("mmff_or_uff_energy") or 1e9) if str(r.get("mmff_or_uff_energy")) else 1e9))
    return rows


def parameter_requirement_rows(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, tok in enumerate(meta.get("tokens") or [], start=1):
        kind = str(tok.get("kind") or "unknown")
        pclass, requirement = PARAMETER_CLASSES.get(kind, (kind, "manual review required"))
        rows.append({
            "index": i,
            "token": tok.get("raw", ""),
            "kind": kind,
            "parameter_class": pclass,
            "requirement": requirement,
            "all_atom_ready_inside_pepforge": "no" if kind in {"d_std_aa", "non_natural_aa", "linker", "label", "chemical", "sidechain_label_aa"} else "check",
            "note": tok.get("note", ""),
        })
    return rows


def _write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_external_templates(out: Path, name: str, evidence: Dict[str, Any]) -> Dict[str, str]:
    templates = out / "all_atom_validation_bridge"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "vina_config_template.txt").write_text(
        "# AutoDock Vina template generated by Pepforge v2.1.0\n"
        "# Fill receptor/ligand paths after preparing PDBQT files externally.\n"
        "receptor = receptor_cleaned.pdbqt\n"
        f"ligand = {name}.pdbqt\n"
        "center_x = 0\ncenter_y = 0\ncenter_z = 0\n"
        "size_x = 22\nsize_y = 22\nsize_z = 22\n"
        "exhaustiveness = 16\nnum_modes = 20\nenergy_range = 4\n",
        encoding="utf-8",
    )
    (templates / "openmm_validation_template.py").write_text(
        "# Pepforge v2.1.0 OpenMM validation template\n"
        "# This is a bridge template, not a ready-to-run force-field assignment for modified tokens.\n"
        "# 1) Prepare force-field parameters for non-standard residues/linkers/labels.\n"
        "# 2) Load protein + peptide complex.\n"
        "# 3) Run minimization and short equilibration on a capable machine.\n"
        "# 4) Import RMSD/contact persistence results back into Pepforge reports.\n",
        encoding="utf-8",
    )
    (templates / "gromacs_validation_notes.txt").write_text(
        "Pepforge v2.1.0 GROMACS/AMBER validation bridge notes\n\n"
        "This folder is intended for transfer to a workstation, HPC, cloud notebook, or collaborator PC.\n"
        "Pepforge has not replaced force-field parameterization. Review parameter_requirements.csv first.\n\n"
        "Minimum external-validation checklist:\n"
        "1. Receptor cleanup and protonation state review\n"
        "2. Modified peptide topology/charge preparation\n"
        "3. Energy minimization\n"
        "4. Short equilibration\n"
        "5. Production or replicated short MD if making stability claims\n"
        "6. RMSD/RMSF/contact persistence/clash review\n",
        encoding="utf-8",
    )
    (templates / "README_VALIDATION_BRIDGE.txt").write_text(
        f"Pepforge Low-Spec Validation Bridge v2.1.0\n\n"
        f"Evidence grade: {evidence.get('evidence_grade')}\n"
        f"Claim status: {evidence.get('claim_status')}\n\n"
        "This package helps move a modified peptide from local low-spec screening to external all-atom validation.\n"
        "It does not prove nM binding and does not replace AutoDock Vina, OpenMM, GROMACS, AMBER, or experiments.\n",
        encoding="utf-8",
    )
    return {p.stem: str(p) for p in templates.iterdir() if p.is_file()}

def _bridge_needs_stage(path: Path) -> bool:
    return any(ord(ch) > 127 for ch in str(path)) or "#" in str(path)


def _prepare_bridge_output_dir(output_dir: str | Path) -> tuple[Path, Path, bool]:
    requested = Path(output_dir).expanduser()
    requested.mkdir(parents=True, exist_ok=True)
    if _bridge_needs_stage(requested):
        stage = Path(tempfile.gettempdir()) / "Pepforge_Runtime" / "low_spec_validation_bridge"
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True, exist_ok=True)
        return requested, stage, True
    return requested, requested, False


def _copy_bridge_dir(paths: dict[str, str], requested: Path, stage: Path) -> dict[str, str]:
    if requested.resolve() == stage.resolve():
        return paths
    requested.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for key, value in paths.items():
        src = Path(value)
        if src.exists() and stage in src.parents:
            dst = requested / src.relative_to(stage)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            out[key] = str(dst)
        else:
            out[key] = value
    return out



def export_low_spec_validation_bridge(
    sequence: str,
    output_dir: str | Path,
    name: str = "modified_peptide",
    num_confs: int = 32,
) -> Dict[str, str]:
    """Generate a CPU-light simulation/validation bridge package.

    Outputs include multi-conformer SDF/PDB, PyMOL PML, conformer metrics,
    parameter requirements, evidence grading, and external validation templates.
    """
    requested_out, out, staged = _prepare_bridge_output_dir(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(name)
    result = build_structure(sequence, out, name=safe, optimize=True, num_confs=max(1, int(num_confs)), keep_all_confs=True)
    pml = make_pymol_pml(result.meta_path, prefer="sdf")
    meta_path = Path(result.meta_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    conformers = conformer_metric_rows(result.sdf_path, meta)
    evidence = compute_structure_evidence(meta, conformers)
    params = parameter_requirement_rows(meta)

    conformer_csv = out / f"{safe}_conformer_metrics.csv"
    params_csv = out / f"{safe}_parameter_requirements.csv"
    evidence_json = out / f"{safe}_evidence_report.json"
    evidence_txt = out / f"{safe}_evidence_report.txt"
    manifest_json = out / f"{safe}_validation_bridge_manifest.json"

    _write_csv(conformer_csv, conformers)
    _write_csv(params_csv, params)
    evidence_json.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_txt.write_text(
        "Pepforge v2.1.0 Low-Spec Peptide Simulation & Validation Bridge\n"
        "================================================================\n\n"
        f"Input: {sequence}\n"
        f"Evidence grade: {evidence.get('evidence_grade')}\n"
        f"Structure readiness score: {evidence.get('structure_readiness_score_0_100')}/100\n"
        f"Claim status: {evidence.get('claim_status')}\n"
        f"Binding claim allowed: {evidence.get('predicted_binding_claim_allowed')}\n"
        f"Recommended next step: {evidence.get('recommended_next_step')}\n\n"
        "Bridge meaning\n"
        "--------------\n"
        "Bridge means a hand-off package. Pepforge builds a modified-peptide starting structure, then exports conformer metrics, parameter requirements, PyMOL viewing files, and external validation templates.\n"
        "It helps move the model into PyMOL, Vina/Smina/Gnina, OpenMM, GROMACS, AMBER, or collaborator/HPC workflows. It does not execute or replace those external engines.\n\n"
        "How to use\n"
        "----------\n"
        "1. Inspect the generated SDF/PDB/PML in PyMOL.\n"
        "2. Open parameter_requirements.csv before any all-atom claim. Modified tokens such as Pal, FITC, dK, AEEA, PEG, Biotin, or lipid labels require parameter/charge review.\n"
        "3. Use all_atom_validation_bridge templates as starting files for external docking or MD.\n"
        "4. Import external RMSD/contact/energy results back into Pepforge when available.\n\n"
        "Interpretation\n"
        "--------------\n"
        "This report supports local screening, candidate triage, geometry sanity review, and validation-package preparation.\n"
        "It is not final all-atom MD and it is not an experimental Kd or true nM binder proof.\n",
        encoding="utf-8",
    )
    bridge_readme = out / f"{safe}_BRIDGE_HOW_TO_USE_KR.txt"
    bridge_readme.write_text(
        "Pepforge PyMOL Structure Builder Bridge 사용법\n"
        "=============================================\n\n"
        "Bridge는 '구조 생성 결과를 다음 프로그램으로 넘기기 위한 연결 패키지'라는 뜻이다.\n"
        "Pepforge가 modified peptide를 직접 완전한 force-field all-atom MD 구조로 확정하는 것이 아니라, PyMOL 확인/외부 docking/외부 MD/검증으로 넘길 수 있는 파일 묶음을 만든다.\n\n"
        "버튼별 의미\n"
        "1. Build SDF/PDB/PML: PyMOL에서 열어볼 기본 구조 파일 생성\n"
        "2. Simulation Bridge: 저사양 conformer 점검, internal clash, parameter requirement, evidence report 생성\n"
        "3. Docking Bridge: AutoDock Vina/Smina/Gnina 등에 넘길 template/config/import schema 생성\n"
        "4. MD Prep Bridge: GROMACS/OpenMM/AMBER로 넘기기 위한 준비 파일 생성\n"
        "5. MD Result Import: 외부에서 돌린 MD 결과를 다시 Pepforge로 가져오기 위한 import template 생성\n\n"
        "주의\n"
        "Pal, Myr, FITC, FAM, TAMRA, Biotin, AEEA, Ahx, PEG, dK/dH/dG 같은 token은 표준 PDB residue가 아니다.\n"
        "따라서 PyMOL에서는 UNL/HETATM처럼 보일 수 있고, all-atom MD에는 별도 parameter/charge 검토가 필요하다.\n\n"
        "분석 오류 발견됨이 뜨면 bridge_diagnostics 또는 *_diagnostic 파일을 확인한다. 출력 일부는 만들어졌을 수 있다.\n",
        encoding="utf-8",
    )
    template_paths = _write_external_templates(out, safe, evidence)
    manifest = {
        "bridge_version": BRIDGE_VERSION,
        "input": sequence,
        "name": safe,
        "primary_outputs": {
            "sdf_multi_conformer": str(result.sdf_path),
            "pdb": str(result.pdb_path),
            "json_metadata": str(result.meta_path),
            "report": str(result.report_path),
            "pymol_pml": str(pml),
            "conformer_metrics_csv": str(conformer_csv),
            "parameter_requirements_csv": str(params_csv),
            "evidence_report_json": str(evidence_json),
            "evidence_report_txt": str(evidence_txt),
            "bridge_how_to_use_kr": str(bridge_readme),
        },
        "external_validation_templates": template_paths,
        "claim_boundary": evidence.get("predicted_binding_claim_allowed"),
    }
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    paths = dict(manifest["primary_outputs"])
    paths["manifest"] = str(manifest_json)
    paths.update({f"template_{k}": v for k, v in template_paths.items()})
    return _copy_bridge_dir(paths, requested_out, out)
