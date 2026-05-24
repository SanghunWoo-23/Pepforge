# SPPS Coupling Solution and bAla/gAla Update

This build treats each coupling step as a coupling solution/cocktail preparation: the unit (Fmoc-AA, D-AA, non-natural amino acid, modifier, or label), coupling reagent 1, coupling reagent 2/catalyst, and coupling base are prepared in the selected coupling solution solvent and then added to the resin. Individual reagent quantities remain separately tracked in the Material Usage table.

Loading steps also expose a unit dissolution solvent. For 2-CTC/trityl loading, the default is a DCM-rich 90% DCM / 10% DMF system, reflecting cases where the loading amino acid is dissolved with a small DMF fraction in DCM.

bAla and gAla are classified as amino-acid-like/non-natural residue units rather than linker-only tokens. Linker-only tokens remain blocked from N-terminal modifier placement.
