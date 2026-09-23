#!/usr/bin/env python3
"""PDB structure-feature extractor for Pepforge Hot Spot Finder.

Outputs the existing pLDDT/B-factor and C-alpha exposure proxy plus an optional
DSSP-backed beta-edge *candidate* flag.  The beta-edge flag is deliberately
conservative and descriptive: it is not a binding-site prediction and is not
used as a hard PDE selection rule in V4.0.0.
"""
from pathlib import Path
import argparse
import math
import pandas as pd


def _truthy_chain(value: str | None) -> str | None:
    text=str(value or "").strip()
    return text or None


def _dssp_by_residue(pdb_path: str | Path, chain_filter: str | None) -> tuple[dict[int, str], str]:
    try:
        import mdtraj as md
        traj=md.load(str(pdb_path))
        ss=md.compute_dssp(traj, simplified=True)[0]
        mapping={}
        for residue, code in zip(traj.topology.residues, ss):
            chain_id=str(getattr(residue.chain, "chain_id", "") or getattr(residue.chain, "index", ""))
            # mdtraj chain_id is present for PDBs; fall back to index only for
            # availability, never to invent a requested named chain.
            if chain_filter and chain_id != chain_filter:
                continue
            try: resseq=int(residue.resSeq)
            except Exception: continue
            mapping[resseq]=str(code)
        return mapping, "mdtraj_DSSP"
    except Exception as exc:
        return {}, f"not_available:{type(exc).__name__}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pdb", required=True)
    p.add_argument("--record-name", required=True)
    p.add_argument("--chain", default=None)
    p.add_argument("--cutoff", type=float, default=10.0)
    p.add_argument("--output", default="structure_features.csv")
    args = p.parse_args()
    chain_filter=_truthy_chain(args.chain)

    cas=[]; backbone={}
    for line in Path(args.pdb).read_text(errors="ignore").splitlines():
        if not line.startswith("ATOM"): continue
        chain=line[21].strip()
        if chain_filter and chain != chain_filter: continue
        try:
            resi=int(line[22:26]); atom=line[12:16].strip()
            x,y,z=float(line[30:38]),float(line[38:46]),float(line[46:54])
            b=float(line[60:66]) if len(line)>=66 else 0.0
        except Exception:
            continue
        if atom == "CA": cas.append((resi,x,y,z,b))
        if atom in {"N","O"}: backbone.setdefault(resi,{})[atom]=(x,y,z)

    dssp, dssp_method=_dssp_by_residue(args.pdb, chain_filter)
    rows=[]
    for i,(resi,x,y,z,b) in enumerate(cas):
        contacts=0
        for j,(_,x2,y2,z2,_) in enumerate(cas):
            if i==j: continue
            if math.dist((x,y,z),(x2,y2,z2)) <= args.cutoff: contacts += 1
        exposure=1.0/(1.0+contacts/10.0)

        nonlocal_bb=0
        this=backbone.get(resi,{})
        for other_resi, other in backbone.items():
            if abs(other_resi-resi) <= 2: continue
            pairs=[]
            if "O" in this and "N" in other: pairs.append((this["O"],other["N"]))
            if "N" in this and "O" in other: pairs.append((this["N"],other["O"]))
            if any(math.dist(a,c) <= 3.5 for a,c in pairs): nonlocal_bb += 1
        ss=dssp.get(resi, "")
        beta_edge_available=bool(dssp)
        beta_edge=bool(beta_edge_available and ss=="E" and exposure>=0.35 and nonlocal_bb<=1)
        # Local C-alpha strand-axis proxy for downstream review.  This is a
        # geometric orientation descriptor only; it does not choose a peptide
        # register or assert that beta-pairing will occur.
        axis=None
        if len(cas) >= 2:
            if 0 < i < len(cas)-1:
                a=(cas[i-1][1],cas[i-1][2],cas[i-1][3]); c=(cas[i+1][1],cas[i+1][2],cas[i+1][3])
            elif i < len(cas)-1:
                a=(x,y,z); c=(cas[i+1][1],cas[i+1][2],cas[i+1][3])
            else:
                a=(cas[i-1][1],cas[i-1][2],cas[i-1][3]); c=(x,y,z)
            dv=(c[0]-a[0],c[1]-a[1],c[2]-a[2]); norm=math.sqrt(sum(v*v for v in dv))
            if norm > 1e-8:
                axis=tuple(round(v/norm,6) for v in dv)
        pairing_atoms=[atom for atom in ("N","O") if atom in this]
        rows.append({
            "record_name":args.record_name,"position":resi,"solvent_accessibility":exposure,
            "contact_number":contacts,"pLDDT":b,"secondary_structure":ss or "not_available",
            "secondary_structure_method":dssp_method,
            "beta_nonlocal_backbone_contact_count":nonlocal_bb,
            "beta_edge_candidate":beta_edge if beta_edge_available else "not_available",
            "beta_edge_evidence":(
                "DSSP_E + exposed_CA_contact_proxy + limited_nonlocal_backbone_contacts"
                if beta_edge else ("not_candidate" if beta_edge_available else "not_available")
            ),
            "beta_edge_backbone_pairing_atoms":";".join(pairing_atoms) if pairing_atoms else "not_available",
            "beta_edge_local_strand_axis_xyz":(";".join(str(v) for v in axis) if axis is not None else "not_available"),
            "beta_edge_register_status":"not_inferred",
            "beta_edge_claim_guard":"Heuristic exposed-beta-edge opportunity only; local backbone atoms/strand-axis are review metadata, not a binding-site prediction, peptide register, beta-pairing proof, or affinity estimate.",
        })
    pd.DataFrame(rows).to_csv(args.output,index=False)
    print("Wrote",args.output)


if __name__ == "__main__":
    main()
