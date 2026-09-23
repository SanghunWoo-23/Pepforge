# SPPS Planner V5.0.0 — Evidence-Driven Decision Support

V5.0.0 preserves the validated V4 planner calculations and adds an evidence-driven layer around real laboratory history. Decision-support functions never replace Generate/Apply Change and never fabricate categorical reagents, cocktails, or historical observations.

## Evidence order

1. Repeated successful historical consensus under the same or very similar conditions
2. Exact bottle-level building-block / exact-sequence / exact-product evidence
3. Repeated coherent category consensus
4. Bounded interpolation inside observed ranges only
5. Chemistry/risk reference
6. `INSUFFICIENT EVIDENCE`

## V5 modules

- **Sequence Difficulty Map** — deterministic residue-level review flags; not a failure probability and never auto-applied.
- **Stage Risk Advisor** — separate Loading, Coupling, and Cleavage review summaries based on transparent rules and observed evidence.
- **Similar Historical Experiments** — canonical-sequence similarity with linked outcomes and provenance.
- **Outcome-aware data** — condition and result data are stored separately so yield, purity, failure, doubling, and observations remain attributable to the actual experiment.
- **Cleavage Amount / Workup Evidence** — TFA/Water/TIS cocktail amounts and precipitation/workup solvent amounts are stored separately. Ethyl Ether and n-Hexane are distinct workup solvents; they are never added to the cleavage cocktail. Unitless numeric values remain unresolved until operator review. Exact-scale evidence is preferred; interpolation is allowed only inside repeated observed scale ranges; extrapolation is disabled.
- **Explicit Loading Model Registry** — model rebuilds are operator-triggered, validated, versioned, and rollback-capable. Predictions are advisory only; Apply remains historical-evidence gated.

## Public / Private contract

Shared runtime code is identical except for `build_profile.py`. Public starts with an empty experimental seed. Private includes internal Loading/Cleavage/Sequence/Material Usage history. Runtime databases and user-data directories remain isolated.

## Safety contract

No monkey patching, placeholders, cross-experiment cocktail synthesis, unresolved-unit guessing, implicit online retraining, or automatic application of model-only output.


### V5.0.0 final workup safety rules
- Cleavage condition, current-scale amount, and precipitation/workup are presented separately.
- Ethyl Ether and n-Hexane are workup solvents, never cocktail components.
- Aggregate/multi-product usage rows are reference-only and excluded from automatic scaling.
- Unitless amounts remain raw and require operator unit review; mL/L is never guessed.
- Current-scale cocktail totals are generated only from single-product observed usage or bounded interpolation inside repeated observed scale ranges.


## Synthesis Issue Log

Operator-observed synthesis problems can be stored as `Stage → Issue type → Severity → Observation → Action → Resolution`. Product/sequence/scale are prefilled from the active Planner item when available. Issue records feed Risk & Evidence as historical evidence, but they never directly change synthesis conditions or become automatic failure labels.
