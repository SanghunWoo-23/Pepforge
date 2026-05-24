#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd
from sequence_hotspot_finder.io_utils import read_fasta_or_sequence

p = argparse.ArgumentParser(description="Create blank conservation CSV template from FASTA/input.")
p.add_argument("--input", required=True)
p.add_argument("--output", default="conservation_template.csv")
args = p.parse_args()
records = read_fasta_or_sequence(Path(args.input).read_text(encoding="utf-8"))
rows = []
for name, seq in records.items():
    clean = seq.replace("-", "")
    for i in range(1, len(clean)+1):
        rows.append({"record_name": name, "position": i, "conservation_score": ""})
pd.DataFrame(rows).to_csv(args.output, index=False)
print("Wrote", args.output)
