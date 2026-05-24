#!/usr/bin/env python3
"""Simple conservation from aligned FASTA. Score = frequency of consensus residue at each non-gap query position."""
from pathlib import Path
import argparse
import pandas as pd
from collections import Counter


def read_fasta(path):
    records = []
    name, lines = None, []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith(">"):
            if name: records.append((name, "".join(lines)))
            name, lines = line[1:].strip(), []
        else:
            lines.append(line)
    if name: records.append((name, "".join(lines)))
    return records

p = argparse.ArgumentParser()
p.add_argument("--msa", required=True, help="Aligned FASTA; first record is query")
p.add_argument("--record-name", required=True)
p.add_argument("--output", default="conservation_features.csv")
args = p.parse_args()
records = read_fasta(args.msa)
if not records: raise SystemExit("Empty MSA")
query = records[0][1]
seqs = [s for _, s in records]
pos = 0
rows = []
for col_idx, qaa in enumerate(query):
    col = [s[col_idx] for s in seqs if col_idx < len(s) and s[col_idx] != "-"]
    if qaa == "-":
        continue
    pos += 1
    if not col:
        score = 0.0
    else:
        score = Counter(col).most_common(1)[0][1] / len(col)
    rows.append({"record_name": args.record_name, "position": pos, "conservation_score": score})
pd.DataFrame(rows).to_csv(args.output, index=False)
print("Wrote", args.output)
