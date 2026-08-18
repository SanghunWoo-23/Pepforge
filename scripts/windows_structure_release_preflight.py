from __future__ import annotations

"""Windows/RDKit/PyMOL release preflight for Pepforge Structure Builder.

Run from an isolated build environment before promoting a candidate. The script
writes machine-readable evidence and exits non-zero when a required check fails.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(name: str, passed: bool, detail: str, required: bool = True) -> dict:
    return {"check": name, "status": "passed" if passed else ("failed" if required else "warning"), "required": required, "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--require-windows", action="store_true")
    parser.add_argument("--require-pymol", action="store_true")
    args = parser.parse_args()
    out = Path(args.output_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    rows = []
    is_windows = os.name == "nt"
    rows.append(check("windows_host", is_windows, f"os.name={os.name}", args.require_windows))
    rdkit_available = importlib.util.find_spec("rdkit") is not None
    rows.append(check("rdkit_import", rdkit_available, "RDKit import available" if rdkit_available else "RDKit not installed"))
    pymol_path = shutil.which("pymol") or shutil.which("pymol.exe")
    rows.append(check("pymol_executable", bool(pymol_path), pymol_path or "PyMOL not found on PATH", args.require_pymol))
    for rel in ("installer/Pepforge.spec", "installer/Pepforge_Setup.iss", "assets/Pepforge_Icon.ico"):
        path = ROOT / rel
        rows.append(check(f"resource_{rel.replace('/', '_')}", path.is_file(), str(path)))

    if rdkit_available:
        try:
            from peptiforg_core.pymol_structure_builder import export_modified_peptide_structure
            with tempfile.TemporaryDirectory(prefix="pepforge_preflight_") as tmp:
                paths = export_modified_peptide_structure(
                    "Ac-EEMQRR-NH2", tmp, "Ac_EEMQRR_NH2",
                    environment_conditions={"pH": 7.4, "temperature_C": 37.0, "ionic_strength_mM": 150.0, "environment": "Aqueous buffer"},
                )
                required = ["sdf", "pdb", "json", "report", "top5_conformers_sdf", "top5_conformers_csv", "top5_compare_pml"]
                missing = [key for key in required if not Path(paths.get(key, "")).is_file()]
                rows.append(check("reference_structure_outputs", not missing, "missing=" + repr(missing)))
                if not missing:
                    meta = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
                    top = (meta.get("conformation_analysis") or {}).get("top_conformers") or []
                    rows.append(check("top5_rank_contract", len(top) == 5 and [r.get("rank") for r in top] == [1, 2, 3, 4, 5], f"count={len(top)}"))
                    rows.append(check("condition_record_contract", (meta.get("environment_conditions") or {}).get("pH") == 7.4, repr(meta.get("environment_conditions"))))
        except Exception as exc:
            rows.append(check("reference_structure_generation", False, f"{type(exc).__name__}: {exc}"))

    failed = [row for row in rows if row["status"] == "failed"]
    payload = {"status": "failed" if failed else "passed", "passed": sum(r["status"] == "passed" for r in rows), "failed": len(failed), "warnings": sum(r["status"] == "warning" for r in rows), "results": rows}
    (out / "windows_structure_preflight.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
