from __future__ import annotations

"""Lightweight structure-file diagnostics for PSB-generated or external PDB/SDF files.

This module provides V4 static-file geometry review beyond simple two-file
structure comparison.  It accepts one or more independent PDB/SDF files and
produces per-model geometric diagnostics without requiring a trajectory format.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import json
import math

import numpy as np

from peptiforg_core.output_bundle import create_result_bundle, write_bundle_manifest, build_bundle_zip

STRUCTURE_FILE_ANALYZER_VERSION = "1.0.0"

try:  # pragma: no cover - optional runtime dependency
    import mdtraj as md
except Exception as exc:  # pragma: no cover
    md = None
    _MDTRAJ_ERROR = exc
else:
    _MDTRAJ_ERROR = None

try:  # pragma: no cover - optional runtime dependency
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
except Exception as exc:  # pragma: no cover
    Chem = None
    rdMolDescriptors = None
    _RDKIT_ERROR = exc
else:
    _RDKIT_ERROR = None


def _kabsch_aligned_rmsd_A(ref_xyz: np.ndarray, mob_xyz: np.ndarray) -> float:
    ref = np.asarray(ref_xyz, dtype=float)
    mob = np.asarray(mob_xyz, dtype=float)
    if ref.shape != mob.shape or ref.ndim != 2 or ref.shape[1] != 3 or len(ref) < 1:
        raise ValueError("RMSD alignment requires matching N x 3 coordinate arrays.")
    ref_cent = ref.mean(axis=0)
    mob_cent = mob.mean(axis=0)
    ref0 = ref - ref_cent
    mob0 = mob - mob_cent
    cov = mob0.T @ ref0
    v, _s, wt = np.linalg.svd(cov)
    d = np.sign(np.linalg.det(v @ wt))
    corr = np.diag([1.0, 1.0, float(d)])
    rot = v @ corr @ wt
    aligned = mob0 @ rot
    diff = aligned - ref0
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _radius_of_gyration_A(xyz_A: np.ndarray) -> float | None:
    pts = np.asarray(xyz_A, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 1:
        return None
    centered = pts - pts.mean(axis=0)
    return float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))


def _parse_pdb_frames(path: Path) -> list[list[dict[str, Any]]]:
    """Parse PDB coordinate frames using only the standard library.

    This deliberately covers the geometry needed by the PSB UI so ordinary
    PDB analysis does not depend on MDTraj. Full trajectory analysis
    remains an optional advanced workflow.
    """
    frames: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    saw_model = False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MODEL"):
            if current:
                frames.append(current); current=[]
            saw_model = True
            continue
        if line.startswith("ENDMDL"):
            if current:
                frames.append(current); current=[]
            continue
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 54:
            continue
        try:
            x=float(line[30:38]); y=float(line[38:46]); z=float(line[46:54])
        except ValueError:
            continue
        atom=line[12:16].strip().upper()
        resn=line[17:20].strip().upper() or "UNK"
        chain=line[21:22].strip()
        resi=line[22:26].strip()
        element=(line[76:78].strip().upper() if len(line) >= 78 else "") or (atom[:1] or "C")
        current.append({"atom":atom,"resn":resn,"chain":chain,"resi":resi,"element":element,"x":x,"y":y,"z":z})
    if current:
        frames.append(current)
    if not frames and not saw_model:
        return []
    return frames


def _pdb_residue_sequence(frame: list[dict[str, Any]]) -> list[str]:
    out=[]; seen=set()
    for atom in frame:
        key=(atom.get("chain",""), atom.get("resi",""))
        if key in seen: continue
        seen.add(key); out.append(str(atom.get("resn") or "UNK"))
    return out


def _coords_for_atoms(frame: list[dict[str, Any]], atom_names: set[str] | None = None, *, heavy_only: bool = False) -> np.ndarray:
    pts=[]
    for atom in frame:
        if heavy_only and str(atom.get("element","")).upper() == "H":
            continue
        if atom_names is not None and str(atom.get("atom","")).upper() not in atom_names:
            continue
        pts.append([float(atom["x"]), float(atom["y"]), float(atom["z"])])
    return np.asarray(pts, dtype=float)


def _iter_pdb_models(path: Path) -> list[dict[str, Any]]:
    frames=_parse_pdb_frames(path)
    if not frames:
        raise ValueError(f"No readable ATOM/HETATM coordinates were found in PDB: {path}")
    rows: list[dict[str, Any]]=[]
    first=frames[0]
    sequence=_pdb_residue_sequence(first)
    ref_ca=_coords_for_atoms(first, {"CA"})
    ref_bb=_coords_for_atoms(first, {"N","CA","C","O"})
    for frame_idx, frame in enumerate(frames, start=1):
        frame_sequence=_pdb_residue_sequence(frame)
        heavy=_coords_for_atoms(frame, heavy_only=True)
        ca=_coords_for_atoms(frame, {"CA"})
        bb=_coords_for_atoms(frame, {"N","CA","C","O"})
        seq_match=(frame_sequence == sequence)
        ca_rmsd=None; bb_rmsd=None
        if frame_idx > 1 and seq_match and len(ref_ca) and ref_ca.shape == ca.shape:
            ca_rmsd=round(_kabsch_aligned_rmsd_A(ref_ca, ca),6)
        if frame_idx > 1 and seq_match and len(ref_bb)>=4 and ref_bb.shape == bb.shape:
            bb_rmsd=round(_kabsch_aligned_rmsd_A(ref_bb, bb),6)
        rg=_radius_of_gyration_A(heavy)
        rows.append({
            "source_file":str(path), "source_name":path.name, "source_kind":"PDB",
            "model_label":f"{path.stem}:frame{frame_idx}", "frame_index_1based":frame_idx,
            "residue_count":len(frame_sequence), "sequence":"-".join(frame_sequence),
            "atom_count":len(frame), "heavy_atom_count":len(heavy),
            "radius_of_gyration_A":None if rg is None else round(rg,6),
            "helix_fraction":None,
            "rmsd_to_first_model_A":ca_rmsd,
            "backbone_rmsd_to_first_model_A":bb_rmsd,
            "sequence_match_to_first_model":seq_match,
            "note":"PDB geometry analyzed as a static V4 structure review. Trajectory-derived metrics are intentionally not inferred.",
        })
    return rows


def _iter_sdf_models(path: Path) -> list[dict[str, Any]]:
    if Chem is None:
        raise RuntimeError(f"RDKit is required for SDF structure analysis: {_RDKIT_ERROR}")
    supplier = Chem.SDMolSupplier(str(path), removeHs=False)
    rows: list[dict[str, Any]] = []
    ref_xyz = None
    ref_signature = None
    for mol_idx, mol in enumerate(supplier, start=1):
        if mol is None or mol.GetNumConformers() == 0:
            continue
        conf = mol.GetConformer()
        coords = np.asarray(conf.GetPositions(), dtype=float)
        elements = [atom.GetSymbol() for atom in mol.GetAtoms()]
        signature = tuple(elements)
        row: dict[str, Any] = {
            "source_file": str(path),
            "source_name": path.name,
            "source_kind": "SDF",
            "model_label": f"{path.stem}:mol{mol_idx}",
            "frame_index_1based": mol_idx,
            "residue_count": "",
            "sequence": "",
            "atom_count": int(mol.GetNumAtoms()),
            "heavy_atom_count": int(sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1)),
            "radius_of_gyration_A": None,
            "helix_fraction": None,
            "rmsd_to_first_model_A": None,
            "backbone_rmsd_to_first_model_A": None,
            "sequence_match_to_first_model": "",
            "note": "SDF diagnostic uses atom-order-preserving geometric comparison when atom identities match.",
        }
        rg = _radius_of_gyration_A(coords)
        row["radius_of_gyration_A"] = None if rg is None else round(rg, 6)
        if rdMolDescriptors is not None:
            try:
                row["formula"] = rdMolDescriptors.CalcMolFormula(mol)
            except Exception:
                row["formula"] = ""
        else:
            row["formula"] = ""
        if ref_xyz is None:
            ref_xyz = coords
            ref_signature = signature
        elif ref_xyz is not None and ref_signature == signature and ref_xyz.shape == coords.shape:
            row["rmsd_to_first_model_A"] = round(_kabsch_aligned_rmsd_A(ref_xyz, coords), 6)
        rows.append(row)
    if not rows:
        raise ValueError(f"No readable conformers were found in SDF: {path}")
    return rows


def analyze_structure_files(
    inputs: Iterable[str | Path],
    output_dir: str | Path,
    *,
    name: str = "structure_file_analysis",
) -> dict[str, Any]:
    paths = [Path(p).expanduser() for p in inputs if str(p or "").strip()]
    if not paths:
        raise ValueError("Select at least one PDB or SDF file.")
    rows: list[dict[str, Any]] = []
    kinds_used: list[str] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower()
        if suffix == ".pdb":
            rows.extend(_iter_pdb_models(path))
            kinds_used.append("PDB")
        elif suffix == ".sdf":
            rows.extend(_iter_sdf_models(path))
            kinds_used.append("SDF")
        else:
            raise ValueError(f"Unsupported structure file: {path.name}. Use PDB or SDF.")
    if not rows:
        raise ValueError("No analyzable structure models were found.")

    bundle = create_result_bundle(output_dir, name=name, tool="Structure_File_Analysis")
    csv_path = bundle / "structure_file_analysis_summary.csv"
    fieldnames = [
        "source_file", "source_name", "source_kind", "model_label", "frame_index_1based",
        "atom_count", "heavy_atom_count", "residue_count", "sequence", "formula",
        "radius_of_gyration_A", "helix_fraction", "rmsd_to_first_model_A",
        "backbone_rmsd_to_first_model_A", "sequence_match_to_first_model", "note",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rmsd_values = [float(r["rmsd_to_first_model_A"]) for r in rows if r.get("rmsd_to_first_model_A") not in {None, ""}]
    rg_values = [float(r["radius_of_gyration_A"]) for r in rows if r.get("radius_of_gyration_A") not in {None, ""}]
    summary = {
        "version": STRUCTURE_FILE_ANALYZER_VERSION,
        "input_files": [str(p) for p in paths],
        "input_kind_set": sorted(set(kinds_used)),
        "model_count": len(rows),
        "file_count": len(paths),
        "mean_radius_of_gyration_A": None if not rg_values else round(float(np.mean(rg_values)), 6),
        "min_radius_of_gyration_A": None if not rg_values else round(float(np.min(rg_values)), 6),
        "max_radius_of_gyration_A": None if not rg_values else round(float(np.max(rg_values)), 6),
        "mean_rmsd_to_first_model_A": None if not rmsd_values else round(float(np.mean(rmsd_values)), 6),
        "max_rmsd_to_first_model_A": None if not rmsd_values else round(float(np.max(rmsd_values)), 6),
        "interpretation": "Simple PDB/SDF structure-file diagnostics for PSB or external models. Results summarize coordinate differences and compactness only; they are not trajectory populations, docking energies, or experimental validation.",
        "claim_guard": "Structure-file analysis is a convenience layer for direct PDB/SDF review and does not replace full MD/trajectory validation when that is scientifically required.",
    }
    json_path = bundle / "structure_file_analysis_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_bundle_manifest(bundle, tool="Structure_File_Analysis", name=name, artifacts={"summary_csv": csv_path, "summary_json": json_path})
    zip_path = build_bundle_zip(bundle, filename="structure_file_analysis_package.zip")
    return {
        "bundle_dir": str(bundle),
        "summary_csv": str(csv_path),
        "summary_json": str(json_path),
        "zip_path": zip_path,
        **summary,
    }


__all__ = ["analyze_structure_files", "STRUCTURE_FILE_ANALYZER_VERSION"]
