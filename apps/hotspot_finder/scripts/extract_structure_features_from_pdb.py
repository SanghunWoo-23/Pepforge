#!/usr/bin/env python3
"""Lightweight PDB feature extractor: pLDDT/B-factor and CA contact count proxy. Not a full SASA calculator."""
from pathlib import Path
import argparse, math
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--pdb", required=True)
p.add_argument("--record-name", required=True)
p.add_argument("--chain", default=None)
p.add_argument("--cutoff", type=float, default=10.0)
p.add_argument("--output", default="structure_features.csv")
args = p.parse_args()
cas = []
for line in Path(args.pdb).read_text(errors="ignore").splitlines():
    if not line.startswith("ATOM") or line[12:16].strip() != "CA":
        continue
    chain = line[21].strip()
    if args.chain and chain != args.chain:
        continue
    resi = int(line[22:26])
    x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
    b = float(line[60:66]) if len(line) >= 66 else 0.0
    cas.append((resi, x, y, z, b))
rows = []
for i, (resi, x, y, z, b) in enumerate(cas):
    contacts = 0
    for j, (_, x2, y2, z2, _) in enumerate(cas):
        if i == j: continue
        d = math.sqrt((x-x2)**2 + (y-y2)**2 + (z-z2)**2)
        if d <= args.cutoff: contacts += 1
    # crude inverse contact exposure proxy
    exposure = 1.0 / (1.0 + contacts/10.0)
    rows.append({"record_name": args.record_name, "position": resi, "solvent_accessibility": exposure, "contact_number": contacts, "pLDDT": b})
pd.DataFrame(rows).to_csv(args.output, index=False)
print("Wrote", args.output)
