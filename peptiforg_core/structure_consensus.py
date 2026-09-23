from __future__ import annotations

"""Independent structure-consensus diagnostics for canonical peptide PDBs."""

from pathlib import Path
from typing import Any
import csv
import json
import numpy as np

from peptiforg_core.output_bundle import create_result_bundle, write_bundle_manifest, build_bundle_zip
from peptiforg_core.structure_file_analyzer import _parse_pdb_frames, _radius_of_gyration_A

STRUCTURE_CONSENSUS_VERSION = "2.0.0"

try:
    import mdtraj as md
except Exception as exc:  # pragma: no cover
    md = None
    _MDTRAJ_ERROR = exc
else:
    _MDTRAJ_ERROR = None


def _require_mdtraj():
    if md is None: raise RuntimeError(f"MDTraj is required for structure consensus: {_MDTRAJ_ERROR}")


def _sequence(traj) -> list[str]:
    return [r.name for r in traj.topology.residues]


def _indices_by_name(traj, name: str) -> np.ndarray:
    return np.asarray([a.index for a in traj.topology.atoms if a.name == name], dtype=int)


def _dssp(traj) -> list[str]:
    try:
        arr = md.compute_dssp(traj, simplified=True)
        return [str(x) for x in arr[0]]
    except Exception:
        return []


def _kabsch_transform(ref_xyz: np.ndarray, mob_xyz: np.ndarray):
    ref=np.asarray(ref_xyz,dtype=float); mob=np.asarray(mob_xyz,dtype=float)
    if ref.shape != mob.shape or ref.ndim != 2 or ref.shape[1] != 3 or len(ref) < 1:
        raise ValueError("Structure comparison requires matching coordinate arrays.")
    rc=ref.mean(axis=0); mc=mob.mean(axis=0)
    r0=ref-rc; m0=mob-mc
    v,_s,wt=np.linalg.svd(m0.T @ r0)
    d=np.sign(np.linalg.det(v @ wt)); corr=np.diag([1.0,1.0,float(d)])
    rot=v @ corr @ wt
    return rot, rc, mc


def _residue_records(frame: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order=[]; grouped={}
    for atom in frame:
        key=(str(atom.get("chain","")), str(atom.get("resi","")), str(atom.get("resn","UNK")))
        if key not in grouped:
            grouped[key]=[]; order.append(key)
        grouped[key].append(atom)
    return [{"key":key,"atoms":grouped[key]} for key in order]


def _atom_xyz_by_name(residue: dict[str, Any]) -> dict[str,np.ndarray]:
    out={}
    for atom in residue["atoms"]:
        out[str(atom.get("atom","")).upper()]=np.asarray([atom["x"],atom["y"],atom["z"]],dtype=float)
    return out


def _compare_structures_without_mdtraj(reference_pdb: str | Path, comparison_pdb: str | Path, output_dir: str | Path, *, name: str, hotspot_residue_indices=None, contact_cutoff_A: float=8.0) -> dict[str, Any]:
    ref_path=Path(reference_pdb); mob_path=Path(comparison_pdb)
    ref_frames=_parse_pdb_frames(ref_path); mob_frames=_parse_pdb_frames(mob_path)
    if len(ref_frames) != 1 or len(mob_frames) != 1:
        raise ValueError("Structure comparison expects single-frame PDB structures.")
    ref_res=_residue_records(ref_frames[0]); mob_res=_residue_records(mob_frames[0])
    seq_ref=[r["key"][2] for r in ref_res]; seq_mob=[r["key"][2] for r in mob_res]
    if seq_ref != seq_mob:
        raise ValueError("Structure sequences/residue identities differ; Pepforge will not create a misleading automatic RMSD alignment.")
    ref_ca=[]; mob_ca=[]; ca_available=True
    for rr,mr in zip(ref_res,mob_res):
        ra=_atom_xyz_by_name(rr); ma=_atom_xyz_by_name(mr)
        if "CA" not in ra or "CA" not in ma:
            ca_available=False; break
        ref_ca.append(ra["CA"]); mob_ca.append(ma["CA"])
    all_atom_rmsd=None
    if ca_available and ref_ca:
        ref_ca=np.asarray(ref_ca,dtype=float); mob_ca=np.asarray(mob_ca,dtype=float)
        rot,rc,mc=_kabsch_transform(ref_ca,mob_ca)
        mob_ca_aligned=(mob_ca-mc) @ rot + rc
        ca_delta=np.linalg.norm(mob_ca_aligned-ref_ca,axis=1)
        ca_rmsd=float(np.sqrt(np.mean(ca_delta**2)))
        comparison_mode="residue_CA_backbone"
    else:
        # Legacy or externally supplied PDBs may still use generic residue naming/atom names
        # instead of protein-style CA/N/C/O records.  When the atom element
        # signature/order matches, compare the full heavy-atom geometry rather
        # than requiring MDTraj or pretending generic atoms are C-alpha atoms.
        ref_heavy_atoms=[a for a in ref_frames[0] if str(a.get("element","")).upper()!="H"]
        mob_heavy_atoms=[a for a in mob_frames[0] if str(a.get("element","")).upper()!="H"]
        ref_sig=[str(a.get("element","")).upper() for a in ref_heavy_atoms]
        mob_sig=[str(a.get("element","")).upper() for a in mob_heavy_atoms]
        if not ref_heavy_atoms or ref_sig != mob_sig:
            raise ValueError("Structures lack residue-aware CA atoms and their heavy-atom signatures do not match for atom-order comparison.")
        ref_all=np.asarray([[a["x"],a["y"],a["z"]] for a in ref_heavy_atoms],dtype=float)
        mob_all=np.asarray([[a["x"],a["y"],a["z"]] for a in mob_heavy_atoms],dtype=float)
        rot,rc,mc=_kabsch_transform(ref_all,mob_all)
        mob_all_aligned=(mob_all-mc) @ rot + rc
        all_delta=np.linalg.norm(mob_all_aligned-ref_all,axis=1)
        all_atom_rmsd=float(np.sqrt(np.mean(all_delta**2)))
        ca_delta=np.asarray([],dtype=float); ca_rmsd=None
        ref_ca=np.asarray([],dtype=float); mob_ca=np.asarray([],dtype=float)
        comparison_mode="heavy_atom_order"

    bb_names=("N","CA","C","O")
    ref_bb=[]; mob_bb=[]; local=[]; per_rows=[]
    if comparison_mode == "residue_CA_backbone":
        for i,(rr,mr) in enumerate(zip(ref_res,mob_res),1):
            ra=_atom_xyz_by_name(rr); ma=_atom_xyz_by_name(mr)
            local_vals=[]
            for atom_name in bb_names:
                if atom_name in ra and atom_name in ma:
                    ref_bb.append(ra[atom_name]); mob_bb.append(ma[atom_name])
                    aligned=(ma[atom_name]-mc) @ rot + rc
                    local_vals.append(float(np.linalg.norm(aligned-ra[atom_name])))
            local_mean=None if not local_vals else float(np.mean(local_vals))
            local.append(local_mean)
            per_rows.append({
                "residue_index":i, "residue":seq_ref[i-1],
                "reference_dssp":"unavailable", "comparison_dssp":"unavailable", "match":"",
                "ca_displacement_A":round(float(ca_delta[i-1]),5),
                "local_backbone_displacement_A":"" if local_mean is None else round(local_mean,5),
            })
    else:
        per_rows=[{"residue_index":"","residue":"generic PDB","reference_dssp":"unavailable","comparison_dssp":"unavailable","match":"","ca_displacement_A":"","local_backbone_displacement_A":""}]
    backbone_rmsd=None
    if comparison_mode == "residue_CA_backbone" and len(ref_bb)>=4 and len(ref_bb)==len(mob_bb):
        rb=np.asarray(ref_bb,dtype=float); mb=np.asarray(mob_bb,dtype=float)
        mb_aligned=(mb-mc) @ rot + rc
        backbone_rmsd=float(np.sqrt(np.mean(np.sum((mb_aligned-rb)**2,axis=1))))

    ref_contacts=set(); mob_contacts=set(); contact_rows=[]
    if comparison_mode == "residue_CA_backbone":
        for i in range(len(seq_ref)):
            for j in range(i+3,len(seq_ref)):
                rd=float(np.linalg.norm(ref_ca[i]-ref_ca[j])); md_=float(np.linalg.norm(mob_ca[i]-mob_ca[j]))
                rcon=rd<=float(contact_cutoff_A); mcon=md_<=float(contact_cutoff_A); pair=(i+1,j+1)
                if rcon: ref_contacts.add(pair)
                if mcon: mob_contacts.add(pair)
                if rcon or mcon:
                    contact_rows.append({"residue_i":i+1,"residue_j":j+1,"reference_distance_A":round(rd,5),"comparison_distance_A":round(md_,5),"reference_contact":bool(rcon),"comparison_contact":bool(mcon),"match":bool(rcon==mcon)})
    union=ref_contacts|mob_contacts; shared=ref_contacts&mob_contacts
    contact_jaccard=1.0 if not union else float(len(shared)/len(union))
    hotspot=[]
    for value in list(hotspot_residue_indices or []):
        try: idx=int(value)
        except Exception: continue
        if 1<=idx<=len(seq_ref) and idx not in hotspot: hotspot.append(idx)
    hotspot_rmsd=None
    if hotspot and comparison_mode == "residue_CA_backbone":
        vals=np.asarray([ca_delta[i-1] for i in hotspot],dtype=float)
        hotspot_rmsd=float(np.sqrt(np.mean(vals**2)))
    ref_heavy=np.asarray([[a["x"],a["y"],a["z"]] for a in ref_frames[0] if str(a.get("element","")).upper()!="H"],dtype=float)
    mob_heavy=np.asarray([[a["x"],a["y"],a["z"]] for a in mob_frames[0] if str(a.get("element","")).upper()!="H"],dtype=float)

    bundle=create_result_bundle(output_dir,name=name,tool="Structure_Consensus")
    csv_path=bundle/"structure_consensus_per_residue.csv"
    with csv_path.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(per_rows[0])); w.writeheader(); w.writerows(per_rows)
    contact_csv_path=bundle/"structure_consensus_contact_map.csv"
    fields=["residue_i","residue_j","reference_distance_A","comparison_distance_A","reference_contact","comparison_contact","match"]
    with contact_csv_path.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(contact_rows)
    summary={
        "version":STRUCTURE_CONSENSUS_VERSION,
        "reference_pdb":str(ref_path),"comparison_pdb":str(mob_path),"residue_count":len(seq_ref),"sequence_residue_names":seq_ref,
        "comparison_mode":comparison_mode,
        "ca_rmsd_A":None if ca_rmsd is None else round(ca_rmsd,6),
        "backbone_rmsd_A":None if backbone_rmsd is None else round(backbone_rmsd,6),
        "heavy_atom_order_rmsd_A":None if all_atom_rmsd is None else round(all_atom_rmsd,6),
        "reference_rg_A":None if _radius_of_gyration_A(ref_heavy) is None else round(float(_radius_of_gyration_A(ref_heavy)),6),
        "comparison_rg_A":None if _radius_of_gyration_A(mob_heavy) is None else round(float(_radius_of_gyration_A(mob_heavy)),6),
        "dssp_residue_agreement_fraction":None,"reference_helix_fraction":None,"comparison_helix_fraction":None,
        "contact_cutoff_A":float(contact_cutoff_A),"reference_nonlocal_CA_contact_count":len(ref_contacts),"comparison_nonlocal_CA_contact_count":len(mob_contacts),
        "shared_nonlocal_CA_contact_count":len(shared),"contact_map_jaccard_fraction":round(contact_jaccard,6),
        "lost_reference_contacts":len(ref_contacts-mob_contacts),"gained_comparison_contacts":len(mob_contacts-ref_contacts),
        "hotspot_residue_indices_1based":hotspot,"hotspot_ca_rmsd_A":None if hotspot_rmsd is None else round(hotspot_rmsd,6),
        "max_ca_displacement_A":None if not len(ca_delta) else round(float(np.max(ca_delta)),6),
        "mean_ca_displacement_A":None if not len(ca_delta) else round(float(np.mean(ca_delta)),6),
        "interpretation":"Structure comparison using CA/backbone displacement, radius of gyration, and nonlocal CA contact maps. MDTraj is not required for these core PDB metrics; DSSP remains unavailable without an optional secondary-structure backend.",
        "claim_guard":"Model agreement does not establish native structure or experimental correctness.",
    }
    json_path=bundle/"structure_consensus_summary.json"; json_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_bundle_manifest(bundle,tool="Structure_Consensus",name=name,artifacts={"summary_json":json_path,"per_residue_csv":csv_path,"contact_map_csv":contact_csv_path})
    zip_path=build_bundle_zip(bundle,filename="structure_consensus_package.zip")
    return {"bundle_dir":str(bundle),"summary_json":str(json_path),"per_residue_csv":str(csv_path),"contact_map_csv":str(contact_csv_path),"zip_path":zip_path,**summary}


def compare_structures(
    reference_pdb: str | Path,
    comparison_pdb: str | Path,
    output_dir: str | Path,
    *,
    name: str = "structure_consensus",
    hotspot_residue_indices: list[int] | tuple[int, ...] | None = None,
    contact_cutoff_A: float = 8.0,
) -> dict[str, Any]:
    use_fallback = md is None
    if not use_fallback:
        try:
            rf=_parse_pdb_frames(Path(reference_pdb)); mf=_parse_pdb_frames(Path(comparison_pdb))
            if rf and mf:
                ref_has_ca=any(str(a.get("atom","")).upper()=="CA" for a in rf[0])
                mob_has_ca=any(str(a.get("atom","")).upper()=="CA" for a in mf[0])
                use_fallback = not (ref_has_ca and mob_has_ca)
        except Exception:
            pass
    if use_fallback:
        return _compare_structures_without_mdtraj(
            reference_pdb, comparison_pdb, output_dir, name=name,
            hotspot_residue_indices=hotspot_residue_indices, contact_cutoff_A=contact_cutoff_A,
        )
    ref_path = Path(reference_pdb); mob_path = Path(comparison_pdb)
    ref = md.load(str(ref_path)); mob = md.load(str(mob_path))
    if ref.n_frames != 1 or mob.n_frames != 1:
        raise ValueError("Structure consensus expects single-frame PDB structures.")
    seq_ref = _sequence(ref); seq_mob = _sequence(mob)
    if seq_ref != seq_mob:
        raise ValueError("Structure sequences/residue identities differ; Pepforge will not create a misleading automatic RMSD alignment.")
    ca_ref = _indices_by_name(ref, "CA"); ca_mob = _indices_by_name(mob, "CA")
    if len(ca_ref) != len(seq_ref) or len(ca_mob) != len(seq_mob) or not len(ca_ref):
        raise ValueError("Both PDBs require one CA atom per residue for sequence-safe consensus comparison.")
    mob.superpose(ref, 0, atom_indices=ca_mob, ref_atom_indices=ca_ref)
    ca_delta_A = np.linalg.norm(mob.xyz[0, ca_mob] - ref.xyz[0, ca_ref], axis=1) * 10.0
    ca_rmsd_A = float(np.sqrt(np.mean(ca_delta_A ** 2)))

    bb_names = {"N", "CA", "C", "O"}
    ref_bb = [a.index for a in ref.topology.atoms if a.name in bb_names]
    mob_bb = [a.index for a in mob.topology.atoms if a.name in bb_names]
    backbone_rmsd_A = None
    if len(ref_bb) == len(mob_bb) and len(ref_bb) >= 4:
        bb_delta = np.linalg.norm(mob.xyz[0, mob_bb] - ref.xyz[0, ref_bb], axis=1) * 10.0
        backbone_rmsd_A = float(np.sqrt(np.mean(bb_delta ** 2)))

    d_ref = _dssp(ref); d_mob = _dssp(mob)
    dssp_agreement = None
    dssp_rows: list[dict[str, Any]] = []
    if len(d_ref) == len(seq_ref) and len(d_mob) == len(seq_ref):
        dssp_agreement = float(np.mean(np.asarray(d_ref) == np.asarray(d_mob)))
        for i, (res, a, b) in enumerate(zip(seq_ref, d_ref, d_mob), 1):
            dssp_rows.append({"residue_index": i, "residue": res, "reference_dssp": a, "comparison_dssp": b, "match": bool(a == b), "ca_displacement_A": round(float(ca_delta_A[i-1]), 5)})
    else:
        for i, res in enumerate(seq_ref, 1):
            dssp_rows.append({"residue_index": i, "residue": res, "reference_dssp": "unavailable", "comparison_dssp": "unavailable", "match": "", "ca_displacement_A": round(float(ca_delta_A[i-1]), 5)})

    # Per-residue local backbone displacement after the CA superposition.  Atom
    # names are matched within the same residue; missing side atoms do not force
    # a misleading whole-structure failure.
    local_backbone = []
    for ridx in range(len(seq_ref)):
        ref_res = list(ref.topology.residues)[ridx]
        mob_res = list(mob.topology.residues)[ridx]
        ref_names = {a.name: a.index for a in ref_res.atoms if a.name in bb_names}
        mob_names = {a.name: a.index for a in mob_res.atoms if a.name in bb_names}
        common = [n for n in ("N", "CA", "C", "O") if n in ref_names and n in mob_names]
        if common:
            vals = [float(np.linalg.norm(mob.xyz[0, mob_names[n]] - ref.xyz[0, ref_names[n]]) * 10.0) for n in common]
            local_backbone.append(float(np.mean(vals)))
        else:
            local_backbone.append(None)
        dssp_rows[ridx]["local_backbone_displacement_A"] = "" if local_backbone[-1] is None else round(local_backbone[-1], 5)

    # Sequence-safe CA contact-map comparison.  The Jaccard-style agreement is
    # calculated over the union of nonlocal contacts so the many shared
    # non-contacts do not inflate the score.
    ref_ca_xyz = ref.xyz[0, ca_ref] * 10.0
    mob_ca_xyz = mob.xyz[0, ca_mob] * 10.0
    contact_rows = []
    ref_contacts, mob_contacts = set(), set()
    for i in range(len(seq_ref)):
        for j in range(i + 3, len(seq_ref)):
            rd = float(np.linalg.norm(ref_ca_xyz[i] - ref_ca_xyz[j]))
            md_ = float(np.linalg.norm(mob_ca_xyz[i] - mob_ca_xyz[j]))
            rc = rd <= float(contact_cutoff_A); mc = md_ <= float(contact_cutoff_A)
            pair = (i + 1, j + 1)
            if rc: ref_contacts.add(pair)
            if mc: mob_contacts.add(pair)
            if rc or mc:
                contact_rows.append({
                    "residue_i": i + 1, "residue_j": j + 1,
                    "reference_distance_A": round(rd, 5), "comparison_distance_A": round(md_, 5),
                    "reference_contact": bool(rc), "comparison_contact": bool(mc), "match": bool(rc == mc),
                })
    union = ref_contacts | mob_contacts; shared = ref_contacts & mob_contacts
    contact_jaccard = 1.0 if not union else float(len(shared) / len(union))

    hotspot_indices = []
    for value in list(hotspot_residue_indices or []):
        try:
            idx = int(value)
        except Exception:
            continue
        if 1 <= idx <= len(seq_ref) and idx not in hotspot_indices:
            hotspot_indices.append(idx)
    hotspot_rmsd_A = None
    if hotspot_indices:
        vals = np.asarray([ca_delta_A[i - 1] for i in hotspot_indices], dtype=float)
        hotspot_rmsd_A = float(np.sqrt(np.mean(vals ** 2)))

    bundle = create_result_bundle(output_dir, name=name, tool="Structure_Consensus")
    csv_path = bundle / "structure_consensus_per_residue.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dssp_rows[0]))
        writer.writeheader(); writer.writerows(dssp_rows)
    contact_csv_path = bundle / "structure_consensus_contact_map.csv"
    with contact_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["residue_i", "residue_j", "reference_distance_A", "comparison_distance_A", "reference_contact", "comparison_contact", "match"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(contact_rows)
    summary = {
        "version": STRUCTURE_CONSENSUS_VERSION,
        "reference_pdb": str(ref_path), "comparison_pdb": str(mob_path),
        "residue_count": len(seq_ref), "sequence_residue_names": seq_ref,
        "ca_rmsd_A": round(ca_rmsd_A, 6),
        "backbone_rmsd_A": None if backbone_rmsd_A is None else round(backbone_rmsd_A, 6),
        "reference_rg_A": round(float(md.compute_rg(ref)[0]) * 10.0, 6),
        "comparison_rg_A": round(float(md.compute_rg(mob)[0]) * 10.0, 6),
        "dssp_residue_agreement_fraction": None if dssp_agreement is None else round(dssp_agreement, 6),
        "reference_helix_fraction": None if not d_ref else round(float(np.mean(np.asarray(d_ref) == "H")), 6),
        "comparison_helix_fraction": None if not d_mob else round(float(np.mean(np.asarray(d_mob) == "H")), 6),
        "contact_cutoff_A": float(contact_cutoff_A),
        "reference_nonlocal_CA_contact_count": len(ref_contacts),
        "comparison_nonlocal_CA_contact_count": len(mob_contacts),
        "shared_nonlocal_CA_contact_count": len(shared),
        "contact_map_jaccard_fraction": round(contact_jaccard, 6),
        "lost_reference_contacts": len(ref_contacts - mob_contacts),
        "gained_comparison_contacts": len(mob_contacts - ref_contacts),
        "hotspot_residue_indices_1based": hotspot_indices,
        "hotspot_ca_rmsd_A": None if hotspot_rmsd_A is None else round(hotspot_rmsd_A, 6),
        "max_ca_displacement_A": round(float(np.max(ca_delta_A)), 6),
        "mean_ca_displacement_A": round(float(np.mean(ca_delta_A)), 6),
        "interpretation": "Independent model-consensus diagnostic using global/local displacement, DSSP, and nonlocal CA contact-map agreement. Agreement does not establish native structure or experimental correctness.",
        "claim_guard": "AF3/PEP-FOLD/CABS-flex or any other model is not treated as ground truth by this comparison.",
    }
    json_path = bundle / "structure_consensus_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_bundle_manifest(bundle, tool="Structure_Consensus", name=name, artifacts={"summary_json": json_path, "per_residue_csv": csv_path, "contact_map_csv": contact_csv_path})
    zip_path = build_bundle_zip(bundle, filename="structure_consensus_package.zip")
    return {"bundle_dir": str(bundle), "summary_json": str(json_path), "per_residue_csv": str(csv_path), "contact_map_csv": str(contact_csv_path), "zip_path": zip_path, **summary}
