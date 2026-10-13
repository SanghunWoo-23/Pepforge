from __future__ import annotations

"""Pepforge native-result quality gates.

These gates do not replace scientific validation and do not upgrade an
experimental native result into experimental evidence.  They are deliberately
conservative sanity checks that prevent Pepforge's native-first path from
silently trading away geometry/chemistry quality for independence.

Optional third-party libraries (currently RDKit) may contribute *validation*
only.  Their absence never disables the Pepforge-native path and their presence
does not replace Pepforge's own quality checks.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import math
import numpy as np
import pandas as pd

from .interface_quality import parse_pdb_atoms

NATIVE_QUALITY_GATE_VERSION = "0.1.0"
CANONICAL = {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"}

# Geometry windows are broad sanity ranges, not force-field restraints.
_BOND_TARGETS = {
    ("N", "CA"): (1.458, 0.16),
    ("CA", "C"): (1.525, 0.16),
    ("C", "O"): (1.231, 0.14),
}
_INTER_C_N = (1.329, 0.16)


def _finite_xyz(df: pd.DataFrame) -> np.ndarray:
    xyz = df[["x", "y", "z"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return xyz


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float)-np.asarray(b, dtype=float)))


def _status_from_counts(*, fail: int, warn: int) -> str:
    if int(fail) > 0:
        return "FAIL"
    if int(warn) > 0:
        return "WARN"
    return "PASS"


def _optional_rdkit_pdb_validation(path: str | Path) -> dict[str, Any]:
    """Validate, never generate/repair. Missing RDKit is an explicit SKIPPED state."""
    try:
        from rdkit import Chem  # type: ignore
    except Exception as exc:
        return {"available": False, "status": "SKIPPED_NOT_INSTALLED", "detail": str(exc)}
    try:
        mol = Chem.MolFromPDBFile(str(path), sanitize=False, removeHs=False, proximityBonding=True)
        if mol is None:
            return {"available": True, "status": "WARN_PARSE_FAILED", "detail": "MolFromPDBFile returned None"}
        atom_count = int(mol.GetNumAtoms())
        try:
            Chem.SanitizeMol(mol)
            return {"available": True, "status": "PASS", "atom_count": atom_count}
        except Exception as exc:
            # Backbone-only/partial structures can legitimately fail full chemical
            # sanitization; record rather than rewriting or rejecting native output.
            return {"available": True, "status": "WARN_SANITIZE", "atom_count": atom_count, "detail": str(exc)}
    except Exception as exc:
        return {"available": True, "status": "WARN_VALIDATOR_ERROR", "detail": str(exc)}


def audit_peptide_geometry(pdb_path: str | Path, *, optional_rdkit: bool = True) -> dict[str, Any]:
    p = Path(pdb_path).expanduser().resolve()
    atoms = parse_pdb_atoms(p).copy().reset_index(drop=True)
    if atoms.empty:
        return {"version": NATIVE_QUALITY_GATE_VERSION, "status": "FAIL", "fail_count": 1, "warn_count": 0,
                "issues": ["No readable atoms"], "pdb": str(p)}
    xyz = _finite_xyz(atoms)
    issues: list[str] = []
    warnings: list[str] = []
    fail = warn = 0
    if not np.isfinite(xyz).all():
        fail += 1; issues.append("Non-finite coordinates detected")

    residues=[]
    canonical_residue_count=0
    missing_backbone=0
    bond_outliers=[]
    peptide_bond_outliers=[]
    for (chain,resi), g in atoms.groupby(["chain","resi"], sort=False, dropna=False):
        resn=str(g.iloc[0].resn).upper()
        amap={str(r.atom).upper(): np.array([float(r.x),float(r.y),float(r.z)]) for _,r in g.iterrows()}
        if resn in CANONICAL:
            canonical_residue_count += 1
            missing=[a for a in ("N","CA","C","O") if a not in amap]
            if missing:
                missing_backbone += 1; fail += 1
                issues.append(f"{chain}:{resi} {resn} missing backbone atoms {','.join(missing)}")
            for (a,b),(target,tol) in _BOND_TARGETS.items():
                if a in amap and b in amap:
                    d=_dist(amap[a],amap[b])
                    if abs(d-target)>tol:
                        bond_outliers.append({"chain":str(chain),"resi":str(resi),"pair":f"{a}-{b}","distance_A":d,"target_A":target})
        residues.append((str(chain),str(resi),resn,amap))
    if bond_outliers:
        fail += 1; issues.append(f"Backbone covalent geometry outliers: {len(bond_outliers)}")

    # Consecutive peptide C-N sanity by numeric residue order within chain.
    for chain, group in atoms.groupby("chain", sort=False, dropna=False):
        rows=[]
        for resi,g in group.groupby("resi", sort=False, dropna=False):
            try: ri=int(''.join(c for c in str(resi) if c.isdigit() or c=='-'))
            except Exception: continue
            amap={str(r.atom).upper(): np.array([float(r.x),float(r.y),float(r.z)]) for _,r in g.iterrows()}
            rows.append((ri,str(g.iloc[0].resn).upper(),amap,str(resi)))
        rows.sort(key=lambda x:x[0])
        for left,right in zip(rows,rows[1:]):
            if right[0] != left[0]+1 or left[1] not in CANONICAL or right[1] not in CANONICAL: continue
            if "C" in left[2] and "N" in right[2]:
                d=_dist(left[2]["C"],right[2]["N"]); target,tol=_INTER_C_N
                if abs(d-target)>tol:
                    peptide_bond_outliers.append({"chain":str(chain),"left_resi":left[3],"right_resi":right[3],"distance_A":d,"target_A":target})
    if peptide_bond_outliers:
        fail += 1; issues.append(f"Peptide C-N geometry outliers: {len(peptide_bond_outliers)}")

    # Severe exact/near duplicates are always suspicious. This deliberately uses
    # a very small cutoff so normal bonded contacts are not mislabeled as clashes.
    heavy=atoms[~atoms["element"].astype(str).str.upper().eq("H")].reset_index(drop=True)
    hxyz=_finite_xyz(heavy)
    near_duplicate_pairs=0
    if len(hxyz)>1:
        for i in range(len(hxyz)):
            d=np.linalg.norm(hxyz[i+1:]-hxyz[i],axis=1)
            near_duplicate_pairs += int((d < 0.45).sum())
    if near_duplicate_pairs:
        fail += 1; issues.append(f"Near-duplicate heavy-atom coordinates: {near_duplicate_pairs}")

    # Partial/backbone-only is a quality scope warning, not a failure.
    sidechain_heavy=atoms[~atoms["atom"].astype(str).str.upper().isin({"N","CA","C","O","OXT","CB","H","HA","HA2","HA3"})]
    if canonical_residue_count and sidechain_heavy.empty and canonical_residue_count>1:
        warn += 1; warnings.append("Structure is backbone/CB-level rather than full canonical side-chain chemistry")

    rdkit = _optional_rdkit_pdb_validation(p) if optional_rdkit else {"available": False, "status": "SKIPPED_BY_POLICY"}
    if str(rdkit.get("status","")).startswith("WARN"):
        warn += 1; warnings.append(f"Optional RDKit validator: {rdkit.get('status')}")

    status=_status_from_counts(fail=fail,warn=warn)
    return {
        "version":NATIVE_QUALITY_GATE_VERSION,"status":status,"pdb":str(p),"fail_count":fail,"warn_count":warn,
        "atom_count":int(len(atoms)),"canonical_residue_count":int(canonical_residue_count),"missing_backbone_residue_count":int(missing_backbone),
        "backbone_bond_outliers":bond_outliers,"peptide_bond_outliers":peptide_bond_outliers,"near_duplicate_heavy_atom_pairs":int(near_duplicate_pairs),
        "warnings":warnings,"issues":issues,"optional_rdkit_validation":rdkit,
        "claim_guard":"Quality gate is a conservative geometry/chemistry sanity audit, not experimental validation, force-field validation, native-state proof, or accuracy certification.",
    }


def assess_native_docking_pose(*, clash_count: int, min_distance_A: float, contact_count: int, interaction_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary=dict(interaction_summary or {})
    fail=warn=0; issues=[]; warnings=[]
    if not math.isfinite(float(min_distance_A)):
        fail += 1; issues.append("Non-finite minimum interface distance")
    elif float(min_distance_A) < 1.70:
        fail += 1; issues.append(f"Severe interface overlap (min distance {float(min_distance_A):.2f} A)")
    elif float(min_distance_A) < 2.20:
        warn += 1; warnings.append(f"Close interface contact requires clash review ({float(min_distance_A):.2f} A)")
    if int(clash_count) > 10:
        fail += 1; issues.append(f"High native clash count: {int(clash_count)}")
    elif int(clash_count)>0:
        warn += 1; warnings.append(f"Residual native clash count: {int(clash_count)}")
    if int(contact_count)<=0:
        fail += 1; issues.append("No interface contacts detected")
    return {"version":NATIVE_QUALITY_GATE_VERSION,"status":_status_from_counts(fail=fail,warn=warn),"fail_count":fail,"warn_count":warn,
            "issues":issues,"warnings":warnings,"clash_count":int(clash_count),"min_distance_A":float(min_distance_A),"contact_count":int(contact_count),
            "interaction_summary":summary,"claim_guard":"Pose quality gate filters obvious geometry failures only; PASS does not imply native pose or affinity."}


def assess_native_mechanics(*, initial_score: float, final_score: float, final_geometry: dict[str, Any]) -> dict[str, Any]:
    fail=warn=0; issues=[]; warnings=[]
    if not math.isfinite(float(initial_score)) or not math.isfinite(float(final_score)):
        fail += 1; issues.append("Non-finite native mechanics score")
    delta=float(final_score)-float(initial_score)
    # Mechanics is damped relaxation-like dynamics; a large worsening indicates instability.
    scale=max(1.0,abs(float(initial_score)))
    if delta > 0.10*scale:
        fail += 1; issues.append(f"Reduced score worsened substantially ({delta:+.4f})")
    elif delta > 0.02*scale:
        warn += 1; warnings.append(f"Reduced score worsened slightly ({delta:+.4f})")
    gs=str(final_geometry.get("status","UNKNOWN"))
    if gs=="FAIL":
        fail += 1; issues.append("Final geometry failed native structure quality gate")
    elif gs=="WARN":
        warn += 1; warnings.append("Final geometry has native quality warnings")
    return {"version":NATIVE_QUALITY_GATE_VERSION,"status":_status_from_counts(fail=fail,warn=warn),"fail_count":fail,"warn_count":warn,
            "initial_reduced_score":float(initial_score),"final_reduced_score":float(final_score),"score_delta":delta,"final_geometry_status":gs,
            "issues":issues,"warnings":warnings,"claim_guard":"Mechanics quality gate is numerical/geometry sanity only and does not validate a physical force field or MD ensemble."}

__all__=["NATIVE_QUALITY_GATE_VERSION","audit_peptide_geometry","assess_native_docking_pose","assess_native_mechanics"]
