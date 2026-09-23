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


## Interaction distance / geometry criteria

Docking Workbench now uses the conservative PyMOL manual-screening profile supplied for this project as its specific-interaction review layer. The measurement point is interaction-specific rather than a generic residue-centroid distance.

| Interaction | Conservative criterion | Geometry / interpretation |
|---|---:|---|
| Hydrogen bond | donor heavy atom–acceptor heavy atom <= 3.5 A | D-H...A >=120 deg recommended when explicit H exists |
| Hydrophobic | nonpolar atom–nonpolar atom 3.3–5.0 A | no fixed angle; verify the contacting atoms are actually nonpolar |
| Salt bridge | opposite charged group/center <=4.0 A | no separate angle requirement |
| pi-pi | ring centroid <=5.0 A | plane 0–30 deg or 60–90 deg; offset <=2 A |
| Cation-pi | cation center–ring centroid <=5.0 A | cation must approach the ring face; offset <=2 A |
| van der Waals | near the sum of the two vdW radii | packing/contact descriptor, not a specific bond |
| Serious clash | vdW overlap >=0.4 A | structure warning, not a favorable interaction |
| Disulfide | Cys SG–SG ~2.0–2.1 A | covalent geometry/connectivity review remains required |
| Water bridge | 2.5–3.5 A on each water leg | explicit water plus H-bond geometry required |
| Metal coordination | metal–coordinating atom <=3.0 A | metal-specific coordination geometry required |
| Halogen bond | X–acceptor <=3.5 A | C-X...A about >=150 deg recommended |
| Aromatic-S | S–aromatic system <=5.0 A | secondary interaction; inspect ring placement |
| Weak C-H...O/N | C–O/N <=3.5 A screen | C-H...A >=120 deg recommended; secondary without explicit H |
| NH-pi | donor–aromatic system <=3.9 A screen | secondary; donor-H / aromatic-plane direction must be reviewed |

The Contacts page includes a dedicated **Specific interactions — conservative PyMOL criteria** table. A more specific interaction represents the same residue pair where appropriate (for example, salt bridge over duplicate H-bond character, or pi-pi over a generic hydrophobic contact), while clash remains an independent structure warning. Distance-only candidates remain explicitly labelled when the coordinate file does not contain enough geometry to confirm the interaction.
