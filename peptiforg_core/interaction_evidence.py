from __future__ import annotations

"""Geometry-aware protein/peptide interaction evidence for Pepforge V4.0.0.

The conservative profile follows the user's PyMOL manual-screening guide:
interaction-specific measurement points are used instead of one generic residue
cutoff.  Distance-only candidates are kept distinct from geometry-supported
interactions, and no interaction count is converted into affinity/Kd/confidence.
"""

from dataclasses import dataclass, asdict
from typing import Any
import math
import numpy as np
import pandas as pd

INTERACTION_EVIDENCE_VERSION = "1.1.0"


@dataclass(frozen=True)
class InteractionProfile:
    name: str
    hbond_da_max_A: float
    hbond_angle_min_deg: float
    hydrophobic_min_A: float
    hydrophobic_max_A: float
    salt_bridge_max_A: float
    pi_pi_centroid_max_A: float
    pi_parallel_max_deg: float
    pi_t_min_deg: float
    pi_t_max_deg: float
    pi_offset_max_A: float
    cation_pi_max_A: float
    cation_pi_offset_max_A: float
    serious_clash_overlap_A: float
    disulfide_min_A: float
    disulfide_max_A: float
    water_bridge_min_A: float
    water_bridge_max_A: float
    metal_coordination_max_A: float
    halogen_bond_max_A: float
    halogen_angle_min_deg: float
    aromatic_s_max_A: float
    weak_ch_acceptor_max_A: float
    weak_ch_angle_min_deg: float
    nh_pi_max_A: float


PROFILES = {
    "CONSERVATIVE_MANUAL": InteractionProfile(
        name="CONSERVATIVE_MANUAL",
        hbond_da_max_A=3.5,
        hbond_angle_min_deg=120.0,
        hydrophobic_min_A=3.3,
        hydrophobic_max_A=5.0,
        salt_bridge_max_A=4.0,
        pi_pi_centroid_max_A=5.0,
        pi_parallel_max_deg=30.0,
        pi_t_min_deg=60.0,
        pi_t_max_deg=90.0,
        pi_offset_max_A=2.0,
        cation_pi_max_A=5.0,
        cation_pi_offset_max_A=2.0,
        serious_clash_overlap_A=0.4,
        disulfide_min_A=2.0,
        disulfide_max_A=2.1,
        water_bridge_min_A=2.5,
        water_bridge_max_A=3.5,
        metal_coordination_max_A=3.0,
        halogen_bond_max_A=3.5,
        halogen_angle_min_deg=150.0,
        aromatic_s_max_A=5.0,
        weak_ch_acceptor_max_A=3.5,
        weak_ch_angle_min_deg=120.0,
        nh_pi_max_A=3.9,
    ),
    "TOOL_COMPATIBLE": InteractionProfile(
        name="TOOL_COMPATIBLE",
        hbond_da_max_A=4.1,
        hbond_angle_min_deg=100.0,
        hydrophobic_min_A=0.0,
        hydrophobic_max_A=4.0,
        salt_bridge_max_A=5.5,
        pi_pi_centroid_max_A=5.5,
        pi_parallel_max_deg=30.0,
        pi_t_min_deg=60.0,
        pi_t_max_deg=90.0,
        pi_offset_max_A=2.0,
        cation_pi_max_A=6.0,
        cation_pi_offset_max_A=2.0,
        serious_clash_overlap_A=0.4,
        disulfide_min_A=2.0,
        disulfide_max_A=2.08,
        water_bridge_min_A=2.5,
        water_bridge_max_A=4.1,
        metal_coordination_max_A=3.0,
        halogen_bond_max_A=4.0,
        halogen_angle_min_deg=135.0,
        aromatic_s_max_A=5.3,
        weak_ch_acceptor_max_A=3.5,
        weak_ch_angle_min_deg=120.0,
        nh_pi_max_A=3.9,
    ),
}

VDW_RADII = {"H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "P": 1.80, "S": 1.80, "CL": 1.75, "BR": 1.85, "I": 1.98}
AROMATIC_RINGS = {
    "PHE": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
    "TYR": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
    "HIS": ["CG", "ND1", "CD2", "CE1", "NE2"],
    "TRP": ["CG", "CD1", "NE1", "CE2", "CD2", "CE3", "CZ3", "CH2", "CZ2"],
}
POSITIVE_GROUPS = {
    "LYS": ["NZ"],
    "ARG": ["CZ", "NH1", "NH2"],
    # Histidine protonation is not inferable reliably from a generic PDB name.
}
NEGATIVE_GROUPS = {"ASP": ["OD1", "OD2"], "GLU": ["OE1", "OE2"]}
DONORS = {
    "BACKBONE": ["N"], "LYS": ["NZ"], "ARG": ["NE", "NH1", "NH2"], "ASN": ["ND2"], "GLN": ["NE2"],
    "SER": ["OG"], "THR": ["OG1"], "TYR": ["OH"], "TRP": ["NE1"], "HIS": ["ND1", "NE2"], "CYS": ["SG"],
}
ACCEPTORS = {
    "BACKBONE": ["O", "OXT"], "ASP": ["OD1", "OD2"], "GLU": ["OE1", "OE2"], "ASN": ["OD1"], "GLN": ["OE1"],
    "SER": ["OG"], "THR": ["OG1"], "TYR": ["OH"], "HIS": ["ND1", "NE2"], "CYS": ["SG"], "MET": ["SD"],
}
WATER_RESN = {"HOH", "WAT", "H2O", "TIP3", "TIP3P"}
METAL_ELEMENTS = {"ZN", "MG", "CA", "FE", "MN", "CU", "CO", "NI"}
HALOGEN_ELEMENTS = {"CL", "BR", "I"}
COORDINATING_ELEMENTS = {"N", "O", "S"}


def profile(name: str = "CONSERVATIVE_MANUAL") -> InteractionProfile:
    key = str(name or "CONSERVATIVE_MANUAL").strip().upper()
    if key not in PROFILES:
        raise ValueError(f"Unknown interaction profile: {name}. Choose one of {sorted(PROFILES)}")
    return PROFILES[key]


def profile_table() -> pd.DataFrame:
    rows = []
    for p in PROFILES.values():
        data = asdict(p)
        name = data.pop("name")
        for metric, value in data.items():
            rows.append({"profile": name, "metric": metric, "value": value, "unit": "degree" if metric.endswith("deg") else "Angstrom"})
    return pd.DataFrame(rows)


def _norm_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["atom", "resn", "chain", "resi", "x", "y", "z", "element", "aa"])
    df = frame.copy()
    for c in ["atom", "resn", "chain", "resi", "element", "aa"]:
        if c not in df:
            df[c] = ""
        df[c] = df[c].astype(str)
    for c in ["x", "y", "z"]:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df = df.dropna(subset=["x", "y", "z"]).reset_index(drop=True)
    df["atom"] = df["atom"].str.upper()
    df["resn"] = df["resn"].str.upper()
    df["element"] = df["element"].str.upper()
    return df


def _res_key(row: pd.Series) -> tuple[str, str, str]:
    return str(row.get("chain", "")), str(row.get("resi", "")), str(row.get("resn", ""))


def _res_label(key: tuple[str, str, str]) -> str:
    chain, resi, resn = key
    return f"{chain}:{resi}{resn}" if chain else f"{resi}{resn}"


def _distance(a: pd.Series, b: pd.Series) -> float:
    return float(np.linalg.norm(np.asarray([a.x, a.y, a.z], dtype=float) - np.asarray([b.x, b.y, b.z], dtype=float)))


def _is_donor(row: pd.Series) -> bool:
    resn, atom = str(row.resn), str(row.atom)
    if atom in DONORS["BACKBONE"] and resn != "PRO":
        return True
    return atom in DONORS.get(resn, [])


def _is_acceptor(row: pd.Series) -> bool:
    resn, atom = str(row.resn), str(row.atom)
    return atom in ACCEPTORS["BACKBONE"] or atom in ACCEPTORS.get(resn, [])


def _is_generic_acceptor(row: pd.Series) -> bool:
    if _is_acceptor(row):
        return True
    return str(row.element) in {"O", "N", "S"}


def _is_nonpolar(row: pd.Series) -> bool:
    # Operational atom-level definition: carbon/sulfur side-chain atoms,
    # excluding backbone carbonyl C and explicitly charged-group atoms.
    if str(row.element) not in {"C", "S"}:
        return False
    if str(row.atom) == "C":
        return False
    resn, atom = str(row.resn), str(row.atom)
    if atom in POSITIVE_GROUPS.get(resn, []) or atom in NEGATIVE_GROUPS.get(resn, []):
        return False
    return True


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    # A-B-C angle at B.
    v1 = a - b
    v2 = c - b
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    cosv = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosv)))


def _explicit_h_angle(donor: pd.Series, acceptor: pd.Series, same_molecule: pd.DataFrame) -> float | None:
    d = np.asarray([donor.x, donor.y, donor.z], dtype=float)
    a = np.asarray([acceptor.x, acceptor.y, acceptor.z], dtype=float)
    hyd = same_molecule[same_molecule["element"].eq("H")]
    if hyd.empty:
        return None
    xyz = hyd[["x", "y", "z"]].to_numpy(dtype=float)
    ds = np.linalg.norm(xyz - d[None, :], axis=1)
    idx = np.where(ds <= 1.30)[0]
    if not len(idx):
        return None
    angles = [_angle_deg(d, xyz[i], a) for i in idx]
    angles = [x for x in angles if math.isfinite(x)]
    return max(angles) if angles else None


def _explicit_h_angle_from_carbon(carbon: pd.Series, acceptor: pd.Series, same_molecule: pd.DataFrame) -> float | None:
    return _explicit_h_angle(carbon, acceptor, same_molecule)


def _ring_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for key, group in frame.groupby(["chain", "resi", "resn"], dropna=False):
        names = AROMATIC_RINGS.get(str(key[2]).upper())
        if not names:
            continue
        ring = group[group["atom"].isin(names)]
        if len(ring) < 4:
            continue
        pts = ring[["x", "y", "z"]].to_numpy(dtype=float)
        centroid = pts.mean(axis=0)
        centered = pts - centroid
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            normal = vh[-1]
            normal = normal / max(np.linalg.norm(normal), 1e-12)
        except Exception:
            continue
        out.append({"key": tuple(map(str, key)), "centroid": centroid, "normal": normal, "atoms": ";".join(ring["atom"].tolist())})
    return out


def _charge_groups(frame: pd.DataFrame, positive: bool) -> list[dict[str, Any]]:
    defs = POSITIVE_GROUPS if positive else NEGATIVE_GROUPS
    out = []
    for key, group in frame.groupby(["chain", "resi", "resn"], dropna=False):
        names = defs.get(str(key[2]).upper())
        if not names:
            continue
        atoms = group[group["atom"].isin(names)]
        if atoms.empty:
            continue
        out.append({"key": tuple(map(str, key)), "center": atoms[["x", "y", "z"]].to_numpy(dtype=float).mean(axis=0), "atoms": ";".join(atoms["atom"].tolist())})
    return out


def _vdw_radius(element: str) -> float:
    return VDW_RADII.get(str(element or "").upper(), 1.70)


def _is_disulfide_pair(a: pd.Series, b: pd.Series, p: InteractionProfile, d: float) -> bool:
    return (
        str(a.resn) == "CYS" and str(a.atom) == "SG" and
        str(b.resn) == "CYS" and str(b.atom) == "SG" and
        p.disulfide_min_A <= d <= p.disulfide_max_A
    )


def _bonded_carbon_for_halogen(x: pd.Series, frame: pd.DataFrame) -> pd.Series | None:
    same = frame[
        frame["chain"].eq(str(x.chain)) &
        frame["resi"].eq(str(x.resi)) &
        frame["element"].eq("C")
    ]
    if same.empty:
        return None
    xyz = same[["x", "y", "z"]].to_numpy(dtype=float)
    xxyz = np.asarray([x.x, x.y, x.z], dtype=float)
    ds = np.linalg.norm(xyz - xxyz[None, :], axis=1)
    idx = int(np.argmin(ds))
    # A permissive covalent-neighbour screen; it is used only to determine angle,
    # never as an interaction cutoff.
    if float(ds[idx]) > 2.3:
        return None
    return same.iloc[idx]


def analyze_interaction_evidence(
    target_atoms: pd.DataFrame,
    peptide_atoms: pd.DataFrame,
    *,
    profile_name: str = "CONSERVATIVE_MANUAL",
    representative_only: bool = True,
) -> pd.DataFrame:
    p = profile(profile_name)
    t_all = _norm_frame(target_atoms)
    q_all = _norm_frame(peptide_atoms)
    columns = [
        "interaction", "representative", "profile", "target_residue", "peptide_residue",
        "target_atoms", "peptide_atoms", "distance_A", "angle_deg", "plane_angle_deg",
        "offset_A", "vdw_overlap_A", "geometry_status", "evidence_level", "note",
    ]
    if t_all.empty or q_all.empty:
        return pd.DataFrame(columns=columns)

    # Water is a third-body bridge, not the protein or peptide residue in the
    # reported pair. Keep it out of direct-contact loops and inspect separately.
    t_water = t_all[t_all["resn"].isin(WATER_RESN)].copy()
    q_water = q_all[q_all["resn"].isin(WATER_RESN)].copy()
    waters = pd.concat([t_water, q_water], ignore_index=True)
    waters = waters[waters["element"].eq("O")]
    t = t_all[~t_all["resn"].isin(WATER_RESN)].reset_index(drop=True)
    q = q_all[~q_all["resn"].isin(WATER_RESN)].reset_index(drop=True)
    if t.empty or q.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []

    def add(interaction: str, tk, qk, *, ta="", qa="", distance=None, angle=None, plane=None, offset=None, overlap=None, geometry="distance_only", level="candidate", note=""):
        rows.append({
            "interaction": interaction,
            "representative": True,
            "profile": p.name,
            "target_residue": _res_label(tk),
            "peptide_residue": _res_label(qk),
            "target_atoms": ta,
            "peptide_atoms": qa,
            "distance_A": None if distance is None else round(float(distance), 3),
            "angle_deg": None if angle is None else round(float(angle), 2),
            "plane_angle_deg": None if plane is None else round(float(plane), 2),
            "offset_A": None if offset is None else round(float(offset), 3),
            "vdw_overlap_A": None if overlap is None else round(float(overlap), 3),
            "geometry_status": geometry,
            "evidence_level": level,
            "note": note,
        })

    # Clash / vdW and atom-level H-bond/hydrophobic/weak-contact candidates.
    closest_by_hbond: dict[tuple, tuple] = {}
    closest_by_hyd: dict[tuple, tuple] = {}
    closest_vdw: dict[tuple, tuple] = {}
    closest_weak_ch: dict[tuple, tuple] = {}
    for _, qa in q.iterrows():
        qxyz = np.asarray([qa.x, qa.y, qa.z], dtype=float)
        dxyz = t[["x", "y", "z"]].to_numpy(dtype=float) - qxyz[None, :]
        dist = np.linalg.norm(dxyz, axis=1)
        near_max = max(6.0, p.hydrophobic_max_A, p.hbond_da_max_A, p.salt_bridge_max_A, p.aromatic_s_max_A)
        near_idx = np.where(dist <= near_max)[0]
        for idx in near_idx:
            ta = t.iloc[int(idx)]
            d = float(dist[int(idx)])
            pair = (_res_key(ta), _res_key(qa))
            disulfide = _is_disulfide_pair(ta, qa, p, d)
            overlap = _vdw_radius(ta.element) + _vdw_radius(qa.element) - d
            # A Cys SG-SG pair in the disulfide distance range is a covalent
            # candidate, not a nonbonded clash.
            if not disulfide and overlap >= p.serious_clash_overlap_A:
                add("clash", pair[0], pair[1], ta=ta.atom, qa=qa.atom, distance=d, overlap=overlap, geometry="serious_vdw_overlap", level="structure_warning", note="Serious nonbonded vdW overlap; do not count as a favorable interaction without covalent/connectivity review.")
            elif not disulfide and abs(overlap) <= 0.35:
                old = closest_vdw.get(pair)
                if old is None or abs(overlap) < abs(old[0]):
                    closest_vdw[pair] = (overlap, d, ta, qa)

            if disulfide:
                add("disulfide", pair[0], pair[1], ta=ta.atom, qa=qa.atom, distance=d, geometry="SG_SG_distance_pass_geometry_review", level="candidate", note="Cys SG-SG distance is in the ~2.0-2.1 A manual range; covalent connectivity/geometry should also be verified.")

            hb = (_is_donor(ta) and _is_acceptor(qa)) or (_is_acceptor(ta) and _is_donor(qa))
            if hb and d <= p.hbond_da_max_A:
                old = closest_by_hbond.get(pair)
                if old is None or d < old[0]:
                    closest_by_hbond[pair] = (d, ta, qa)
            if _is_nonpolar(ta) and _is_nonpolar(qa) and p.hydrophobic_min_A <= d <= p.hydrophobic_max_A:
                old = closest_by_hyd.get(pair)
                if old is None or d < old[0]:
                    closest_by_hyd[pair] = (d, ta, qa)

            # Weak C-H...O/N screening. With no explicit H this remains only a
            # secondary distance candidate, matching the manual guide.
            if d <= p.weak_ch_acceptor_max_A:
                candidates = []
                if str(ta.element) == "C" and _is_generic_acceptor(qa):
                    candidates.append((ta, qa, t, True))
                if str(qa.element) == "C" and _is_generic_acceptor(ta):
                    candidates.append((qa, ta, q, False))
                for carbon, acceptor, same, carbon_target in candidates:
                    old = closest_weak_ch.get(pair)
                    if old is None or d < old[0]:
                        closest_weak_ch[pair] = (d, carbon, acceptor, same, carbon_target)

    for pair, (d, ta, qa) in closest_by_hbond.items():
        angle = None
        if _is_donor(ta):
            angle = _explicit_h_angle(ta, qa, t)
        elif _is_donor(qa):
            angle = _explicit_h_angle(qa, ta, q)
        if angle is None:
            geom = "distance_candidate_H_not_available"
            level = "candidate"
        elif angle >= p.hbond_angle_min_deg:
            geom = "distance_and_angle_pass"
            level = "geometry_supported"
        else:
            geom = "angle_fail"
            level = "not_confirmed"
        add("hydrogen_bond", pair[0], pair[1], ta=ta.atom, qa=qa.atom, distance=d, angle=angle, geometry=geom, level=level, note="D-A heavy-atom screening; explicit D-H...A angle is used only when hydrogens are present.")

    for pair, (d, ta, qa) in closest_by_hyd.items():
        add("hydrophobic", pair[0], pair[1], ta=ta.atom, qa=qa.atom, distance=d, geometry="nonpolar_atom_contact", level="geometry_supported", note="Nonpolar atom-to-atom contact; residue-center distance is not used.")

    for pair, (overlap, d, ta, qa) in closest_vdw.items():
        add("van_der_Waals", pair[0], pair[1], ta=ta.atom, qa=qa.atom, distance=d, overlap=overlap, geometry="near_sum_of_vdw_radii", level="packing_contact", note="General packing descriptor; not counted as a specific bond.")

    for pair, (d, carbon, acceptor, same, carbon_target) in closest_weak_ch.items():
        angle = _explicit_h_angle_from_carbon(carbon, acceptor, same)
        if angle is None:
            geometry = "distance_candidate_H_not_available"
            level = "secondary_candidate"
        elif angle >= p.weak_ch_angle_min_deg:
            geometry = "distance_and_angle_pass"
            level = "geometry_supported"
        else:
            geometry = "angle_fail"
            level = "not_confirmed"
        tk, qk = pair
        ta, qa = (carbon.atom, acceptor.atom) if carbon_target else (acceptor.atom, carbon.atom)
        add("weak_C_H_O_N", tk, qk, ta=ta, qa=qa, distance=d, angle=angle, geometry=geometry, level=level, note="Weak C-H...O/N interaction; without explicit H the C...A <=3.5 A screen is secondary evidence only.")

    # Salt bridges from charge-group centers.
    tpos, tneg = _charge_groups(t, True), _charge_groups(t, False)
    qpos, qneg = _charge_groups(q, True), _charge_groups(q, False)
    for positives, negatives, t_is_pos in [(tpos, qneg, True), (qpos, tneg, False)]:
        for pos in positives:
            for neg in negatives:
                d = float(np.linalg.norm(pos["center"] - neg["center"]))
                if d <= p.salt_bridge_max_A:
                    tk, qk = (pos["key"], neg["key"]) if t_is_pos else (neg["key"], pos["key"])
                    ta, qa = (pos["atoms"], neg["atoms"]) if t_is_pos else (neg["atoms"], pos["atoms"])
                    add("salt_bridge", tk, qk, ta=ta, qa=qa, distance=d, geometry="opposite_charge_group_centers", level="geometry_supported", note="Direct opposite-charge group proximity; histidine is excluded unless protonation is explicitly resolved elsewhere.")

    # Aromatic ring records are reused by pi-pi, cation-pi, aromatic-S, and NH-pi.
    trings, qrings = _ring_records(t), _ring_records(q)

    # pi-pi geometry.
    for a in trings:
        for b in qrings:
            dv = b["centroid"] - a["centroid"]
            d = float(np.linalg.norm(dv))
            if d > p.pi_pi_centroid_max_A:
                continue
            angle = math.degrees(math.acos(float(np.clip(abs(np.dot(a["normal"], b["normal"])), 0.0, 1.0))))
            lateral_a = float(np.linalg.norm(dv - np.dot(dv, a["normal"]) * a["normal"]))
            lateral_b = float(np.linalg.norm(dv - np.dot(dv, b["normal"]) * b["normal"]))
            offset = min(lateral_a, lateral_b)
            orient_ok = angle <= p.pi_parallel_max_deg or p.pi_t_min_deg <= angle <= p.pi_t_max_deg
            offset_ok = offset <= p.pi_offset_max_A
            if orient_ok and offset_ok:
                geom = "centroid_orientation_offset_pass"
                level = "geometry_supported"
            else:
                geom = "distance_only_geometry_fail"
                level = "not_confirmed"
            add("pi_pi", a["key"], b["key"], ta=a["atoms"], qa=b["atoms"], distance=d, plane=angle, offset=offset, geometry=geom, level=level, note="Ring centroid + plane orientation + lateral offset; closest C-C distance alone is insufficient.")

    # cation-pi; histidine intentionally not auto-cationic.
    for cat, rings, cat_target in [(tpos, qrings, True), (qpos, trings, False)]:
        for c in cat:
            for ring in rings:
                dv = c["center"] - ring["centroid"]
                d = float(np.linalg.norm(dv))
                if d > p.cation_pi_max_A:
                    continue
                offset = float(np.linalg.norm(dv - np.dot(dv, ring["normal"]) * ring["normal"]))
                ok = offset <= p.cation_pi_offset_max_A
                tk, qk = (c["key"], ring["key"]) if cat_target else (ring["key"], c["key"])
                ta, qa = (c["atoms"], ring["atoms"]) if cat_target else (ring["atoms"], c["atoms"])
                add("cation_pi", tk, qk, ta=ta, qa=qa, distance=d, offset=offset, geometry="ring_face_offset_pass" if ok else "edge_like_offset_fail", level="geometry_supported" if ok else "not_confirmed", note="Cation center to aromatic ring centroid; ring-face positioning is required.")

    # Aromatic-sulfur: sulfur atom to ring centroid. The guide treats this as a
    # secondary interaction because geometry definitions are less standardized.
    for sulfur_frame, rings, sulfur_target in [(t[t["element"].eq("S")], qrings, True), (q[q["element"].eq("S")], trings, False)]:
        for _, sulfur in sulfur_frame.iterrows():
            sxyz = np.asarray([sulfur.x, sulfur.y, sulfur.z], dtype=float)
            for ring in rings:
                d = float(np.linalg.norm(sxyz - ring["centroid"]))
                if d > p.aromatic_s_max_A:
                    continue
                tk, qk = (_res_key(sulfur), ring["key"]) if sulfur_target else (ring["key"], _res_key(sulfur))
                ta, qa = (sulfur.atom, ring["atoms"]) if sulfur_target else (ring["atoms"], sulfur.atom)
                add("aromatic_S", tk, qk, ta=ta, qa=qa, distance=d, geometry="S_to_ring_centroid_distance_pass_geometry_review", level="secondary_candidate", note="S-to-aromatic-system <= cutoff; ring placement should be reviewed because this geometry is less standardized.")

    # NH-pi / amino-aromatic screening. The source guide does not define one
    # universal confirmatory geometry, so <=3.9 A is kept as secondary evidence.
    for donor_frame, rings, donor_target in [(t, qrings, True), (q, trings, False)]:
        donors = donor_frame[donor_frame.apply(_is_donor, axis=1) & donor_frame["element"].eq("N")]
        for _, donor in donors.iterrows():
            dxyz = np.asarray([donor.x, donor.y, donor.z], dtype=float)
            for ring in rings:
                d = float(np.linalg.norm(dxyz - ring["centroid"]))
                if d > p.nh_pi_max_A:
                    continue
                tk, qk = (_res_key(donor), ring["key"]) if donor_target else (ring["key"], _res_key(donor))
                ta, qa = (donor.atom, ring["atoms"]) if donor_target else (ring["atoms"], donor.atom)
                add("NH_pi", tk, qk, ta=ta, qa=qa, distance=d, geometry="donor_to_aromatic_screen_geometry_review", level="secondary_candidate", note="NH-pi/amino-aromatic screening <=3.9 A; aromatic-plane and donor-H direction require manual review.")

    # Metal coordination: distance can be screened automatically, but final
    # geometry is metal-specific and therefore remains a candidate.
    for metal_frame, coord_frame, metal_target in [(t[t["element"].isin(METAL_ELEMENTS)], q, True), (q[q["element"].isin(METAL_ELEMENTS)], t, False)]:
        acceptors = coord_frame[coord_frame["element"].isin(COORDINATING_ELEMENTS)]
        for _, metal in metal_frame.iterrows():
            for _, atom in acceptors.iterrows():
                d = _distance(metal, atom)
                if d > p.metal_coordination_max_A:
                    continue
                tk, qk = (_res_key(metal), _res_key(atom)) if metal_target else (_res_key(atom), _res_key(metal))
                ta, qa = (metal.atom, atom.atom) if metal_target else (atom.atom, metal.atom)
                add("metal_coordination", tk, qk, ta=ta, qa=qa, distance=d, geometry="distance_pass_metal_geometry_review", level="candidate", note="Metal-to-coordinating atom <=3.0 A screen; coordination number and metal-specific geometry must be checked.")

    # Halogen bond: X...acceptor distance plus C-X...A direction when the carbon
    # covalently attached to X is present in the same coordinate frame.
    for hal_frame, acc_frame, same_frame, hal_target in [(t[t["element"].isin(HALOGEN_ELEMENTS)], q, t, True), (q[q["element"].isin(HALOGEN_ELEMENTS)], t, q, False)]:
        acceptors = acc_frame[acc_frame.apply(_is_generic_acceptor, axis=1)]
        for _, x in hal_frame.iterrows():
            carbon = _bonded_carbon_for_halogen(x, same_frame)
            for _, acc in acceptors.iterrows():
                d = _distance(x, acc)
                if d > p.halogen_bond_max_A:
                    continue
                angle = None
                if carbon is not None:
                    angle = _angle_deg(
                        np.asarray([carbon.x, carbon.y, carbon.z], dtype=float),
                        np.asarray([x.x, x.y, x.z], dtype=float),
                        np.asarray([acc.x, acc.y, acc.z], dtype=float),
                    )
                if angle is None:
                    geometry = "distance_candidate_CX_geometry_unavailable"
                    level = "candidate"
                elif angle >= p.halogen_angle_min_deg:
                    geometry = "distance_and_CX_acceptor_angle_pass"
                    level = "geometry_supported"
                else:
                    geometry = "CX_acceptor_angle_fail"
                    level = "not_confirmed"
                tk, qk = (_res_key(x), _res_key(acc)) if hal_target else (_res_key(acc), _res_key(x))
                ta, qa = (x.atom, acc.atom) if hal_target else (acc.atom, x.atom)
                add("halogen_bond", tk, qk, ta=ta, qa=qa, distance=d, angle=angle, geometry=geometry, level=level, note="Halogen X...acceptor distance plus C-X...A direction; distance alone does not confirm a halogen bond.")

    # Water bridge: one explicit water O must sit within the configured range of
    # one target and one peptide polar atom. Without explicit H geometry the
    # result remains a candidate, exactly as requested by the manual guide.
    if not waters.empty:
        tpolar = t[t.apply(lambda r: _is_donor(r) or _is_acceptor(r), axis=1)]
        qpolar = q[q.apply(lambda r: _is_donor(r) or _is_acceptor(r), axis=1)]
        for _, water in waters.iterrows():
            wxyz = np.asarray([water.x, water.y, water.z], dtype=float)
            tnear = []
            qnear = []
            for _, atom in tpolar.iterrows():
                d = float(np.linalg.norm(np.asarray([atom.x, atom.y, atom.z], dtype=float) - wxyz))
                if p.water_bridge_min_A <= d <= p.water_bridge_max_A:
                    tnear.append((d, atom))
            for _, atom in qpolar.iterrows():
                d = float(np.linalg.norm(np.asarray([atom.x, atom.y, atom.z], dtype=float) - wxyz))
                if p.water_bridge_min_A <= d <= p.water_bridge_max_A:
                    qnear.append((d, atom))
            for dt, ta in sorted(tnear, key=lambda x: x[0])[:4]:
                for dq, qa in sorted(qnear, key=lambda x: x[0])[:4]:
                    bridge_angle = _angle_deg(
                        np.asarray([ta.x, ta.y, ta.z], dtype=float),
                        wxyz,
                        np.asarray([qa.x, qa.y, qa.z], dtype=float),
                    )
                    add("water_bridge", _res_key(ta), _res_key(qa), ta=f"{ta.atom}->water:{water.chain}:{water.resi}", qa=f"water:{water.chain}:{water.resi}->{qa.atom}", distance=max(dt, dq), angle=bridge_angle, geometry="two_distance_pass_Hbond_geometry_review", level="candidate", note=f"Explicit water O bridges polar atoms ({dt:.2f}/{dq:.2f} A); donor/acceptor H-bond geometry should be reviewed.")

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    if representative_only:
        # A more specific interaction represents the same residue pair. Clash is
        # retained independently as a structure warning, except disulfide-range
        # SG-SG contacts which were excluded from clash generation above.
        priority = {
            "disulfide": 0,
            "metal_coordination": 1,
            "salt_bridge": 2,
            "pi_pi": 3,
            "cation_pi": 4,
            "halogen_bond": 5,
            "hydrogen_bond": 6,
            "water_bridge": 7,
            "aromatic_S": 8,
            "NH_pi": 9,
            "weak_C_H_O_N": 10,
            "hydrophobic": 11,
            "van_der_Waals": 12,
        }
        df["_priority"] = df["interaction"].map(priority).fillna(99)
        out = []
        for _, g in df.groupby(["target_residue", "peptide_residue"], sort=False):
            clashes = g[g["interaction"].eq("clash")]
            if not clashes.empty:
                out.append(clashes.sort_values("distance_A").iloc[0])
            favorable = g[~g["interaction"].eq("clash")].sort_values(["_priority", "distance_A"], na_position="last")
            confirmed = favorable[~favorable["evidence_level"].eq("not_confirmed")]
            if not confirmed.empty:
                out.append(confirmed.iloc[0])
            elif not favorable.empty:
                out.append(favorable.iloc[0])
        df = pd.DataFrame(out).drop(columns=["_priority"], errors="ignore").reset_index(drop=True)
    return df[columns]


def interaction_summary(evidence: pd.DataFrame) -> dict[str, Any]:
    if evidence is None or evidence.empty:
        return {"status": "no_interactions", "counts": {}, "claim_guard": "No affinity or binding-energy inference is made."}
    counts = evidence["interaction"].value_counts().to_dict()
    supported = evidence[evidence["evidence_level"].isin(["geometry_supported", "packing_contact"])]
    return {
        "status": "available",
        "profile": str(evidence.iloc[0].get("profile", "")),
        "counts": {str(k): int(v) for k, v in counts.items()},
        "geometry_supported_count": int(len(supported)),
        "structure_warning_count": int((evidence["evidence_level"] == "structure_warning").sum()),
        "claim_guard": "Coordinate-derived interaction evidence only; counts are not affinity, energy, probability, or experimental validation.",
    }


__all__ = [
    "INTERACTION_EVIDENCE_VERSION", "InteractionProfile", "PROFILES", "profile",
    "profile_table", "analyze_interaction_evidence", "interaction_summary",
]
