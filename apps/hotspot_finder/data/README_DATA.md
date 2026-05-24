# Data Pack

This directory contains the default data tables used by Sequence Hotspot Finder.

## Included tables

- `token_db.csv`: natural amino acids, D-form amino acids, non-natural amino acids, linkers, terminal modifications, and labels.
- `sidechain_mod_db.csv`: side-chain modification effects used for K[Biotin]-style annotations.
- `aa_property_reference.csv`: reference copy of canonical amino acid properties used by the default token DB.
- `default_config.json`: default runtime configuration.

## Current token counts

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

## Important note

The values in these tables are practical engineering approximations for sequence-only prioritization. They are not a substitute for measured physical constants, experimental binding data, or structure-resolved energetics.

You can edit these CSV files in GitHub or directly inside the Colab UI.
