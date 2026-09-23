# PSB Preferred Structure Probe — Design/Structure Theory Refined

This probe records generated/relaxed PSB search outcomes for representative requested-family cases after the 2026-09-02 theory refinement. It is a deterministic regression/sanity probe of the current search/ranking path, not a native-structure benchmark, equilibrium-population estimate, or experimental validation.

| Preferred | Sequence | Match | Fallback | Severe clash selected | Rank-1 family | Note |
|---|---|---:|---:|---:|---|---|
| ALPHA_HELIX | `VRLLREFQEIC` | 3/3 | 0 | 0 | `alpha_helix_seed_candidate` | requested-family alpha geometry retained after relaxation |
| AMPHIPATHIC_ALPHA | `LKKLLELLKKLL` | 3/3 | 0 | 0 | `alpha_helix_seed_candidate` | backbone call is alpha-like; amphipathic organization remains sequence/context evidence |
| HELIX_310 | `Aib-A-Aib-L-Aib-NH2` | 3/3 | 0 | 0 | `3_10_helix_seed_candidate` | explicit Aib retained; Aib-specific 3_10 search channel used without Aib->Ala substitution |
| BETA_HAIRPIN | `LVV-dP-G-LVV-NH2` | 3/3 | 0 | 0 | `beta_hairpin_like` | literature-guided dP-G local turn + beta-extended arm search; final call requires measured relaxed turn/contact geometry |
| BETA_STRAND | `VTVTVTVT` | 3/3 | 0 | 0 | `beta_extended_seed_candidate` | requested beta-extended geometry selected |
| PPII_EXTENDED | `PPAPPPAP` | 3/3 | 0 | 0 | `PPII_seed_candidate` | Pro ring-constrained torsions no longer invalidate the whole seed; final call uses measured phi/psi |
| TURN_RICH | `N-Aib-G-S-N-NH2` | 2/3 | 1 | 0 | `turn_rich` | two Aib-G type-I-prime search candidates satisfy measured turn geometry; one explicit clean fallback remains |
| COILED_COIL | `LEKLAEIAELK` | 3/3 | 0 | 0 | `alpha_helix_seed_candidate` | monomeric helical preorganization only; oligomeric state/pairing is not predicted |

## Implementation notes

- PDE intent is accepted through the public `pde_objective_mode`/design-intent bridge and normalized for PSB selection.
- Requested-family conformers are preferred only when post-relaxation measured geometry matches the requested family.
- Severe-clash conformers are not used merely to fill the requested count.
- `dP-G` and `Aib-G` are literature-guided **search initialization** motifs, not automatic family labels.
- Beta-hairpin classification checks measured C-alpha(i)-C-alpha(i+3) turn geometry, bidirectional nonlocal backbone contacts, and compatible beta/PPII backbone content after relaxation.
- Coiled-coil remains a monomeric preorganization screen until a separate multichain partner/assembly workflow is implemented and validated.

Claim boundary: these results show that the current PSB search/ranking implementation can recover requested-family conformers for these selected regression cases. They do not establish experimental structure accuracy, native-state probability, binding affinity, or conformational population.
