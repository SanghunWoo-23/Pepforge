import argparse
from pathlib import Path
from spps_planner.engine import PlanInput, plan_summary, validate_plan
from spps_planner.export import export_csvs, export_excel
from spps_planner.version import VERSION_NAME


def _normalize_cli_resin(value: str) -> str:
    """Preserve the user-facing resin label while engine.resin_family() resolves behavior.

    Older CLI builds collapsed 2-CTC into CTC/Trityl, which made operator-facing
    material tables show a generic resin instead of the resin the user selected.
    """
    text = str(value or "").strip()
    return text or "Amide"


def _read_override_text(value: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return value


def main():
    ap = argparse.ArgumentParser(description=VERSION_NAME)
    ap.add_argument("--seq", "--sequence", dest="seq", default="Ac-EEMQRR-NH2", help="Peptide sequence, e.g. Ac-EEMQRR-NH2 or ghk-nh2")
    ap.add_argument("--resin", dest="resin", default="Amide", help="Resin/resin family. Accepts Amide, Rink Amide AM, CTC/Trityl, 2-CTC, Trityl.")
    ap.add_argument("--mmol", "--scale-mmol", dest="mmol", type=float, default=400)
    ap.add_argument("--loading", "--resin-loading-mmol-g", dest="loading", type=float, default=0.8)
    ap.add_argument("--coupling-eq", type=float, default=5.0)
    ap.add_argument("--ac-eq", type=float, default=3.0)
    ap.add_argument("--coupling-repeats", type=int, default=1)
    ap.add_argument("--modifier-repeats", type=int, default=1)
    ap.add_argument("--coupling-reagent", default="DIC")
    ap.add_argument("--catalyst", default="HOBt")
    ap.add_argument("--base", default="")
    ap.add_argument("--reaction-solvent", default="DMF")
    ap.add_argument("--tfa-factor", type=float, default=10.0)
    ap.add_argument("--cleavage-tfa-percent", type=float, default=95.0)
    ap.add_argument("--cleavage-tis-percent", type=float, default=2.5)
    ap.add_argument("--cleavage-water-percent", type=float, default=2.5)
    ap.add_argument("--cleavage-eq", type=float, default=0.0, help="Manual cleavage cocktail eq override; 0 = auto/user-rule")
    ap.add_argument("--cleavage-preset", default="AUTO", help="AUTO, DEFAULT_TFA_TIS_WATER, CYS_EDT, REAGENT_B/K/L/R/H/I, or custom components")
    ap.add_argument("--cleavage-components", default="", help="Custom cocktail components, e.g. TFA=95;TIS=2.5;Water=2.5;EDT=0")
    ap.add_argument("--cleavage-reserve-ml", type=float, default=0.0, help="Minimum total cocktail volume reserve; 0 = equivalent-based volume only")
    ap.add_argument("--loading-aa-eq", type=float, default=2.0)
    ap.add_argument("--loading-diea-eq", type=float, default=4.0)
    ap.add_argument("--no-auto-short-eq", action="store_true", help="Disable 1-5 mer = 2 eq rule")
    ap.add_argument("--overrides", default="", help="Inline override text or path to override txt/csv")
    ap.add_argument("--outdir", "--out", dest="outdir", default="outputs/run")
    args = ap.parse_args()
    inp = PlanInput(
        sequence=args.seq,
        resin=_normalize_cli_resin(args.resin),
        scale_mmol=args.mmol,
        resin_loading_mmol_g=args.loading,
        coupling_eq=args.coupling_eq,
        ac_eq=args.ac_eq,
        default_coupling_repeats=args.coupling_repeats,
        default_modifier_repeats=args.modifier_repeats,
        default_coupling_reagent=args.coupling_reagent,
        default_catalyst=args.catalyst,
        default_base=args.base,
        default_reaction_solvent=args.reaction_solvent,
        tfa_factor=args.tfa_factor,
        cleavage_tfa_percent=args.cleavage_tfa_percent,
        cleavage_tis_percent=args.cleavage_tis_percent,
        cleavage_water_percent=args.cleavage_water_percent,
        cleavage_eq_override=args.cleavage_eq,
        cleavage_preset=args.cleavage_preset,
        cleavage_components_text=args.cleavage_components,
        cleavage_reserve_mL=args.cleavage_reserve_ml,
        loading_aa_eq=args.loading_aa_eq,
        loading_diea_eq=args.loading_diea_eq,
        auto_short_peptide_eq=not args.no_auto_short_eq,
        step_overrides_text=_read_override_text(args.overrides),
    )
    outdir = Path(args.outdir)
    export_csvs(inp, outdir)
    export_excel(inp, outdir / "spps_plan.xlsx")
    print(VERSION_NAME)
    print(plan_summary(inp))
    warnings = validate_plan(inp)
    if not warnings.empty:
        print(warnings.to_string(index=False))
    print(f"Saved outputs to: {outdir}")


if __name__ == "__main__":
    main()
