# SPPS Reagent Database Schema Recommendation

Recommended future database split:

- AA_DB.csv
- MODIFIER_DB.csv
- COUPLING_REAGENT_DB.csv
- CATALYST_ADDITIVE_DB.csv
- BASE_DB.csv
- SOLVENT_DB.csv
- RESIN_DB.csv
- CLEAVAGE_DB.csv

Recommended fields:

name, display_name, class, state, MW, density, default_eq, default_count, unit, compatible_resin, compatible_phase, notes

State should be one of:

- solid
- liquid
- solution
- solvent

Solid reagents are reported in g/mg. Liquid reagents and solvents are reported in mL when density or volume-basis information is available.
