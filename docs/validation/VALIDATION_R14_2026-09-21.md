# Pepforge V4.0.0 R14 Validation — PSB PDB sequence/construct metadata

Date: 2026-09-21
Suite version: V4.0.0 fixed
Base: R13

## Implemented

- PSB residue-aware PDB now writes peptide `SEQRES` records on chain `P`.
- PSB PDB writes `REMARK 901 PEPFORGE_EXACT_SEQUENCE` with continuation support for long constructs.
- PSB PDB writes peptide-token and modifier-token REMARK metadata.
- Existing ATOM/HETATM residue-aware coordinate mapping is preserved.
- N-terminal/covalent chemistry that already has an explicit Pepforge graph remains coordinate-bearing (for example Ac/Boc/Fmoc; Pal/Myr/Ste/Lau/Gal/Caf/Nic; Biotin/FITC/FAM in supported attachment contexts; supported linkers; D residues; supported non-natural residues).
- Linkers/modifiers do not consume peptide residue numbering in `SEQRES`.
- Docking Workbench recovers peptide identity in this order: Pepforge exact-sequence REMARK -> SEQRES -> ATOM/HETATM residue extraction.
- Loading a Pepforge PSB peptide PDB into Docking Workbench exposes the recovered exact construct in the peptide sequence field.
- Ambiguous derivatives remain blocked from fabricated 3D generation; R14 does not add surrogate all-atom structures for unsupported chemistry.

## Validation

Focused new R14 regression: 5 passed.
Existing affected PSB/notation regression: 17 passed.
Existing UI/output + lineage regression: 16 passed.
Existing Docking regression: 18 passed.
Source integrity + release integrity: 5 passed.
Release verify matrix: 2 passed.
Release gate: 2 passed.
Compileall: PASS.

Additional coordinate round-trip smoke:
- 20 representative modified constructs: 20/20 passed.
- 47 currently explicit/buildable chemistry constructs generated as PDB and recovered exact notation: 47/47 passed.

Examples verified include:
- Ac-EEMQRR-NH2
- Pal-AEEA-dK-NH2
- Boc-GHK-NH2
- Fmoc-GHK-NH2
- Myr/Ste/Lau/Gal/Caf/Nic terminal acyl constructs
- Biotin/FITC/FAM + AEEA constructs
- supported linker constructs
- supported D/non-natural residue constructs
- K(Biotin), K(FITC), K(FAM) side-chain constructs

## Scientific boundary

PDB is a review/interoperability representation. SDF/JSON remain authoritative for exact modified-chemistry graph/connectivity. `SEQRES` intentionally describes peptide residue positions only. Exact Pepforge notation preserves chemistry that cannot be represented faithfully as ordinary amino-acid sequence. Recognized chemistry without a unique curated derivative/attachment graph is not assigned fabricated coordinates.
