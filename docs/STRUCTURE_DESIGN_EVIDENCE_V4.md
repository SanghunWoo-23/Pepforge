# Pepforge V4.0.0 — Structure Design Evidence & Generation Contract

## V4 scope

V4 generates and reviews **starting structures / conformer hypotheses**. It does not claim a native solution structure, folding probability, experimental validation, or production-MD result.

## Structure-generation routes

### Canonical-L linear peptides

For a plain canonical-L linear peptide, Pepforge uses its own explicit chemistry graph and supplements stochastic RDKit ETKDG sampling with deterministic backbone-basin search seeds. The explicit phi/psi construction concept is consistent with:

- Tien MZ, Sydykova DK, Meyer AG, Wilke CO. *PeptideBuilder: A simple Python library to generate model peptides*. PeerJ. 2013;1:e80. DOI: 10.7717/peerj.80.

Pepforge does **not** require or bundle the external PeptideBuilder Python package. It implements the search-seed concept internally so that the same chemistry graph, token mapping, Windows packaging, and downstream audits remain intact.

Representative search basins are alpha, 3-10, beta-extended, and PPII. They are starting hypotheses, not probabilities. After minimization Pepforge re-measures phi/psi geometry and stores a seed-fidelity audit rather than assuming the seed identity survived relaxation.

### D/non-natural/modified/linker constructs

Canonical-L phi/psi seeds are not silently transferred to D residues, non-natural residues, linkers, or side-chain-modified units. These constructs stay on the explicit chemistry-graph/RDKit route unless a specific supported motif has its own explicit search rule.

Every generated construct receives an adjacent-range covalent-connection audit. A disconnected or missing encoded linkage is a build failure rather than a display-only workaround.

## Context-aware sequence evidence

V4 keeps sequence evidence separate from measured/generated geometry.

- Helix: Pace-Scholtz intrinsic canonical-L propensity, N/C-cap context, helix dipole context, i,i+3 / i,i+4 charge-pair evidence.
- Pro/Gly: internal helix-breaker context is separated from terminal/cap-adjacent context; Gly runs are reported separately.
- Beta: alternating/odd-even face context and terminal negative-design descriptors are reported without calling a folded beta sheet.
- Charge: whole-sequence balance and local charge patches are reported separately.
- Aggregation/SPPS: hydrophobic/aromatic/NQ runs, V/I/T-rich difficult-sequence context, aspartimide motifs, and chemical liabilities remain separate evidence axes.

Key literature context includes Aurora & Rose (helix capping), Minor & Kim (beta-sheet context dependence), Chiti et al. (aggregation), Richardson & Richardson (beta-edge negative design), and the evidence registry distributed with Pepforge.

## Environment boundary

Aqueous hydrophobicity/amphipathicity descriptors are not silently reused as membrane partition free energies. pH, solvent/membrane context, ionic strength, termini, and modification state are provenance/interpretation fields unless the corresponding calculation explicitly uses them.

## V5 hand-off

Production MD, automatic DCD/XTC generation, MDTraj/MDAnalysis feature extraction, replicate comparison, clustering/medoids, force-field/water-model sensitivity, and enhanced sampling belong to V5. V4 may prepare hand-off material and import summary metadata, but it does not expose trajectory analysis.
