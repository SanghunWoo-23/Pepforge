# Pepforge V4.0.0 Modified-Peptide Support Matrix

Pepforge does not use a single "supported / unsupported" flag for modified
peptides. A token can be recognized by one stage while requiring explicit
parameterization or review in another stage.

The stage matrix separates:

- **PDE** — whether structure/design evidence exists for the token;
- **PSB topology** — whether an explicit chemical graph/template can be built;
- **PSB local MM** — whether local MMFF/UFF cleanup is usable as a geometry step;
- **SPPS** — whether reagent/protection/workflow information is available;
- **Docking export** — whether explicit coordinates can be handed to a docking workflow;
- **MD** — whether a standard force-field route is plausible or explicit parameterization is required.

Important boundaries:

- D-amino acids are not silently converted to L-amino acids for canonical-L
  propensity claims.
- Aib and other non-natural residues do not inherit canonical values merely
  because a rough analogue exists.
- A buildable RDKit graph is not proof that a production MD force field is valid.
- A recognized linker/label is not automatically parameterized for docking/MD.
- Terminal modifications and protonation must be reviewed explicitly.

Exports:

- `modified_peptide_support_matrix.json`
- `modified_peptide_support_matrix.csv`

The same matrix is embedded in the candidate Summary Report and the external MD
preparation protocol when available.

## PSB PDB sequence and construct metadata (R14 refinement)

PSB PDB exports now preserve two complementary layers of identity:

- `SEQRES` on chain `P` lists peptide residue positions that can be represented as PDB residue names.
- `REMARK 901 PEPFORGE_EXACT_SEQUENCE` preserves the complete Pepforge construct notation, including terminal modifiers, linkers, labels, D-residues, non-natural residues, and C-terminal state.
- `REMARK 902 PEPFORGE_PEPTIDE_TOKENS` records residue-position tokens.
- `REMARK 903 PEPFORGE_MODIFIER_TOKENS` records non-residue chemistry tokens.
- ATOM/HETATM records retain the existing residue-aware coordinate representation: peptide residue positions use chain `P`; separable terminal/linker/modifier chemistry uses chain `X` where appropriate.

Docking Workbench reads Pepforge exact-construct REMARK metadata first, then `SEQRES`, then ATOM/HETATM residue identity. This allows a PSB-generated PDB such as `Ac-EEMQRR-NH2` or `Pal-AEEA-dK-NH2` to carry its construct identity into Docking Workbench without requiring manual re-entry of the sequence.

This does not expand the chemistry model by inventing derivatives. Tokens with an explicit curated graph continue to receive coordinates. Recognized but chemically ambiguous labels/modifiers continue to require an explicit derivative/attachment rule and are not assigned fabricated all-atom structures.
