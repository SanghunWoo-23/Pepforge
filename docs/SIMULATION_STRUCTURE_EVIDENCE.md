# Pepforge V4.0.0 — Structure & Simulation Evidence Contract

Pepforge V4 separates **structure generation**, **static structure analysis**, and **external simulation protocol planning**. PSB constrained molecular mechanics is not molecular dynamics. V4 does not expose production MD or trajectory analysis; those functions are reserved for the V5 simulation workflow.

## Implemented evidence directions

1. **Force-field sensitivity rather than a universal best force field.** Singh, Martínez-Noa & Perez, *J. Phys. Chem. B* (2026), DOI 10.1021/acs.jpcb.6c01176, benchmarked 11 force fields across 12 peptide systems using both folded and extended starts and found no single model optimal across all peptide classes. Pepforge therefore exports a sensitivity set and explicit initial-state challenge instead of a universal winner.
2. **Cyclic peptides use a separate sensitivity profile.** *J. Phys. Chem. B* (2024), DOI 10.1021/acs.jpcb.4c00157, compared seven force-field/solvent combinations against solution NMR for 12 cyclic peptides; RSFF2/RSFF2C/Amber14SB + TIP3P performed best in that benchmark. Pepforge reports those as cyclic-peptide sensitivity candidates, not guaranteed best models.
3. **Enhanced sampling is an escalation, not automatic proof.** Streit et al., *Nature Communications* (2026), DOI corresponding to article s41467-026-73067-3, showed OPES multithermal sampling can broaden atomistic exploration of disordered peptides/proteins. Pepforge lists OPES multiT as an optional external escalation after independent unbiased replicates.
4. **Independent structure cross-checks remain external.** Badaczewska-Dawid et al., *Briefings in Bioinformatics* (2024), CABS-flex peptide benchmark, evaluated 159 linear/cyclic peptides. Pepforge can compare imported independent PDB models but does not claim it ran CABS-flex/PEP-FOLD/AF3 unless those tools were actually run outside Pepforge.
5. **AF-family predictions are not ground truth.** Guan et al., *Protein Science* (2025), DOI 10.1002/pro.70331, reported training-set/interface bias in protein–peptide docking predictions. Pepforge structure-consensus therefore treats AF3 and related models as independent diagnostics only.
6. **Membrane-interface descriptors remain thermodynamic descriptors.** Wimley & White, *Nature Structural Biology* (1996), DOI 10.1038/nsb1096-842. PDE stores the whole-residue water-to-interface transfer free-energy sum for canonical residues and never converts it into a permeability probability.

## Analysis contract

V4 analyzes static PDB/SDF structures and compares compatible PDB models. It may import external MD **summary metadata** as provenance/supporting evidence, but it does not read XTC/DCD/TRR trajectories or calculate trajectory populations.

V5 is the planned home for production MD, automatic trajectory generation, MDTraj/MDAnalysis feature extraction, replicate comparison, clustering/medoids, and force-field/water-model sensitivity. Nominal simulation duration alone must never be converted into a convergence grade.
