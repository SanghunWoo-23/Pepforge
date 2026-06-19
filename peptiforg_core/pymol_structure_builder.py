from __future__ import annotations

"""Pepforge PyMOL Structure Builder compatibility layer.

Pepforge v2.1.0 integrates the standalone Pepforge PyMOL Structure Tool v1.3.0.
This wrapper preserves the earlier Pepforge GUI/API names while delegating actual
3D generation to the RDKit-backed, attachment-aware builder.
"""

from dataclasses import dataclass
from pathlib import Path
import csv
import json
import shutil
import tempfile

from pepforge_structure_tool.pepforge_core import (
    VERSION as STRUCTURE_TOOL_VERSION,
    PepforgeBuildError,
    build_structure,
    describe_parse,
    supported_token_table,
    environment_report,
    template_manifest,
    audit_template_files,
)
from pepforge_structure_tool.pymol_script import make_pymol_pml


@dataclass
class PeptideToken:
    raw: str
    token: str
    cls: str
    residue_name: str
    note: str
    position: int | None = None
    d_form: bool = False
    warning: str = ""


def tokenize_modified_peptide(sequence: str) -> list[str]:
    """Compatibility tokenizer used by earlier Pepforge tests/UI.

    The real v2.1.0 builder delegates generation to pepforge_structure_tool v1.3.0,
    but this function keeps the simple public token list stable.
    """
    import re
    if not sequence:
        return []
    s = sequence.strip()
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", "", s).strip("-")
    if not s:
        return []
    parts = [p for p in s.split("-") if p] if "-" in s else []
    if not parts:
        # conservative compact fallback: keep known two-letter D tokens and one-letter AA cores
        known = ["CaffeicAcid", "GallicAcid", "PalmiticAcid", "FITC", "FAM", "TAMRA", "Biotin", "AEEA", "PEG8", "PEG4", "PEG2", "Ahx", "Cha", "Aib", "Nle", "Orn", "Cit", "Hyp", "Dab", "Nal", "Pal", "Myr", "Gal", "Caf", "Nic", "CHS", "Ac", "NH2"]
        i = 0
        parts = []
        while i < len(s):
            if s[i:i+1] == "d" and i + 1 < len(s):
                parts.append(s[i:i+2]); i += 2; continue
            m = next((k for k in sorted(known, key=len, reverse=True) if s[i:].lower().startswith(k.lower())), None)
            if m:
                parts.append(s[i:i+len(m)]); i += len(m)
            else:
                parts.append(s[i]); i += 1
    known_no_split = {"FITC", "FAM", "TAMRA", "BIOTIN", "AEEA", "PEG8", "PEG4", "PEG3", "PEG2", "AHX", "CHA", "AIB", "NLE", "ORN", "CIT", "HYP", "DAB", "NAL", "PAL", "PALMITICACID", "MYR", "MYRISTICACID", "GAL", "GALLICACID", "CAF", "CAFFEICACID", "NIC", "NICOTINICACID", "CHS", "AC", "NH2", "OH", "BOC", "FMOC"}
    out=[]
    for part in parts:
        up = part.upper()
        if len(part) == 2 and part[0] == "d" and part[1].upper() in "ARNDCQEGHILKMFPSTWYV":
            out.append(part)
        elif up not in known_no_split and len(part)>1 and all(ch.upper() in "ARNDCQEGHILKMFPSTWYV" for ch in part):
            out.extend(list(part))
        else:
            out.append(part)
    return out


def classify_tokens(sequence: str) -> list[PeptideToken]:
    # v1.3.0 uses side-chain notation K(FITC). Accept legacy/UI bracket notation K[Biotin].
    import re
    sequence_for_parse = re.sub(r"([A-Za-z])\[([^\]]+)\]", r"\1(\2)", sequence or "")
    parsed = describe_parse(sequence_for_parse)
    rows: list[PeptideToken] = []
    pos = 0
    for row_index, item in enumerate(parsed.get("tokens", [])):
        kind = str(item.get("kind", "unknown"))
        raw = str(item.get("raw", ""))
        note = str(item.get("note", ""))
        label = str(item.get("label", kind))
        parent = item.get("parent_residue") or ""
        mod = item.get("modification") or ""
        residue_like = kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa", "linker"}
        if residue_like:
            pos += 1
            position = pos
        else:
            position = None
        cls = {
            "sidechain_label_aa": "side_chain_modified_residue",
            "n_terminal": "n_terminal_modifier",
            "c_terminal_atom": "c_terminal_modifier",
        }.get(kind, kind)
        if kind == "chemical" and row_index == 0 and raw.upper() in {"PAL", "MYR", "STE", "LAU", "CHOL", "CHS", "GAL", "CAF", "NIC"}:
            cls = "n_terminal_modifier"
        warning = ""
        if kind == "chemical" and raw.upper() in {"PAL", "MYR", "STE", "LAU", "CHOL", "CHS", "GAL", "CAF", "NIC"} and pos > 0 and not parent:
            warning = f"{raw.upper()} is normally treated as an N-terminal modifier unless side-chain attachment is explicitly specified."
        if kind == "label" and not parent and pos > 0:
            warning = "Free internal label token is not a standard residue; confirm intended terminal or side-chain attachment chemistry."
        if parsed.get("warnings"):
            warning = warning or "See parse/export report for warning details."
        _display_map = {"PAL":"PAL", "MYR":"MYR", "GAL":"Gallic acid", "CAF":"Caffeic acid", "NIC":"Nicotinic acid", "NH2":"NH2", "FITC":"FITC", "FAM":"FAM", "TAMRA":"TAMRA"}
        token_display = _display_map.get(raw.upper(), raw)
        if parent and mod:
            token_display = f"{parent}({mod})"
        rows.append(PeptideToken(raw=raw, token=token_display, cls=cls, residue_name=(parent or raw)[:3].upper(), note=f"{label}; {note}".strip("; "), position=position, d_form=(kind == "d_std_aa"), warning=warning))
    return rows

def _path_needs_ascii_stage(path: Path) -> bool:
    """RDKit SDWriter can fail on some Windows/non-ASCII paths.

    Stage RDKit writes in an ASCII temp folder and then copy the outputs back.
    Python file copying normally handles the user's Unicode/Desktop path better
    than RDKit's C++ writer.
    """
    text = str(path)
    return any(ord(ch) > 127 for ch in text) or "#" in text


def _prepare_safe_output_dir(output_dir: str | Path, namespace: str = "pymol_structure_builder") -> tuple[Path, Path, bool]:
    requested = Path(output_dir).expanduser()
    requested.mkdir(parents=True, exist_ok=True)
    # Confirm normal Python write permission first.
    probe = requested / ".pepforge_write_probe.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        fallback = Path(tempfile.gettempdir()) / "Pepforge_Runtime" / namespace
        fallback.mkdir(parents=True, exist_ok=True)
        return requested, fallback, True
    if _path_needs_ascii_stage(requested):
        fallback = Path(tempfile.gettempdir()) / "Pepforge_Runtime" / namespace
        fallback.mkdir(parents=True, exist_ok=True)
        return requested, fallback, True
    return requested, requested, False


def _copy_outputs_to_requested(paths: dict[str, str], requested: Path, stage: Path) -> dict[str, str]:
    if requested.resolve() == stage.resolve():
        return paths
    requested.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for key, value in paths.items():
        src = Path(value)
        if src.exists() and stage in src.parents:
            dst = requested / src.name
            try:
                shutil.copy2(src, dst)
                out[key] = str(dst)
            except Exception:
                # Preserve the staged file if copying back fails.
                out[key] = str(src)
        else:
            out[key] = value
    return out



def export_modified_peptide_structure(sequence: str, output_dir: str | Path, name: str = "modified_peptide") -> dict[str, str]:
    """Export RDKit-backed SDF/PDB/JSON/report/PML plus compatibility CIF/CSV files.

    v4.1.0 functional fix:
    - writes RDKit outputs in an ASCII-safe staging directory when the selected
      Windows path contains Korean/non-ASCII characters or shell-sensitive
      characters such as '#';
    - copies finished SDF/PDB/PML/metadata files back to the requested folder;
    - returns the actual readable file paths.
    """
    import re
    requested_out, out, staged = _prepare_safe_output_dir(output_dir, "pymol_structure_builder")
    sequence_for_build = re.sub(r"([A-Za-z])\[([^\]]+)\]", r"\1(\2)", sequence or "")
    result = build_structure(sequence_for_build, out, name=name, optimize=True, num_confs=8)
    pml = make_pymol_pml(result.meta_path, prefer="sdf")

    meta_path = Path(result.meta_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Prepend Pepforge-readable REMARK block for PyMOL/users while keeping RDKit ATOM/HETATM content intact.
    pdb_path = Path(result.pdb_path)
    pdb_original = pdb_path.read_text(encoding="utf-8", errors="ignore")
    remark_lines = [
        "HEADER    PEPFORGE PYMOL-READABLE MODIFIED PEPTIDE MODEL",
        f"REMARK   Input sequence: {sequence}",
        "REMARK   This is a connected PyMOL visualization/screening model, not a fully parameterized all-atom structure.",
    ]
    for i, tok in enumerate(meta.get("tokens") or [], start=1):
        remark_lines.append(f"REMARK TOKEN {i:03d} {tok.get('raw','')} {tok.get('kind','')} {tok.get('note','')}")
    if not pdb_original.startswith("HEADER    PEPFORGE PYMOL-READABLE"):
        pdb_path.write_text("\n".join(remark_lines) + "\n" + pdb_original, encoding="utf-8")

    # Compatibility token map expected by Pepforge users.
    token_map = out / f"{Path(result.pdb_path).stem}_token_map.csv"
    with token_map.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["index", "token", "kind", "label", "parent_residue", "modification", "heavy_start_1based", "heavy_end_1based", "note"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        ranges = meta.get("atom_ranges") or []
        tokens = meta.get("tokens") or []
        for i, tok in enumerate(tokens, start=1):
            rng = ranges[i-1] if i-1 < len(ranges) else {}
            writer.writerow({
                "index": i,
                "token": tok.get("raw", ""),
                "kind": tok.get("kind", ""),
                "label": rng.get("label", ""),
                "parent_residue": tok.get("parent_residue", ""),
                "modification": tok.get("modification", ""),
                "heavy_start_1based": rng.get("heavy_start_1based", ""),
                "heavy_end_1based": rng.get("heavy_end_1based", ""),
                "note": tok.get("note", ""),
            })

    # Minimal CIF compatibility export. SDF/PDB are the primary PyMOL outputs.
    cif_path = out / f"{Path(result.pdb_path).stem}.cif"
    cif_path.write_text(
        "# Pepforge PyMOL Structure Tool v%s\n"
        "# Visualization/screening-grade connected model. Not force-field-parameterized all-atom MD input.\n"
        "data_%s\n"
        "_pepforge.input '%s'\n"
        "_pepforge.primary_sdf '%s'\n"
        "_pepforge.primary_pdb '%s'\n" % (STRUCTURE_TOOL_VERSION, Path(result.pdb_path).stem, sequence.replace("'", ""), Path(result.sdf_path).name, Path(result.pdb_path).name),
        encoding="utf-8",
    )

    paths = {
        "sdf": str(result.sdf_path),
        "pdb": str(result.pdb_path),
        "cif": str(cif_path),
        "json": str(result.meta_path),
        "report": str(result.report_path),
        "pml": str(pml),
        "token_map": str(token_map),
        "csv": str(token_map),
    }
    return _copy_outputs_to_requested(paths, requested_out, out)
