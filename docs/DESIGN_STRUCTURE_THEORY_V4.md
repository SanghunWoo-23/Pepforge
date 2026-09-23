# Pepforge V4.0.0 — Design / Structure Theory Contract

This document records the evidence and claim boundaries used by the V4.0.0 PDE/PSB theory-refined workflow. It is a software design contract, not a claim that sequence heuristics predict an experimental structure, affinity, or solution-state population.

## 1. Conformational Strategy

`Conformational Strategy` is an **optimizer policy** layered on top of the existing Design Objective. It does not assign a biological binding mechanism.

- `PREORGANIZED` — supported requested-structure evidence remains a standalone Pareto objective when the selected Design Objective permits structure optimization. Use when the design goal intentionally favors candidates already compatible with the requested basin.
- `ADAPTIVE` — requested-structure accessibility is blended with interaction evidence rather than kept as a standalone fold objective. This allows interaction-centered candidates that can access the requested basin without requiring a strong free-state fold bias.
- `FLEXIBLE` — only a weak requested-structure accessibility guard is retained in structure-aware modes. It is intended for designs where conformational flexibility is acceptable or desirable.
- `Interaction Only` remains special: the structure objective is removed from the NSGA-II objective set regardless of Conformational Strategy. Structure metadata may still be reported.

These labels must not be reported as proof of conformational selection, induced fit, coupled folding/binding, or free-state population.

## 2. Alpha / amphipathic alpha evidence

For canonical-L coverage, PDE keeps the Pace–Scholtz helix-propensity values as a raw descriptor and converts them only to a transparent internal ordinal preference; modified/D/non-natural residues are not silently assigned canonical-L values.

N-terminal context is treated separately. The Chakrabartty/Doig/Baldwin capping study found a strong residue-identity effect at the N-cap and a much smaller identity effect at the C-cap; N-terminal acetylation removes that residue-specific N-cap effect in their peptide system. Pepforge therefore records N-cap context and acetylation explicitly and does not apply a symmetrical C-cap identity score.

Amphipathic alpha design adds hydrophobic-moment/organization evidence to alpha compatibility. PSB still classifies the measured backbone as alpha-like; amphipathicity is sequence/context evidence rather than separate structural proof.

## 3. 3_10 helix and explicit Aib

3_10 classification is based on measured phi/psi compatibility plus i->i+3 backbone O...N geometry after relaxation. A 120-degree hydrophobic moment is not used as the primary 3_10 definition.

Explicit Aib can contribute an Aib-specific 3_10 search/evidence channel. Aib is retained as Aib and is never converted to Ala or assigned a canonical-L helix scale simply to obtain a score. Final selection still requires measured relaxed geometry.

## 4. Beta strand / beta hairpin

Intrinsic beta-compatible sequence evidence is kept separate from alternating hydrophobic/polar organization, because alternation is an amphipathic beta-face descriptor rather than a universal beta-strand propensity.

Hairpin design/analysis separates:

- turn-nucleation evidence,
- strand/register-compatible geometry,
- cross-strand aromatic/opposite-charge/cation-aromatic candidate evidence,
- exposed beta-edge negative-design evidence,
- and final measured post-relaxation geometry.

Exact turn-basin search seeds are used **only** for explicit literature-supported motifs currently implemented:

- `dP-G` — representative D-Pro-Gly type II-prime search basin,
- `Aib-G` — representative Aib-Gly type I-prime search basin.

For an explicit beta-hairpin request, flanking residues are seeded into beta-extended search arms around the supported turn motif to improve antiparallel-hairpin coverage. This is a search initialization, not a family assignment. A conformer is called `beta_hairpin_like` only when measured relaxed coordinates contain beta-turn C-alpha(i)-C-alpha(i+3) geometry (<7 A), at least one nonlocal backbone contact, and compatible beta/PPII backbone content. Unsupported motifs do not receive invented exact turn templates.

## 5. PPII

PPII evidence is not reduced to Pro fraction. Pepforge keeps a coarse, transparent residue/context descriptor in which Pro is strongly compatible and selected non-Pro residues can also support PPII-like conformations. Pro-aromatic adjacency is reported as a cis/trans-isomerization risk context in Pro-rich sequences rather than as an experimental probability.

PSB Pro-rich seeds tolerate ring-constrained torsions that RDKit cannot rotate: settable backbone torsions are applied, the structure is relaxed, and the final PPII family call is made from measured phi/psi geometry.

## 6. Turn-rich

Generic turn-rich sequences are sampled without an invented exact universal turn template. When an explicit supported `dP-G` or `Aib-G` motif is present, the same literature-guided local turn seeds may be searched. Final `turn_rich`/hairpin labels still come from measured coordinates. If the requested family is not sampled cleanly, fallback is explicit.

## 7. Coiled-coil

PDE reports heptad-register evidence including a/d hydrophobic-core organization, e/g charged-edge organization, Leu@d/Ile@a context and buried-polar-core warnings. These are sequence/design descriptors.

PSB is a **monomer** conformer generator. A `COILED_COIL` preference therefore screens helical preorganization of one chain only. It does not assign dimer/trimer/tetramer state or pairing specificity. A future multichain pairing workflow would require explicit partner sequence/geometry and a separate validation contract.

## 8. Hot Spot chemistry complementarity

`Hotspot Complementarity` is a coarse target-feature/peptide-feature evidence layer and is deliberately separate from geometric contact analysis.

- `OFF` — disabled.
- `REPORT_ONLY` — score/status exported but not used for selection.
- `EVIDENCE_AND_SELECTION` — the coarse complementarity evidence can contribute to the interaction evidence objective.

Current feature matching includes acidic/basic, hydrophobic, aromatic/cationic, and polar/H-bond-capable categories. It must not be reported as a contact map, docking score, binding free energy, affinity, or proof that two groups are geometrically paired.

The separately maintained PyMOL interaction-cutoff guides are **not hard-coded into this layer**. Geometry/contact classification should remain a distinct future Hot Spot/Docking analysis component with its own conservative/tool-compatible profiles.

## 9. Candidate traceability

The following theory fields are part of downstream design intent and must survive PDE export -> candidate manifest -> Workflow import -> PSB/SPPS -> Candidate Summary Report:

- `mode` / `pde_objective_mode`,
- `preferred_structure`,
- `structure_bias`,
- `environment`,
- `conformational_strategy`,
- `hotspot_complementarity_mode`.

Hotspot chemistry complementarity score/status remain sequence-context evidence. Missing Docking, trajectory, or experimental stages remain `not_available`; Pepforge does not fill them with inferred values.

## 10. References used for these rules

- Pace CN, Scholtz JM. *A helix propensity scale based on experimental studies of peptides and proteins.* Biophysical Journal (1998). PMID: 9649402.
- Chakrabartty A, Doig AJ, Baldwin RL. *Helix capping propensities in peptides parallel those in proteins.* PNAS (1993). PMID: 8248248.
- Brown AM, Zondlo NJ. *A propensity scale for type II polyproline helices (PPII): aromatic amino acids in proline-rich sequences strongly disfavor PPII due to proline cis-trans isomerization.* Biochemistry (2012). PMID: 22667692.
- Wilmot CM, Thornton JM. *Analysis and prediction of the different types of beta-turn in proteins.* J Mol Biol (1988). PMID: 3184187.
- Karle IL et al. Experimental D-Pro-Gly beta-hairpin examples include Boc-LVV-DPro-G-LVV-OMe. PMID: 7488115.
- Gellman/Waters design literature: *Rules for Antiparallel beta-Sheet Design: D-Pro-Gly Is Superior to L-Asn-Gly for beta-Hairpin Nucleation.* JACS. DOI: 10.1021/ja973704q.
- Aib-Gly type I-prime beta-turn nucleation study. PMID: 17427180.
- Mason JM, Arndt KM. Coiled-coil sequence specificity/oligomerization review. PMID: 17041258.

## 11. Global claim guard

PDE values are design-ranking evidence. PSB outputs are conformer/search hypotheses. Neither is an experimental structure, conformational population, affinity, activity, synthesis yield, pharmacokinetic property, or safety result. Unsupported chemistry remains unsupported/limited/parameterization-required rather than being silently canonicalized.
