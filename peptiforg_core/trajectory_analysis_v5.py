from __future__ import annotations

"""Real trajectory analysis for Pepforge V5 using MDTraj when available.

The module reports descriptive trajectory evidence only.  It intentionally does
not convert finite-time MD stability, cluster occupancy, or autocorrelation
statistics into equilibrium, folding-probability, affinity, or function claims.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import importlib.util
import json
import math
import numpy as np

TRAJECTORY_ANALYSIS_VERSION = "5.0.0-rc2"


def backend_readiness() -> dict[str, Any]:
    ok = importlib.util.find_spec("mdtraj") is not None
    return {
        "backend": "mdtraj", "version": TRAJECTORY_ANALYSIS_VERSION,
        "available": ok, "status": "READY" if ok else "OPTIONAL_DEPENDENCY_MISSING",
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _chain_identifier(chain: Any) -> str:
    for attr in ("chain_id", "id"):
        value = getattr(chain, attr, None)
        if value:
            return str(value)
    return str(getattr(chain, "index", ""))


def _integrated_autocorrelation_diagnostics(values: np.ndarray) -> dict[str, Any]:
    """Return a conservative descriptive autocorrelation/ESS diagnostic.

    The sum stops at the first non-positive lag correlation.  This is a compact
    diagnostic rather than a formal convergence test and is labelled as such in
    the returned payload.
    """
    x = np.asarray(values, dtype=float).reshape(-1)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n < 4:
        return {
            "sample_count": n,
            "integrated_autocorrelation_time_frames": None,
            "effective_sample_size_estimate": None,
            "status": "INSUFFICIENT_FRAMES",
        }
    centered = x - float(np.mean(x))
    var = float(np.dot(centered, centered) / n)
    if var <= 1e-18:
        return {
            "sample_count": n,
            "integrated_autocorrelation_time_frames": 0.5,
            "effective_sample_size_estimate": float(n),
            "status": "NEAR_CONSTANT_SERIES",
        }
    max_lag = min(n // 2, 1000)
    positive_rhos: list[float] = []
    for lag in range(1, max_lag + 1):
        rho = float(np.dot(centered[:-lag], centered[lag:]) / ((n - lag) * var))
        if not math.isfinite(rho) or rho <= 0:
            break
        positive_rhos.append(rho)
    tau = 0.5 + float(sum(positive_rhos))
    ess = min(float(n), float(n) / max(1.0, 2.0 * tau))
    return {
        "sample_count": n,
        "positive_lags_used": len(positive_rhos),
        "integrated_autocorrelation_time_frames": float(tau),
        "effective_sample_size_estimate": float(ess),
        "status": "DESCRIPTIVE_ESTIMATE",
    }


def _secondary_structure_summary(traj: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import mdtraj as md

    try:
        dssp = md.compute_dssp(traj, simplified=True)
    except Exception as exc:
        return [], {"status": "UNAVAILABLE", "reason": f"{type(exc).__name__}: {exc}"}
    if dssp.size == 0:
        return [], {"status": "NO_ASSIGNMENTS"}
    # simplified DSSP uses H/E/C.  Preserve frame-wise fractions for plotting and
    # report ensemble means without calling them equilibrium populations.
    rows: list[dict[str, Any]] = []
    for frame in range(dssp.shape[0]):
        values = dssp[frame]
        total = max(1, len(values))
        rows.append({
            "frame": frame,
            "helix_fraction": float(np.sum(values == "H") / total),
            "extended_fraction": float(np.sum(values == "E") / total),
            "coil_fraction": float(np.sum(values == "C") / total),
        })
    return rows, {
        "status": "COMPLETED",
        "mean_helix_fraction": float(np.mean([r["helix_fraction"] for r in rows])),
        "mean_extended_fraction": float(np.mean([r["extended_fraction"] for r in rows])),
        "mean_coil_fraction": float(np.mean([r["coil_fraction"] for r in rows])),
        "claim_guard": "DSSP fractions describe sampled frames; they are not equilibrium folding probabilities.",
    }


def _hydrogen_bond_persistence(traj: Any) -> list[dict[str, Any]]:
    """Compute explicit-H donor-H-acceptor persistence when hydrogens exist."""
    import mdtraj as md

    try:
        triplets = md.baker_hubbard(traj, periodic=False, freq=0.0)
    except Exception:
        return []
    if triplets is None or len(triplets) == 0:
        return []
    triplets = np.asarray(triplets, dtype=int)
    try:
        # Baker-Hubbard convention: donor-heavy, hydrogen, acceptor-heavy.
        distances = md.compute_distances(traj, triplets[:, [1, 2]], periodic=False)
        angles = md.compute_angles(traj, triplets, periodic=False)
    except Exception:
        return []
    # Match the conventional Baker-Hubbard geometry approximately: H-A <2.5 A
    # and D-H-A >120 degrees.  This is geometry evidence, not bond energy.
    mask = (distances <= 0.25) & (angles >= np.deg2rad(120.0))
    rows: list[dict[str, Any]] = []
    for col, (donor_idx, hydrogen_idx, acceptor_idx) in enumerate(triplets):
        frac = float(np.mean(mask[:, col]))
        if frac <= 0:
            continue
        donor = traj.topology.atom(int(donor_idx))
        hydrogen = traj.topology.atom(int(hydrogen_idx))
        acceptor = traj.topology.atom(int(acceptor_idx))
        rows.append({
            "donor_atom_index": int(donor_idx),
            "donor": str(donor),
            "donor_chain": _chain_identifier(donor.residue.chain),
            "hydrogen_atom_index": int(hydrogen_idx),
            "hydrogen": str(hydrogen),
            "acceptor_atom_index": int(acceptor_idx),
            "acceptor": str(acceptor),
            "acceptor_chain": _chain_identifier(acceptor.residue.chain),
            "distance_cutoff_A": 2.5,
            "angle_cutoff_deg": 120.0,
            "persistence_fraction": frac,
        })
    rows.sort(key=lambda x: x["persistence_fraction"], reverse=True)
    return rows


def analyze_trajectory(
    topology_pdb: str | Path,
    trajectory_path: str | Path,
    output_dir: str | Path,
    *,
    peptide_chain_ids: Iterable[str] = ("B", "P"),
    contact_cutoff_nm: float = 0.45,
    clusters: int = 5,
    stride: int = 1,
) -> dict[str, Any]:
    ready = backend_readiness()
    if not ready["available"]:
        raise RuntimeError("MDTraj is not installed; Pepforge will not fabricate trajectory analysis.")
    import mdtraj as md
    from sklearn.cluster import KMeans

    top_path = Path(topology_pdb).expanduser().resolve()
    traj_path = Path(trajectory_path).expanduser().resolve()
    if not top_path.exists() or not traj_path.exists():
        raise FileNotFoundError("Topology or trajectory file missing.")
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    traj = md.load(str(traj_path), top=str(top_path), stride=max(1, int(stride)))
    if traj.n_frames < 1:
        raise ValueError("Trajectory contains no frames.")

    ca = traj.topology.select("name CA")
    if ca.size < 2:
        ca = traj.topology.select("protein and element != H")
    if ca.size < 1:
        ca = np.arange(traj.n_atoms)
    aligned = traj.superpose(traj, 0, atom_indices=ca)
    rmsd_nm = md.rmsd(aligned, aligned, 0, atom_indices=ca)
    rg_nm = md.compute_rg(aligned)
    try:
        rmsf_nm = md.rmsf(aligned, aligned[0], atom_indices=ca)
    except Exception:
        rmsf_nm = np.full(len(ca), np.nan)

    frame_rows = [
        {"frame": i, "rmsd_A": float(rmsd_nm[i] * 10.0), "rg_A": float(rg_nm[i] * 10.0)}
        for i in range(traj.n_frames)
    ]
    _write_csv(out / "trajectory_frame_metrics.csv", frame_rows)

    rmsf_rows = []
    for idx, atom_index in enumerate(ca):
        atom = traj.topology.atom(int(atom_index))
        rmsf_rows.append({
            "atom_index": int(atom_index), "chain": _chain_identifier(atom.residue.chain),
            "residue": str(atom.residue), "atom": atom.name,
            "rmsf_A": None if math.isnan(float(rmsf_nm[idx])) else float(rmsf_nm[idx] * 10.0),
        })
    _write_csv(out / "trajectory_rmsf.csv", rmsf_rows)

    peptide_ids = {str(x) for x in peptide_chain_ids}
    peptide_res = [r for r in traj.topology.residues if _chain_identifier(r.chain) in peptide_ids]
    receptor_res = [r for r in traj.topology.residues if _chain_identifier(r.chain) not in peptide_ids and r.is_protein]
    contact_rows: list[dict[str, Any]] = []
    if peptide_res and receptor_res:
        pairs = np.asarray([(r.index, p.index) for r in receptor_res for p in peptide_res], dtype=int)
        if len(pairs):
            dist, pairs_out = md.compute_contacts(aligned, contacts=pairs, scheme="closest-heavy", periodic=False)
            for col, pair in enumerate(pairs_out):
                fraction = float(np.mean(dist[:, col] <= float(contact_cutoff_nm)))
                if fraction <= 0:
                    continue
                r1, r2 = traj.topology.residue(int(pair[0])), traj.topology.residue(int(pair[1]))
                contact_rows.append({
                    "receptor_residue": str(r1), "receptor_chain": _chain_identifier(r1.chain),
                    "peptide_residue": str(r2), "peptide_chain": _chain_identifier(r2.chain),
                    "contact_cutoff_A": float(contact_cutoff_nm) * 10.0,
                    "persistence_fraction": fraction,
                })
            contact_rows.sort(key=lambda x: x["persistence_fraction"], reverse=True)
    _write_csv(out / "interface_contact_persistence.csv", contact_rows)

    hbond_rows = _hydrogen_bond_persistence(aligned)
    _write_csv(out / "hydrogen_bond_persistence.csv", hbond_rows)

    ss_rows, ss_summary = _secondary_structure_summary(aligned)
    _write_csv(out / "secondary_structure_by_frame.csv", ss_rows)

    # Cluster on aligned C-alpha coordinates. Cluster occupancy is descriptive,
    # never converted to folding probability.
    features = aligned.xyz[:, ca, :].reshape(traj.n_frames, -1)
    k = max(1, min(int(clusters), traj.n_frames))
    km = KMeans(n_clusters=k, random_state=20260928, n_init=10).fit(features)
    cluster_rows: list[dict[str, Any]] = []
    medoid_files: list[str] = []
    for cluster in range(k):
        members = np.where(km.labels_ == cluster)[0]
        centroid = km.cluster_centers_[cluster]
        distances = np.linalg.norm(features[members] - centroid, axis=1)
        medoid_frame = int(members[int(np.argmin(distances))])
        pdb_path = out / f"cluster_{cluster+1:02d}_medoid_frame_{medoid_frame:05d}.pdb"
        aligned[medoid_frame].save_pdb(str(pdb_path))
        medoid_files.append(str(pdb_path))
        cluster_rows.append({
            "cluster": cluster + 1, "frames": int(len(members)),
            "occupancy_fraction": float(len(members) / traj.n_frames), "medoid_frame": medoid_frame,
            "medoid_pdb": str(pdb_path),
        })
    cluster_rows.sort(key=lambda x: x["occupancy_fraction"], reverse=True)
    _write_csv(out / "trajectory_clusters.csv", cluster_rows)

    midpoint = max(1, traj.n_frames // 2)
    first = rmsd_nm[:midpoint] * 10.0
    second = rmsd_nm[midpoint:] * 10.0 if midpoint < traj.n_frames else first
    drift = float(abs(np.mean(second) - np.mean(first))) if len(first) and len(second) else None
    autocorr = {
        "rmsd": _integrated_autocorrelation_diagnostics(rmsd_nm * 10.0),
        "radius_of_gyration": _integrated_autocorrelation_diagnostics(rg_nm * 10.0),
        "claim_guard": "Autocorrelation/ESS values are sampling diagnostics only and are not a convergence certificate.",
    }

    summary = {
        "version": TRAJECTORY_ANALYSIS_VERSION,
        "status": "COMPLETED",
        "frames": int(traj.n_frames), "atoms": int(traj.n_atoms),
        "mean_rmsd_A": float(np.mean(rmsd_nm) * 10.0),
        "median_rmsd_A": float(np.median(rmsd_nm) * 10.0),
        "mean_rg_A": float(np.mean(rg_nm) * 10.0),
        "first_second_half_rmsd_mean_shift_A": drift,
        "interface_contact_pairs_observed": len(contact_rows),
        "hydrogen_bonds_observed": len(hbond_rows),
        "secondary_structure": ss_summary,
        "autocorrelation_diagnostics": autocorr,
        "cluster_count": k, "cluster_rows": cluster_rows,
        "files": {
            "frame_metrics": str(out / "trajectory_frame_metrics.csv"),
            "rmsf": str(out / "trajectory_rmsf.csv"),
            "contact_persistence": str(out / "interface_contact_persistence.csv"),
            "hbond_persistence": str(out / "hydrogen_bond_persistence.csv"),
            "secondary_structure": str(out / "secondary_structure_by_frame.csv"),
            "clusters": str(out / "trajectory_clusters.csv"),
            "medoids": medoid_files,
        },
        "claim_guard": "Cluster occupancy, secondary-structure fractions, and finite-trajectory stability are descriptive simulation evidence, not folding probability, equilibrium proof, affinity, or functional validation.",
    }
    (out / "trajectory_analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def summarize_replicates(analyses: Iterable[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    rows = [dict(x) for x in analyses if str(x.get("status")) == "COMPLETED"]
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not rows:
        summary = {
            "status": "NO_COMPLETED_REPLICATES", "replicate_count": 0,
            "claim_guard": "No replicate convergence claim is available.",
        }
    else:
        rmsds = [float(x["mean_rmsd_A"]) for x in rows]
        rgs = [float(x["mean_rg_A"]) for x in rows]
        drifts = [float(x["first_second_half_rmsd_mean_shift_A"]) for x in rows if x.get("first_second_half_rmsd_mean_shift_A") is not None]
        contact_counts = [int(x.get("interface_contact_pairs_observed", 0)) for x in rows]
        hb_counts = [int(x.get("hydrogen_bonds_observed", 0)) for x in rows]
        summary = {
            "status": "COMPLETED", "replicate_count": len(rows),
            "mean_rmsd_A_across_replicates": float(np.mean(rmsds)),
            "rmsd_between_replicate_means_range_A": float(max(rmsds) - min(rmsds)) if len(rmsds) > 1 else 0.0,
            "mean_rg_A_across_replicates": float(np.mean(rgs)),
            "rg_between_replicate_means_range_A": float(max(rgs) - min(rgs)) if len(rgs) > 1 else 0.0,
            "mean_first_second_half_rmsd_shift_A": float(np.mean(drifts)) if drifts else None,
            "interface_contact_pair_count_range": [min(contact_counts), max(contact_counts)] if contact_counts else [0, 0],
            "hydrogen_bond_count_range": [min(hb_counts), max(hb_counts)] if hb_counts else [0, 0],
            "replicate_metrics": [
                {
                    "replicate": x.get("replicate"),
                    "mean_rmsd_A": x.get("mean_rmsd_A"),
                    "mean_rg_A": x.get("mean_rg_A"),
                    "drift_A": x.get("first_second_half_rmsd_mean_shift_A"),
                    "contacts": x.get("interface_contact_pairs_observed"),
                    "hbonds": x.get("hydrogen_bonds_observed"),
                }
                for x in rows
            ],
            "claim_guard": "Replicate agreement/disagreement is reported descriptively; no binary convergence grade is inferred from these summaries alone.",
        }
    path = out / "replicate_comparison.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


__all__ = ["TRAJECTORY_ANALYSIS_VERSION", "backend_readiness", "analyze_trajectory", "summarize_replicates"]
