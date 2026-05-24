# Sequence Hotspot Finder v1.1 Full-Data Practical Edition

This version expands the v1.0 stable package with a larger practical token database and supervised-score support.

## What is fully included

- GitHub + Colab clone/import workflow
- Python package engine
- Local CLI
- Modular parser/scoring/ESM/validation/io code
- Expanded `token_db.csv`
- Expanded `sidechain_mod_db.csv`
- Natural AA, D-AA, common non-natural AA, linkers, terminal modifications, labels
- Side-chain modification effects for K[Biotin]-style syntax
- Long sequence window mode
- Domain-aware segmentation support
- Structure/conservation/supervised external feature merge
- ESM-2 embedding, masked marginal, mutation sensitivity
- Output reproducibility package
- Example inputs and templates
- Scripts for conservation and supervised score workflows
- Tests for parser, validation, and no-ESM execution

## Token counts

```text
C_terminal_modification     8
D_amino_acid               20
N_terminal_modification    23
label                      15
linker                     25
natural_L_amino_acid       20
non_natural_amino_acid     66
sidechain_modification      37
```

## What cannot be bundled directly

The package does not embed global external databases such as all AlphaFold structures, all Pfam/InterPro domain annotations, all BLAST/MMseqs2 homologs, all DMS datasets, or all alanine scanning datasets. Those are too large, change over time, or have separate licensing/use constraints.

Instead, this package includes the code, templates, merge points, and example workflows needed to bring those data in as CSVs.
