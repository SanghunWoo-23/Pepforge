from __future__ import annotations
from pathlib import Path
import json, re

CATEGORY_COLORS = {
    "std_aa": "white",
    "d_std_aa": "hotpink",
    "non_natural_aa": "yelloworange",
    "sidechain_label_aa": "magenta",
    "linker": "cyan",
    "label": "lime",
    "chemical": "tv_orange",
    "n_terminal": "orange",
    "c_terminal_atom": "marine",
}

def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_") or "pepforge_model"

def make_pymol_pml(meta_path: str | Path, output_path: str | Path | None = None, prefer: str = "sdf") -> Path:
    """Create a portable PML loader for a generated Pepforge structure.

    This is intentionally NOT a PyMOL plugin. It is a plain PyMOL script that can
    be opened with File > Run Script or launched as `pymol file.pml`.

    v1.3.0 portability rule
    -----------------------
    The PML starts with `cd <folder containing the PML>` and loads only the local
    structure filename. This keeps generated examples usable after moving the
    project folder to another computer.
    """
    meta_path = Path(meta_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    obj = _safe_name(Path(meta.get("sdf_path") or meta_path.stem).stem)
    structure_value = meta.get("sdf_path") if prefer.lower() == "sdf" else meta.get("pdb_path")
    structure_path = Path(structure_value)
    if not structure_path.is_absolute():
        if structure_path.exists():
            structure_path = structure_path.resolve()
        else:
            structure_path = (meta_path.parent / structure_path.name).resolve()
    output_path = Path(output_path) if output_path else meta_path.with_suffix(".pml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atom_ranges = meta.get("atom_ranges") or []

    # Make PML portable: keep structure beside the PML and load by filename after cd.
    pml_dir = output_path.parent.resolve()
    try:
        rel_structure = structure_path.resolve().relative_to(pml_dir)
        load_target = rel_structure.as_posix()
    except Exception:
        load_target = structure_path.name

    lines = []
    lines.append(f"# Pepforge PyMOL Structure Tool loader v{meta.get('version','1.0.0')}")
    lines.append("# This is not a PyMOL plugin. It only loads and styles an already generated structure.")
    lines.append(f"cd {pml_dir.as_posix()}")
    lines.append(f"load {load_target}, {obj}")
    lines.append(f"hide everything, {obj}")
    lines.append(f"show sticks, {obj}")
    lines.append(f"set stick_radius, 0.14, {obj}")
    lines.append(f"set sphere_scale, 0.18, {obj}")
    lines.append(f"hide everything, {obj} and elem H")
    lines.append("set valence, on")
    lines.append("set label_size, 13")
    lines.append("set label_color, black")
    lines.append(f"color gray80, {obj}")
    lines.append("")
    for i, r in enumerate(atom_ranges, start=1):
        start, end = r.get("heavy_start_1based"), r.get("heavy_end_1based")
        if not start or not end:
            continue
        token = _safe_name(r.get("token", f"tok{i}"))
        kind = r.get("kind", "unknown")
        sel = f"{obj}_{i:02d}_{token}_{_safe_name(kind)}"
        color = CATEGORY_COLORS.get(kind, "gray80")
        lines.append(f"select {sel}, {obj} and index {start}-{end}")
        lines.append(f"color {color}, {sel}")
        lines.append(f"label {sel} and index {start}, \"{r.get('token', '?')}\"")
    lines.append("")
    attach_points = meta.get("attach_point_map") or []
    for j, ap in enumerate(attach_points, start=1):
        token = _safe_name(ap.get("token", f"attach{j}"))
        kind = _safe_name(ap.get("kind", "unit"))
        gin = ap.get("global_in_atom_1based")
        gout = ap.get("global_out_atom_1based")
        if gin:
            sel = f"{obj}_attach_{j:02d}_{token}_IN"
            lines.append(f"select {sel}, {obj} and index {gin}")
            lines.append(f"show spheres, {sel}")
            lines.append(f"color blue, {sel}")
            lines.append(f"label {sel}, \"{ap.get('token','?')} IN\"")
        if gout:
            sel = f"{obj}_attach_{j:02d}_{token}_OUT"
            lines.append(f"select {sel}, {obj} and index {gout}")
            lines.append(f"show spheres, {sel}")
            lines.append(f"color red, {sel}")
            lines.append(f"label {sel}, \"{ap.get('token','?')} OUT\"")
    lines.append("")
    kinds = sorted(set(r.get("kind") for r in atom_ranges if r.get("kind")))
    for kind in kinds:
        chunks = []
        for r in atom_ranges:
            if r.get("kind") == kind:
                chunks.append(f"index {r.get('heavy_start_1based')}-{r.get('heavy_end_1based')}")
        if chunks:
            sel_name = f"{obj}_{_safe_name(kind)}"
            expr = " or ".join(chunks)
            lines.append(f"select {sel_name}, {obj} and ({expr})")
    lines.append("")
    lines.append(f"orient {obj}")
    lines.append(f"zoom {obj}, 5")
    lines.append("set ray_opaque_background, off")
    lines.append("")
    lines.append("# Category colors")
    for k, c in CATEGORY_COLORS.items():
        lines.append(f"# {k}: {c}")
    lines.append("")
    lines.append("# Attach-point display: blue sphere = inferred IN atom, red sphere = inferred OUT atom")
    lines.append(f"# Input: {meta.get('input')}")
    lines.append(f"# Formula: {meta.get('formula')}")
    lines.append(f"# Exact MW: {meta.get('exact_mw')}")
    for w in meta.get("warnings") or []:
        lines.append(f"# WARNING: {w}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path

def make_batch_pml(meta_paths: list[str | Path], output_path: str | Path, prefer: str = "sdf") -> Path:
    output_path = Path(output_path)
    lines = ["# Pepforge batch PyMOL loader", "delete all", ""]
    for mp in meta_paths:
        mp = Path(mp)
        single = make_pymol_pml(mp, mp.with_suffix(".pml"), prefer=prefer)
        lines.append(f"@{single.as_posix()}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
