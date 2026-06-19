# Docking and Molecular Dynamics Workbench Guide

## Purpose

This module helps prioritize peptide candidates after sequence design and SPPS feasibility review. It is designed to answer practical screening questions:

- Does the peptide input look valid?
- Is a target structure or sequence available?
- Are contact regions detected?
- Is the candidate stable enough for further validation?
- Which tokens require external all-atom parameters?

## Simplified tabs

1. **Input**: checks target/peptide inputs and token compatibility.
2. **Results**: summarizes docking score, contact quality, clash risk, and interpretation.
3. **Contacts**: shows residue and atom contacts.
4. **Molecular Dynamics**: shows embedded MD screening outputs such as RMSD/contact trends.
5. **Export / Import**: saves the analysis package or reloads previous output folders.

## Token handling

Pepforge accepts peptide chemistry tokens such as D-form residues, non-natural amino acids, linkers, labels, and chemical caps. For screening, unsupported all-atom details are approximated. For external validation, the all-atom validation package reports which tokens need parameter review.

## Interpretation

The workbench should be used for candidate triage. A good screening result means the peptide may be worth further review. It does not prove binding experimentally.

## External validation

Use Export to create an all-atom validation package. Run external MD or structure validation in a dedicated environment, then import the output files back into Pepforge when needed.


## Affinity report units

The Docking Workbench reports generally interpretable binding quantities:

| Metric | Unit | Meaning |
|---|---:|---|
| estimated_ΔG | kcal/mol | Estimated binding free energy; more negative is stronger. |
| estimated_Kd | mM, uM, nM, pM, or M | Dissociation constant derived from ΔG using Kd = exp(ΔG / RT) at 298.15 K. Only one representative unit is shown. |
| interface_residue_contacts | count | Number of residue-level target-peptide contacts. |
| charged_contacts | count | Acidic/basic contact count. |
| apolar_contacts | count | Hydrophobic plus aromatic contact count. |
| steric_clashes | count | Steric clash count; lower is better. |
| minimum_distance | Angstrom | Closest target-peptide distance in the selected pose. |

These values are intended for candidate screening and ranking. Experimental Kd, server-side affinity prediction, or external all-atom MD should be used for final quantitative claims.


## Affinity notation note

Docking Workbench reports **estimated_ΔG** in **kcal/mol** and **estimated_Kd** in **one representative concentration unit**. Kd is converted from ΔG using `Kd = exp(ΔG / RT)` at 298.15 K. These values are calibrated contact-based screening estimates for relative candidate ranking and are kept in a practical protein-peptide affinity range. They are not measured binding constants and should be validated externally before quantitative claims.


## Interaction distance criteria

Pepforge reports explicit distance criteria in the Affinity report so the docking result is easier to interpret. Hydrogen-bond contacts use a donor-acceptor heavy-atom proxy cutoff of **3.9 Angstrom** because many imported PDB/mmCIF files do not include explicit hydrogen atoms or reliable bond-angle information. Hydrophobic contacts use a **5.0 Angstrom** contact cutoff for hydrophobic residue/atom pairs. These cutoffs are intended for screening and interface triage; final quantitative claims should still be checked with external all-atom MD or experimental binding data.
