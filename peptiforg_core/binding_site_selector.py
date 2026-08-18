from __future__ import annotations

"""Pepforge Binding Site Selector v3.2.0.

This module analyzes a target PDB and proposes binding-site regions from:
- user-selected target chains,
- ligand/cofactor proximity,
- selected residue seeds,
- geometric pocket-like residue clusters.

It is a conservative screening helper. It does not prove the biological binding
site or replace expert structural biology review.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv
import json
import math
import re

BINDING_SITE_SELECTOR_VERSION = "3.2.0"

AA3_TO_1 = {
    "ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E","GLY":"G",
    "HIS":"H","ILE":"I","LEU":"L","LYS":"K","MET":"M","PHE":"F","PRO":"P","SER":"S",
    "THR":"T","TRP":"W","TYR":"Y","VAL":"V","SEC":"U","PYL":"O","MSE":"M",
}
WATER_NAMES = {"HOH","WAT","H2O","DOD"}
COMMON_IONS = {"NA","K","CL","CA","MG","MN","ZN","FE","CU","CO","NI","CD","HG","SR","BA","IOD","BR","F","LI","CS","RB"}
COMMON_BUFFERS = {"SO4","PO4","ACT","ACE","FMT","GOL","EDO","PEG","DMS","DMSO","TRS","MES","HEP","BME","MPD","IPA","EOH"}
HYDROPHOBIC = set("AILMFWVY")
AROMATIC = set("FWYH")
CHARGED = set("DEKRH")
POLAR = set("STNQCY")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def classify_het(resn: str) -> str:
    r = str(resn or "").upper()
    if r in WATER_NAMES:
        return "water"
    if r in COMMON_IONS:
        return "ion"
    if r in COMMON_BUFFERS:
        return "buffer_or_crystallization_agent"
    return "ligand_or_cofactor"


def parse_pdb_atoms(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDB file not found: {p}")
    rows = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        rec = line[0:6].strip()
        if rec not in {"ATOM","HETATM"}:
            continue
        atom = line[12:16].strip()
        altloc = line[16:17].strip()
        resn = line[17:20].strip().upper()
        chain = line[21:22].strip() or "_"
        resi = line[22:26].strip()
        try:
            x=float(line[30:38]); y=float(line[38:46]); z=float(line[46:54])
        except (TypeError, ValueError):
            # Invalid coordinates are not real atoms. Skipping them avoids
            # fabricating contacts/pockets at the origin.
            continue
        rows.append({
            "record": rec, "atom": atom, "altloc": altloc, "resn": resn, "chain": chain, "resi": resi,
            "aa": AA3_TO_1.get(resn, "X"), "x": x, "y": y, "z": z, "line": line,
            "het_class": classify_het(resn) if rec == "HETATM" else "",
        })
    return rows


def _dist(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt((float(a["x"])-float(b["x"]))**2 + (float(a["y"])-float(b["y"]))**2 + (float(a["z"])-float(b["z"]))**2)


def residue_centers(atoms: list[dict[str, Any]], chains: Optional[Iterable[str]] = None) -> list[dict[str, Any]]:
    selected = {str(c).strip() for c in chains or [] if str(c).strip()}
    groups: dict[tuple[str,str,str], list[dict[str, Any]]] = {}
    for a in atoms:
        if a["record"] != "ATOM":
            continue
        if selected and a["chain"] not in selected:
            continue
        groups.setdefault((a["chain"], a["resi"], a["resn"]), []).append(a)
    out = []
    for (chain, resi, resn), vals in sorted(groups.items(), key=lambda x: (x[0][0], int(re.sub(r"[^0-9-]","",x[0][1]) or 0))):
        xs=[v["x"] for v in vals]; ys=[v["y"] for v in vals]; zs=[v["z"] for v in vals]
        aa = AA3_TO_1.get(resn, "X")
        out.append({
            "chain": chain, "resi": resi, "resn": resn, "aa": aa,
            "x": sum(xs)/len(xs), "y": sum(ys)/len(ys), "z": sum(zs)/len(zs),
            "atom_count": len(vals),
            "chemistry": (
                "aromatic" if aa in AROMATIC else
                "charged" if aa in CHARGED else
                "hydrophobic" if aa in HYDROPHOBIC else
                "polar" if aa in POLAR else "other"
            ),
        })
    return out


def ligand_groups(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str,str,str,str], list[dict[str, Any]]] = {}
    for a in atoms:
        if a["record"] != "HETATM":
            continue
        cls = a["het_class"]
        if cls in {"water","ion","buffer_or_crystallization_agent"}:
            continue
        groups.setdefault((a["chain"], a["resi"], a["resn"], cls), []).append(a)
    out = []
    for (chain, resi, resn, cls), vals in sorted(groups.items()):
        out.append({
            "ligand_id": f"{chain}:{resn}{resi}",
            "chain": chain, "resi": resi, "resn": resn, "class": cls,
            "atom_count": len(vals),
            "x": sum(v["x"] for v in vals)/len(vals),
            "y": sum(v["y"] for v in vals)/len(vals),
            "z": sum(v["z"] for v in vals)/len(vals),
        })
    return out


def residues_near_ligands(residues: list[dict[str, Any]], ligands: list[dict[str, Any]], cutoff_A: float = 6.0) -> list[dict[str, Any]]:
    rows = []
    for r in residues:
        best = None
        for lig in ligands:
            d = _dist(r, lig)
            if d <= cutoff_A and (best is None or d < best[0]):
                best = (d, lig)
        if best:
            d, lig = best
            rows.append({
                "site_id": "ligand_proximal_site",
                "chain": r["chain"], "resi": r["resi"], "resn": r["resn"], "aa": r["aa"],
                "distance_A": round(d, 2),
                "selection_reason": f"within {cutoff_A} A of {lig['ligand_id']}",
                "ligand_id": lig["ligand_id"],
                "chemistry": r["chemistry"],
                "x": round(r["x"], 3), "y": round(r["y"], 3), "z": round(r["z"], 3),
            })
    return rows


def parse_seed_residues(seed_text: str) -> list[tuple[str, str]]:
    out = []
    for part in re.split(r"[,;\s]+", str(seed_text or "").strip()):
        if not part:
            continue
        # accepted: A:123, A123, 123
        m = re.match(r"^([A-Za-z_])[:]?([0-9A-Za-z-]+)$", part)
        if m:
            out.append((m.group(1), m.group(2)))
        else:
            out.append(("", part))
    return out


def residues_near_seeds(residues: list[dict[str, Any]], seed_text: str, cutoff_A: float = 8.0) -> list[dict[str, Any]]:
    seeds = parse_seed_residues(seed_text)
    if not seeds:
        return []
    seed_res = []
    for chain, resi in seeds:
        for r in residues:
            if str(r["resi"]) == str(resi) and (not chain or r["chain"] == chain):
                seed_res.append(r)
    rows = []
    for r in residues:
        best = None
        for s in seed_res:
            d = _dist(r, s)
            if d <= cutoff_A and (best is None or d < best[0]):
                best = (d, s)
        if best:
            d, s = best
            rows.append({
                "site_id": "seed_residue_site",
                "chain": r["chain"], "resi": r["resi"], "resn": r["resn"], "aa": r["aa"],
                "distance_A": round(d, 2),
                "selection_reason": f"within {cutoff_A} A of seed {s['chain']}:{s['resn']}{s['resi']}",
                "ligand_id": "",
                "chemistry": r["chemistry"],
                "x": round(r["x"], 3), "y": round(r["y"], 3), "z": round(r["z"], 3),
            })
    return rows


def pocket_like_residues(residues: list[dict[str, Any]], top_n: int = 30) -> list[dict[str, Any]]:
    """Heuristic pocket-like residues by local residue density and chemistry."""
    scored = []
    for r in residues:
        neigh = [o for o in residues if o is not r and _dist(r, o) <= 8.0]
        density = len(neigh)
        chem_bonus = 1.0 if r["aa"] in (HYDROPHOBIC | AROMATIC | CHARGED | POLAR) else 0.0
        score = density + chem_bonus
        scored.append((score, r, density))
    out = []
    for score, r, density in sorted(scored, key=lambda x: x[0], reverse=True)[:max(1, int(top_n))]:
        out.append({
            "site_id": "pocket_like_site",
            "chain": r["chain"], "resi": r["resi"], "resn": r["resn"], "aa": r["aa"],
            "distance_A": "",
            "selection_reason": f"local residue density={density}; heuristic pocket-like region",
            "ligand_id": "",
            "chemistry": r["chemistry"],
            "x": round(r["x"], 3), "y": round(r["y"], 3), "z": round(r["z"], 3),
            "site_score": round(score, 3),
        })
    return out


def merge_site_rows(*row_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str,str], dict[str, Any]] = {}
    for rows in row_sets:
        for r in rows:
            key = (str(r.get("chain","")), str(r.get("resi","")))
            if key not in merged:
                merged[key] = dict(r)
                merged[key]["selection_sources"] = r.get("site_id", "")
            else:
                merged[key]["selection_sources"] += ";" + str(r.get("site_id", ""))
                # prefer ligand/seed reasons over pocket-like when present
                if "ligand" in str(r.get("site_id","")) or "seed" in str(r.get("site_id","")):
                    merged[key].update({k:v for k,v in r.items() if k != "selection_sources"})
    out = list(merged.values())
    for i, r in enumerate(out, start=1):
        r["rank"] = i
    return out


def select_binding_site(
    pdb_path: str | Path,
    selected_chains: Optional[Iterable[str]] = None,
    seed_residues: str = "",
    ligand_cutoff_A: float = 6.0,
    seed_cutoff_A: float = 8.0,
    pocket_top_n: int = 30,
) -> dict[str, Any]:
    atoms = parse_pdb_atoms(pdb_path)
    residues = residue_centers(atoms, selected_chains)
    ligands = ligand_groups(atoms)
    ligand_rows = residues_near_ligands(residues, ligands, ligand_cutoff_A)
    seed_rows = residues_near_seeds(residues, seed_residues, seed_cutoff_A)
    pocket_rows = pocket_like_residues(residues, pocket_top_n)
    selected_rows = merge_site_rows(ligand_rows, seed_rows, pocket_rows)
    summary = {
        "pepforge_version": BINDING_SITE_SELECTOR_VERSION,
        "pdb_path": str(pdb_path),
        "selected_chains": list(selected_chains or []),
        "residue_count_considered": len(residues),
        "ligand_or_cofactor_count": len(ligands),
        "ligand_proximal_residue_count": len(ligand_rows),
        "seed_site_residue_count": len(seed_rows),
        "pocket_like_residue_count": len(pocket_rows),
        "final_selected_residue_count": len(selected_rows),
        "claim_boundary": "Binding site selector proposes screening regions. It does not prove the biological binding site.",
    }
    return {
        "summary": summary,
        "residues": residues,
        "ligands": ligands,
        "ligand_site_rows": ligand_rows,
        "seed_site_rows": seed_rows,
        "pocket_site_rows": pocket_rows,
        "selected_site_rows": selected_rows,
    }


def export_binding_site_selection_package(
    pdb_path: str | Path,
    output_dir: str | Path,
    selected_chains: Optional[Iterable[str]] = None,
    seed_residues: str = "",
    ligand_cutoff_A: float = 6.0,
    seed_cutoff_A: float = 8.0,
    pocket_top_n: int = 30,
) -> dict[str, str]:
    out = Path(output_dir) / "binding_site_selector"
    out.mkdir(parents=True, exist_ok=True)
    result = select_binding_site(
        pdb_path=pdb_path,
        selected_chains=selected_chains,
        seed_residues=seed_residues,
        ligand_cutoff_A=ligand_cutoff_A,
        seed_cutoff_A=seed_cutoff_A,
        pocket_top_n=pocket_top_n,
    )
    summary_json = out / "binding_site_summary.json"
    _write_json(summary_json, result["summary"])
    selected_csv = out / "selected_binding_site_residues.csv"
    _write_csv(selected_csv, result["selected_site_rows"], [
        "rank","site_id","selection_sources","chain","resi","resn","aa","distance_A",
        "selection_reason","ligand_id","chemistry","x","y","z","site_score",
    ])
    ligand_csv = out / "ligand_cofactor_summary.csv"
    _write_csv(ligand_csv, result["ligands"], ["ligand_id","chain","resi","resn","class","atom_count","x","y","z"])
    residue_csv = out / "target_residue_centers.csv"
    _write_csv(residue_csv, result["residues"], ["chain","resi","resn","aa","x","y","z","atom_count","chemistry"])
    pymol_pml = out / "binding_site_selection.pml"
    selections = []
    for r in result["selected_site_rows"][:80]:
        selections.append(f"(chain {r.get('chain')} and resi {r.get('resi')})")
    sel_expr = " or ".join(selections) if selections else "none"
    _write_text(pymol_pml, f"""# Pepforge binding site selector v{BINDING_SITE_SELECTOR_VERSION}
load {Path(pdb_path).as_posix()}, target
select pepforge_binding_site, {sel_expr}
show sticks, pepforge_binding_site
color yellow, pepforge_binding_site
zoom pepforge_binding_site
""")
    readme = out / "README_BINDING_SITE_SELECTOR.txt"
    _write_text(readme, """Pepforge Binding Site Selector
==============================

This package proposes screening binding-site residues using chain selection,
ligand/cofactor proximity, user seed residues, and heuristic pocket-like local
residue density.

Review before scientific claims:
- biological assembly vs asymmetric unit,
- ligand/cofactor relevance,
- chain identity,
- missing residues,
- experimental quality,
- known literature binding site.

This output is a screening-region proposal, not proof of the biological binding site.
""")
    manifest = out / "binding_site_selector_manifest.json"
    _write_json(manifest, {
        "pepforge_version": BINDING_SITE_SELECTOR_VERSION,
        "files": {
            "summary": str(summary_json),
            "selected_binding_site_residues": str(selected_csv),
            "ligand_cofactor_summary": str(ligand_csv),
            "target_residue_centers": str(residue_csv),
            "pymol_selection": str(pymol_pml),
            "readme": str(readme),
        },
        "claim_boundary": result["summary"]["claim_boundary"],
    })
    return {
        "binding_site_summary": str(summary_json),
        "selected_binding_site_residues": str(selected_csv),
        "ligand_cofactor_summary": str(ligand_csv),
        "target_residue_centers": str(residue_csv),
        "binding_site_selection_pml": str(pymol_pml),
        "binding_site_selector_readme": str(readme),
        "binding_site_selector_manifest": str(manifest),
    }


__all__ = [
    "BINDING_SITE_SELECTOR_VERSION",
    "parse_pdb_atoms",
    "select_binding_site",
    "export_binding_site_selection_package",
    "parse_seed_residues",
]
