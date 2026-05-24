import argparse
from pathlib import Path
from spps_planner.engine import PlanInput, plan_summary
from spps_planner.export import export_csvs, export_excel


def main():
    ap = argparse.ArgumentParser(description="SPPS Python Planner")
    ap.add_argument("--seq", default="Ac-EEMQRR-NH2")
    ap.add_argument("--resin", default="Amide", choices=["Amide", "CTC/Trityl"])
    ap.add_argument("--mmol", type=float, default=400)
    ap.add_argument("--loading", type=float, default=0.8)
    ap.add_argument("--outdir", default="outputs/run")
    args = ap.parse_args()
    inp = PlanInput(sequence=args.seq, resin=args.resin, scale_mmol=args.mmol, resin_loading_mmol_g=args.loading)
    outdir = Path(args.outdir)
    export_csvs(inp, outdir)
    export_excel(inp, outdir / "spps_plan.xlsx")
    print(plan_summary(inp))
    print(f"Saved outputs to: {outdir}")

if __name__ == "__main__":
    main()
