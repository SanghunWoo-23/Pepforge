# Peptide Structure Builder (PSB) conformer engine — V4.0.0

PSB is a local **conformer generation and geometry-screening** engine. It is not AlphaFold, molecular dynamics, or an experimentally validated native-structure predictor.

## Current generation path

1. **Chemistry parsing**
   - The Pepforge token grammar is converted to an explicit molecular graph.
   - D/non-natural/linker/label chemistry is retained explicitly when supported; unsupported chemistry is rejected rather than silently canonicalized.

2. **Baseline conformer sampling**
   - RDKit ETKDGv3 generates multiple 3D coordinate candidates.
   - Baseline ETKDG conformers are optimized with MMFF94 when fully parameterized, otherwise UFF is used and the fallback is recorded.

3. **Sequence-evidence search plan**
   - Canonical-L sequence evidence is used only to prioritize which already-defined backbone families deserve search coverage.
   - Alpha, 3_10, beta-extended, PPII, turn/hairpin and coil alternatives remain distinguishable.
   - Evidence labels are not structure probabilities.

4. **Backbone search seeds**
   - Plain canonical-L peptides can receive explicit alpha, 3_10, beta-extended and PPII phi/psi search seeds.
   - D/non-natural/linker/side-chain-modified constructs do not inherit canonical-L torsions.
   - Two explicit noncanonical turn motifs have dedicated literature-guided local search seeds: `dP-G` (type II-prime candidate) and `Aib-G` (type I-prime candidate). For a beta-hairpin request, beta-extended flank search torsions are added around the explicit turn motif.
   - Explicit Aib can receive a dedicated 3_10 search seed without Aib->Ala conversion. Search seeds are hypotheses; family labels still require measured post-relaxation geometry.

5. **Seed geometry relaxation (V4.0.0)**
   - Stage 1: side chains are minimized while peptide N/CA/C/O backbone atoms are fixed.
   - Stage 2: the whole structure is minimized while each seeded phi/psi is kept inside a narrow torsion window.
   - This removes avoidable steric overlap without turning a seed into an unconstrained force-field minimum.

6. **Steric geometry audit (V4.0.0)**
   - Non-bonded heavy-atom pairs separated by more than two covalent bonds are screened against van-der-Waals radii.
   - Severe overlaps and a softer overlap count are reported per conformer.
   - The audit is a geometry-quality screen, not a free energy or experimental clash probability.

7. **Backbone-family interpretation**
   - Phi/psi basins and simple backbone O...N contact patterns are used to classify generated conformers.
   - Labels include alpha-like, 3_10-like, beta-extended, beta-hairpin-like, PPII, turn-rich and coil/mixed.

8. **Top-5 selection**
   - When PDE supplies a supported Preferred Structure, severe-clash-free conformers from that measured geometry family are selected first.
   - Within the requested family, family-specific backbone geometry is ranked before softer steric/evidence and same-molecule force-field energy terms.
   - Cross-family or RMSD diversity is **not** forced into Top-5; RMSD spread is retained as audit metadata only.
   - If too few requested-family conformers remain, clean fallbacks are labelled explicitly. Severe-clash structures are never added merely to fill five slots.
   - Force-field energy is used only within the same molecular graph and is not converted to population or binding probability.

9. **Canonical peptide visualization PDB (V4.0.0)**
   - Plain canonical-L peptides additionally receive a residue-aware, heavy-atom PDB view with chain/residue numbers and N/CA/C/O atom names.
   - The chemistry-faithful SDF/generic graph export remains available.
   - Modified/D/linker constructs are never relabeled as canonical residues just to obtain a prettier PDB.

## What PSB does not do

PSB does not run explicit-solvent MD, constant-pH simulation, AF3 inference, PEP-FOLD, REMD, or a learned native-state probability model. Environment metadata can guide interpretation and PDE design objectives, but it is not converted into an invented solvent free-energy correction.

For publication-grade structural claims, PSB conformers should be treated as starting/screening structures and validated with appropriate external structure prediction, MD/ensemble analysis, docking, CD/NMR, or other experiments as applicable.

## Preferred-structure limitations

- `BETA_HAIRPIN` and `TURN_RICH`: Pepforge does not invent a generic exact torsion template. Only explicit literature-supported `dP-G` / `Aib-G` motifs receive local turn-basin search seeds; family assignment still requires measured post-relaxation geometry and any shortage remains explicit fallback.
- `COILED_COIL`: PSB is monomeric. It can screen helical preorganization of one chain, not predict oligomeric coiled-coil assembly.
- `AMPHIPATHIC_ALPHA`: alpha-backbone geometry is screened in PSB; amphipathic organization remains sequence/context evidence rather than separate multimeric structural proof.
- Pro-rich `PPII_EXTENDED`: ring-constrained Pro torsions that RDKit cannot rotate no longer invalidate the entire PPII seed. Settable backbone torsions are applied and the relaxed conformer is accepted only if measured phi/psi geometry supports the family.
