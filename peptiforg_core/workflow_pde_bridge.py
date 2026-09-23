from __future__ import annotations

import csv
import copy
import importlib
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PDE_DIR = ROOT / "apps" / "peptide_design_engine" / "Python"
if str(PDE_DIR) not in sys.path:
    sys.path.insert(0, str(PDE_DIR))

from pde_option_catalog import (
    WORKFLOW_PSB_SAFE_BASE_CHEM_TYPES,
    WORKFLOW_PSB_SAFE_LABEL_TYPES,
    WORKFLOW_PSB_SAFE_LINKER_TYPES,
    WORKFLOW_PSB_SAFE_NON_NAT_TYPES,
    WORKFLOW_PSB_SAFE_TAG_TYPES,
)

_ENGINE_LOCK = threading.Lock()
_ENGINE_MODULE = None
_ENGINE_BASE_CONFIG = None

QUALITY_OPTIONS = ["Balanced (recommended)", "Quick", "Thorough"]
QUALITY_PRESETS = {
    "Balanced (recommended)": {"POP": 100, "GEN": 8, "FINAL_TOPK": 10},
    "Quick": {"POP": 60, "GEN": 4, "FINAL_TOPK": 8},
    "Thorough": {"POP": 200, "GEN": 20, "FINAL_TOPK": 10},
}

STRUCTURE_OPTIONS = [
    "AUTO / BALANCED",
    "ALPHA_HELIX",
    "AMPHIPATHIC_ALPHA",
    "HELIX_310",
    "BETA_HAIRPIN",
    "BETA_STRAND",
    "PPII_EXTENDED",
    "TURN_RICH",
    "COILED_COIL",
]

WORKFLOW_BASE_CHEM_TYPES = WORKFLOW_PSB_SAFE_BASE_CHEM_TYPES.copy()
WORKFLOW_LINKER_TYPES = WORKFLOW_PSB_SAFE_LINKER_TYPES.copy()
WORKFLOW_TAG_TYPES = WORKFLOW_PSB_SAFE_TAG_TYPES.copy()
WORKFLOW_LABEL_TYPES = WORKFLOW_PSB_SAFE_LABEL_TYPES.copy()
WORKFLOW_NON_NAT_TYPES = WORKFLOW_PSB_SAFE_NON_NAT_TYPES.copy()
SELECTOR_PREFIX = ["Any", "Off"]


def _selector_to_library(value: str, library: list[str]) -> tuple[bool, list[str]]:
    choice = str(value or "Any").strip()
    if choice.lower() == "off":
        return False, list(library)
    if choice.lower() == "any" or not choice:
        return True, list(library)
    for item in library:
        if item.lower() == choice.lower():
            return True, [item]
    raise ValueError(f"Unsupported Workflow PDE chemistry choice: {value}")


def build_workflow_chemistry_overrides(
    *,
    use_d: bool = True,
    use_non_nat: bool = True,
    nterm_chem: str = "Any",
    linker: str = "Any",
    tag: str = "Any",
    label: str = "Any",
    cterm: str = "NH2",
) -> dict[str, Any]:
    use_base, base_types = _selector_to_library(nterm_chem, WORKFLOW_BASE_CHEM_TYPES)
    use_linker, linker_types = _selector_to_library(linker, WORKFLOW_LINKER_TYPES)
    use_tag, tag_types = _selector_to_library(tag, WORKFLOW_TAG_TYPES)
    use_label, label_types = _selector_to_library(label, WORKFLOW_LABEL_TYPES)
    cterm_choice = str(cterm or "NH2").strip().upper()
    if cterm_choice not in {"NH2", "COOH"}:
        raise ValueError(f"Unsupported C-terminal choice: {cterm}")
    overrides: dict[str, Any] = {
        "USE_D": bool(use_d),
        "USE_NON_NAT": bool(use_non_nat),
        "USE_BASE_CHEM": use_base,
        "BASE_CHEM_TYPES": base_types,
        "USE_LINKER": use_linker,
        "LINKER_TYPES": linker_types,
        "MAX_LINKERS": 1,
        "USE_TAG": use_tag,
        "TAG_TYPES": tag_types,
        "USE_LABEL": use_label,
        "LABEL_TYPES": label_types,
        "USE_CTERM_NH2": cterm_choice == "NH2",
        # These selectors restrict the allowed chemistry space. They do not
        # claim or force that an optional modifier must be inserted.
        "ENRICH_SELECTED_CHEMISTRY": False,
    }
    if use_linker and len(linker_types) == 1:
        overrides.update({"LINKER_MODE": "FIX", "FIX_LINKER_TYPE": linker_types[0]})
    else:
        overrides.update({"LINKER_MODE": "MIX", "FIX_LINKER_TYPE": linker_types[0] if linker_types else "PEG4"})
    return overrides


def normalize_structure_choice(choice: str) -> tuple[str, str]:
    value = str(choice or "AUTO / BALANCED").strip().upper()
    if value in {"", "AUTO", "AUTO / BALANCED", "NONE", "BALANCED"}:
        return "BALANCED", "NONE"
    allowed = set(STRUCTURE_OPTIONS[1:])
    if value not in allowed:
        raise ValueError(f"Unsupported preferred structure: {choice}")
    return "STRUCTURE_GUIDED", value


def build_workflow_pde_config(
    target_sequence: str,
    preferred_structure: str = "AUTO / BALANCED",
    quality_profile: str = "Balanced (recommended)",
    *,
    hotspot_profile_path: str | Path | None = None,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = "".join(str(target_sequence or "").split()).upper()
    if not target:
        raise ValueError("PDE target sequence is empty.")
    objective_mode, structure = normalize_structure_choice(preferred_structure)
    quality = str(quality_profile or "Balanced (recommended)").strip()
    if quality not in QUALITY_PRESETS:
        raise ValueError(f"Unsupported PDE quality profile: {quality_profile}")
    cfg: dict[str, Any] = {
        "TARGETS": [list(target)],
        "TARGET_MODE_LABEL": "SINGLE",
        "DESIGN_MODE": "SINGLE_TARGET",
        "PDE_OBJECTIVE_MODE": objective_mode,
        "PREFERRED_STRUCTURE": structure,
        "STRUCTURE_BIAS": "BALANCED",
        "STRUCTURE_ENVIRONMENT": "AQUEOUS",
        "CONFORMATIONAL_STRATEGY": "PREORGANIZED",
        "HOTSPOT_COMPLEMENTARITY_MODE": "EVIDENCE_AND_SELECTION",
        **QUALITY_PRESETS[quality],
        "SEED": 42,
        "AUTO_SEED_EACH_RUN": False,
        "USE_OPTIONAL_ML": False,
        # Workflow Mode presents candidates directly to PSB, so generation is
        # restricted to chemistry with an explicit PSB graph. The standalone
        # PDE keeps its broader exploration space.
        "NON_NAT_TYPES": WORKFLOW_NON_NAT_TYPES.copy(),
        "LINKER_TYPES": WORKFLOW_LINKER_TYPES.copy(),
        "USE_AA_LINKER_LIBRARY": False,
        "MAX_LINKERS": 1,
        "TAG_TYPES": WORKFLOW_TAG_TYPES.copy(),
        "BASE_CHEM_TYPES": WORKFLOW_BASE_CHEM_TYPES.copy(),
        "LABEL_TYPES": WORKFLOW_LABEL_TYPES.copy(),
        "ALLOW_MULTIPLE_NTERM_MODIFIERS": False,
        "DISALLOW_NTERM_LINKER": True,
        "PREPARE_PSEUDODOCKING_COLAB": False,
        "DOCKING_ENGINE": "NONE",
        "USE_REAL_DOCKING": False,
        "USE_AF": False,
        "AUTO_HOTSPOT": False,
    }
    if hotspot_profile_path:
        profile = Path(hotspot_profile_path)
        if profile.exists():
            cfg["HOTSPOT_CHEMISTRY_PROFILE_PATH"] = str(profile)
    if config_overrides:
        cfg.update(dict(config_overrides))
    return cfg


def _ensure_engine_loaded():
    global _ENGINE_MODULE, _ENGINE_BASE_CONFIG
    if _ENGINE_MODULE is None:
        pde_path = str(PDE_DIR)
        if pde_path not in sys.path:
            sys.path.insert(0, pde_path)
        _ENGINE_MODULE = importlib.import_module("peptide_engine")
        _ENGINE_BASE_CONFIG = copy.deepcopy(dict(_ENGINE_MODULE.CONFIG))
    return _ENGINE_MODULE


def _load_engine_clean():
    """Reuse the imported engine but reset its mutable CONFIG before each run."""
    module = _ensure_engine_loaded()
    base = copy.deepcopy(dict(_ENGINE_BASE_CONFIG or {}))
    module.CONFIG.clear()
    module.CONFIG.update(base)
    module.normalize_length_config()
    module.sync_custom_aa_linkers()
    return module


def warm_pde_engine() -> None:
    """Pre-import the PDE engine in a background thread to reduce first-run latency."""
    with _ENGINE_LOCK:
        _ensure_engine_loaded()


def _read_top_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _psb_graph_buildability(sequence: str) -> tuple[bool, str]:
    try:
        from pepforge_structure_tool.pepforge_core import expand_and_tokenize, tokens_to_smiles
        raw = expand_and_tokenize(str(sequence or ""))
        tokens_to_smiles(raw)
        return True, "explicit PSB chemistry graph available"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _workflow_compatible_candidates(rows: list[dict[str, Any]], limit: int, output_dir: Path) -> tuple[list[dict[str, Any]], str]:
    compatible: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        seq = str(row.get("sequence", "")).strip()
        if not seq or seq in seen:
            continue
        seen.add(seq)
        ok, reason = _psb_graph_buildability(seq)
        audit_rows.append({
            "rank": row.get("rank", ""),
            "candidate_id": row.get("candidate_id", ""),
            "sequence": seq,
            "psb_graph_buildable": bool(ok),
            "reason": reason,
        })
        if ok and len(compatible) < max(1, int(limit)):
            compatible.append(dict(row))
        if len(compatible) >= max(1, int(limit)):
            break
    audit_path = output_dir / "workflow_pde_buildability_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "candidate_id", "sequence", "psb_graph_buildable", "reason"])
        writer.writeheader()
        writer.writerows(audit_rows)
    return compatible, str(audit_path)


def run_pde_for_workflow(
    target_sequence: str,
    preferred_structure: str,
    output_dir: str | Path,
    *,
    quality_profile: str = "Balanced (recommended)",
    hotspot_profile_path: str | Path | None = None,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the real PDE backend for Workflow Mode without opening a second GUI."""
    cfg = build_workflow_pde_config(
        target_sequence,
        preferred_structure,
        quality_profile,
        hotspot_profile_path=hotspot_profile_path,
        config_overrides=config_overrides,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with _ENGINE_LOCK:
        eng = _load_engine_clean()
        rows, progress, paths = eng.run(cfg, verbose=False, outdir=str(out))
    top_csv = paths.get("top_csv")
    ranked_top = _read_top_rows(top_csv) if top_csv and Path(top_csv).exists() else list(rows)[: int(cfg.get("FINAL_TOPK", 10))]
    # Workflow Mode only exposes candidates whose explicit chemistry graph can
    # be consumed by PSB. The original PDE outputs remain untouched/auditable.
    scan_rows = list(ranked_top)
    top_sequences = {str(row.get("sequence", "")) for row in scan_rows}
    scan_rows.extend(row for row in list(rows) if str(row.get("sequence", "")) not in top_sequences)
    compatible_rows, audit_path = _workflow_compatible_candidates(scan_rows, int(cfg.get("FINAL_TOPK", 10)), out)
    if not compatible_rows:
        raise RuntimeError(
            "PDE completed, but no candidate had an explicit PSB-buildable chemistry graph. "
            f"See buildability audit: {audit_path}"
        )
    compatible_csv = out / "results_workflow_compatible.csv"
    fieldnames = list(compatible_rows[0].keys())
    with compatible_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(compatible_rows)
    paths["workflow_compatible_csv"] = str(compatible_csv)
    paths["workflow_buildability_audit_csv"] = audit_path
    return {
        "config": cfg,
        "rows": list(rows),
        "top_rows": compatible_rows,
        "progress": progress,
        "paths": paths,
    }


__all__ = [
    "QUALITY_OPTIONS",
    "QUALITY_PRESETS",
    "STRUCTURE_OPTIONS",
    "WORKFLOW_BASE_CHEM_TYPES",
    "WORKFLOW_LINKER_TYPES",
    "WORKFLOW_TAG_TYPES",
    "WORKFLOW_LABEL_TYPES",
    "WORKFLOW_NON_NAT_TYPES",
    "build_workflow_chemistry_overrides",
    "warm_pde_engine",
    "normalize_structure_choice",
    "build_workflow_pde_config",
    "run_pde_for_workflow",
]
