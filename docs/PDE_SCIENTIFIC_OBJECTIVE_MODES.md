# PDE Scientific Objective Modes

This public implementation adds explicit design intent without converting sequence heuristics into experimental claims.

## Objective modes

- `INTERACTION_ONLY`: optimize target-interaction evidence only. Preferred structure is normalized to `NONE`. SPPS difficulty, aggregation and solubility remain visible as warnings but do not steer PDE selection; malformed/unknown chemistry and invalid topology remain blocked.
- `INTERACTION_FIRST`: target interaction dominates; feasibility remains an independent objective and an optional structure preference can act as a weak guard.
- `BALANCED`: interaction, feasibility, chemistry route, environment context and diversity are considered together; a structure objective is added only when the user explicitly selects one.
- `STRUCTURE_GUIDED`: requires an explicit preferred structure and jointly evaluates interaction, structure-context evidence, environment and feasibility.
- `STRUCTURE_EXPLORATION`: requires an explicit preferred structure and uses a structure-led objective while retaining interaction as a secondary term.

## Supported preferred structures

`ALPHA_HELIX`, `AMPHIPATHIC_ALPHA`, `HELIX_310`, `BETA_HAIRPIN`, `BETA_STRAND`, `PPII_EXTENDED`, `TURN_RICH`, `COILED_COIL`.

`MILD`, `BALANCED`, and `STRONG` alter how structure evidence is blended with interaction in the modes where structure is active. They are ranking controls, not confidence levels.

## Context model

The sequence-context screen separates intrinsic residue class from position and sequence context. It includes N/C-cap descriptors, central Pro/Gly penalties, i,i+3/i,i+4 opposite-charge context, alpha-helical hydrophobic moment, beta alternating-face context, central turn context, D-Pro-Gly motif recognition, Pro-rich PPII context and heptad coiled-coil descriptors.

The implementation follows the supplied literature summary's central rules: residue effects are position/context dependent; beta strand, beta hairpin and aggregation are not interchangeable; aqueous and membrane environments should not share one propensity/hydrophobicity interpretation; short peptides should be treated as ensembles rather than one experimentally validated fold.

## Non-natural and D-residue boundary

PDE structure scoring does **not** silently substitute D- or non-natural residues with canonical L residues. The result exports canonical-L coverage and unsupported structure tokens. Partial coverage may contribute only the explicitly supported canonical-L portion and is visibly down-weighted.

## PSB hand-off

PDE records design intent in each candidate manifest. PSB uses a supported preferred-structure intent to prioritize conformers whose measured geometry belongs to that family. It does not force labels or insert unrelated families for diversity; clean fallbacks are marked explicitly when requested-family candidates are insufficient.

Top-5 selection does not enforce cross-family diversity. When PDE supplies a supported preferred-structure intent, PSB prioritizes physically usable conformers inside that requested basin and ranks them by requested-family backbone geometry, steric quality and supporting evidence. If too few clash-free requested-family conformers exist, explicit fallback entries are used rather than fabricating the requested fold. In `INTERACTION_ONLY`, PSB does not force a fold family. RMSD/family spread remains a diagnostic only, not a selection objective.

## SPPS positional risk map

PDE separately reports position-level assembly, cleavage and aggregation warnings for supported sequence contexts such as Asp-Gly/Asn/Ser, V/I/T clusters, hydrophobic/aromatic stretches, Met and Cys. These are warning descriptors, not predicted yield, purity, solubility or reaction probability.
