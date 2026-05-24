# SPPS Reagent, Solvent, Base, and Unit Library Update

This edition expands the SPPS Planner selectable libraries while preserving editable free-text input.

## Editable selection support

The SPPS editable table now supports dropdown-assisted editing for:

- Unit name: standard amino acids, D-amino acids, selected non-natural amino acids, labels, modifiers, linkers, and tags.
- Coupling reagent 1: main coupling or activating reagents such as DIC, HBTU, HATU, PyBOP, COMU, DCC, EDC, CDI, and related reagents.
- Coupling reagent 2 / catalyst: additives/catalysts such as HOBt, Oxyma, HOAt, DMAP, NHS, and Sulfo-NHS.
- Coupling base: DIEA/DIPEA, NMM, TEA, pyridine, collidine, lutidine, DBU, and related bases.
- Solvents and washes: DMF, NMP, DCM, MeOH, EtOH, i-PrOH, ACN, THF, DMSO, TFA, TIS, water, ether, MTBE, and mixed solvent labels.

All dropdown fields remain editable because laboratory protocols often use vendor-specific reagent forms or local naming conventions.

## Calculation policy

Solid reagents are calculated primarily as mass. Liquid reagents, bases, and solvents are calculated primarily as volume when density data are available. Unknown or manual entries remain editable and may require user verification.
