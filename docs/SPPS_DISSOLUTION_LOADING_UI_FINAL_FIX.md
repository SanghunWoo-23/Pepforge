# SPPS Dissolution and Loading-Solution Logic

This update makes dissolution/solution preparation explicit in the SPPS Planner.

## Principle

In practical SPPS planning, solid amino acids, solid additives, solid coupling reagents, solid labels, and solid modifiers are generally prepared as solutions before addition to the resin. This includes the loading step: the loading amino acid is also represented with a loading-dissolution solvent and preparation volume.

## Added editable columns

- Unit dissolve solvent
- Unit dissolve volume(mL)
- Coupling reagent 1 dissolve solvent
- Coupling reagent 1 dissolve volume(mL)
- Coupling reagent 2 / catalyst dissolve solvent
- Coupling reagent 2 / catalyst dissolve volume(mL)
- Coupling base solvent
- Coupling base volume(mL)

## Default resin behavior

- 2-CTC / Trityl resin: loading-dissolution solvent defaults to `90% DCM / 10% DMF`.
- Amide / Rink / Wang resin: loading-dissolution solvent defaults to `DMF`.

All fields remain editable by the user.
