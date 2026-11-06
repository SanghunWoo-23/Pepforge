"""Run SPPS Planner database audit and write CSV output.

Usage from project root:
    python tools/audit_database.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "spps_planner_app"))

from spps_planner.database import audit_compound_database, load_compounds, load_reagent_library, DATA_DIR
from spps_planner.version import DATA_VERSION


def main() -> None:
    audit = audit_compound_database(load_compounds(), load_reagent_library())
    out = DATA_DIR / f"compound_db_audit_{DATA_VERSION}.csv"
    audit.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Wrote {out}")
    print(audit["level"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
