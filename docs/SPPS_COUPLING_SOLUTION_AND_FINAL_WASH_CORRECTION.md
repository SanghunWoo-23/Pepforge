# SPPS Coupling Solution and Final Wash Correction

This edition corrects the SPPS Planner coupling-preparation model.

## Coupling solution model

For ordinary SPPS coupling, the amino acid or modifier, coupling reagent 1, coupling reagent 2/catalyst/additive, and coupling base are treated as components of one coupling solution/cocktail. The editable table therefore uses a single `Coupling solution solvent` and a single `Coupling solution volume(mL)` for each reaction row.

The planner no longer exposes separate `Unit dissolve solvent`, `Coupling reagent 1 dissolve solvent`, `Coupling reagent 2 dissolve solvent`, or `Base solvent` columns. Individual reagent amounts are still calculated and listed separately in Material Usage, but the preparation solvent is represented as one coupling solution.

## Loading solution model

Loading is treated as a dedicated step distinct from ordinary coupling. For 2-CTC/trityl loading, the default loading solution solvent is DCM-rich, with `90% DCM / 10% DMF` available as a practical default. For amide/Rink/Wang workflows, the default solution solvent is DMF-family.

## Final wash model

The final Fmoc-amino-acid coupling workflow is:

1. pre-coupling deprotection
2. DMF wash x6
3. last Fmoc-AA coupling
4. DMF wash x2
5. final deprotection
6. final wash: DMF x3, DCM x3, optional MeOH x3

After the final deprotection, the planner does not add another DMF x6 wash. The final wash is DMF x3 and DCM x3 by default.

For final Ac/chemical/label/modifier steps, no post-coupling Fmoc deprotection is generated. The final wash remains DMF x3, DCM x3, optional MeOH x3.
