from __future__ import annotations
from pathlib import Path
import argparse, csv, json, sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pepforge_structure_tool.pepforge_core import (
    VERSION, build_structure, build_batch, read_batch_csv, describe_parse,
    environment_report, supported_token_table, template_manifest, audit_template_files,
)
from pepforge_structure_tool.pymol_script import make_pymol_pml, make_batch_pml

parser = argparse.ArgumentParser(
    description=f"Pepforge PyMOL Structure Tool v{VERSION} - standalone builder that generates SDF/PDB/JSON/PML for PyMOL"
)
parser.add_argument("sequence", nargs="?", help="Modified peptide string, e.g. Ac-K(FITC)-LVFF-NH2")
parser.add_argument("--name", default="pepforge_model", help="Output object/file name")
parser.add_argument("--outdir", default="outputs", help="Output directory")
parser.add_argument("--parse-only", action="store_true", help="Only parse/classify tokens; do not generate 3D")
parser.add_argument("--batch-csv", help="CSV with name,sequence columns")
parser.add_argument("--no-opt", action="store_true", help="Skip MMFF/UFF optimization")
parser.add_argument("--confs", type=int, default=8, help="Number of RDKit conformers to try before selecting best energy conformer; default 8")
parser.add_argument("--seed", type=int, default=61453, help="RDKit ETKDG random seed; default 61453")
parser.add_argument("--max-iters", type=int, default=1000, help="MMFF/UFF optimization iterations; default 1000")
parser.add_argument("--keep-all-confs", action="store_true", help="Write all generated conformers into SDF; PDB still exports one representative conformer")
parser.add_argument("--env", action="store_true", help="Print runtime/RDKit status")
parser.add_argument("--tokens", nargs="?", const="all", help="Print supported tokens; optionally pass category")
parser.add_argument("--template-manifest", action="store_true", help="Print attach-point template manifest and exit")
parser.add_argument("--audit-templates", action="store_true", help="Check data/templates/*.sdf readability and template metadata")
parser.add_argument("--pml", action="store_true", default=True, help="Generate PyMOL .pml loader script; default on")
parser.add_argument("--prefer", choices=["sdf", "pdb"], default="sdf", help="Structure format to load in generated PML")
args = parser.parse_args()

if args.env:
    print(json.dumps(environment_report(), indent=2, ensure_ascii=False))
    raise SystemExit
if args.template_manifest:
    print(json.dumps(template_manifest(), indent=2, ensure_ascii=False))
    raise SystemExit
if args.audit_templates:
    print(json.dumps(audit_template_files(ROOT), indent=2, ensure_ascii=False))
    raise SystemExit
if args.tokens:
    table = supported_token_table()
    slim = {k: v for k, v in table.items() if k != "template_registry"}
    print(json.dumps(slim if args.tokens == "all" else {args.tokens: table.get(args.tokens, [])}, indent=2, ensure_ascii=False))
    raise SystemExit
if args.parse_only:
    print(json.dumps(describe_parse(args.sequence or ""), indent=2, ensure_ascii=False))
    raise SystemExit

out = Path(args.outdir)
out.mkdir(parents=True, exist_ok=True)

if args.batch_csv:
    items = read_batch_csv(args.batch_csv)
    rows = build_batch(items, out, optimize=not args.no_opt, num_confs=args.confs)
    meta_paths = [r["meta_path"] for r in rows if r.get("status") == "success" and r.get("meta_path")]
    for mp in meta_paths:
        make_pymol_pml(mp, prefer=args.prefer)
    if meta_paths:
        make_batch_pml(meta_paths, out / "load_all_in_pymol.pml", prefer=args.prefer)
    summary = out / "pepforge_batch_summary.csv"
    fields = sorted({k for r in rows for k in r.keys()})
    with summary.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"Batch complete: {sum(r.get('status')=='success' for r in rows)}/{len(rows)} success")
    print(f"Summary: {summary}")
    if meta_paths:
        print(f"PyMOL loader: {out / 'load_all_in_pymol.pml'}")
    raise SystemExit

if not args.sequence:
    parser.error("sequence is required unless --batch-csv, --env, --tokens, or --parse-only is used")

res = build_structure(args.sequence, out, args.name, optimize=not args.no_opt, seed=args.seed, max_iters=args.max_iters, num_confs=args.confs, keep_all_confs=args.keep_all_confs)
pml = make_pymol_pml(res.meta_path, prefer=args.prefer) if args.pml else None
print(f"SDF: {res.sdf_path}")
print(f"PDB: {res.pdb_path}")
print(f"JSON: {res.meta_path}")
print(f"Report: {res.report_path}")
if pml:
    print(f"PyMOL PML: {pml}")
print(f"Formula: {res.formula}; exact MW: {res.exact_mw:.4f}; heavy atoms: {res.heavy_atoms}")
if res.warnings:
    print("Warnings:")
    for w in res.warnings:
        print(" -", w)
