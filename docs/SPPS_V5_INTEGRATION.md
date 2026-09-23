# Pepforge V4.0.0 — Integrated SPPS Planner V5.0.0

Pepforge V4.0.0 embeds the **Public/Data-Sanitized SPPS Planner V5.0.0** calculation and evidence workflow. The suite version and SPPS component version are independent.

## Integration boundary

- Active Pepforge suite version remains `4.0.0`.
- Embedded synthesis component is `SPPS Planner V5.0.0`.
- The internal Python namespace remains `spps_v4_gui` for backward import compatibility; this namespace name is not the component version.
- LOT Number controls and the Batch Manager tab are not exposed in Pepforge. Compatibility fields may remain internally blank so older project schemas can still be read safely.
- Public packages do not bundle Private experimental history, verified local runs, private seeds, batch/lot data, or user-local ML data.

## V5 decision support retained

The integrated component retains V5 Public features including sequence difficulty review, stage-specific Loading/Coupling/Cleavage risk review, similar historical experiments, outcome-aware records, cleavage amount/workup evidence, explicit loading-model registry, synthesis issue logging, and V5 condition recommendations. These are evidence/advisory functions and do not replace Generate/Apply Change.

## Cys cleavage-equivalent contract

The synchronized V5 engine rule is:

1. A positive manual cleavage-equivalent override is used exactly as entered.
2. Otherwise, if Cys is present, automatic TFA equivalents are `100 eq × Cys count`. The peptide-length baseline is not added.
3. Cys-free sequences use the V5 public-safe length baseline.

The Cys rule controls TFA equivalents; scavenger/cocktail selection remains a separate evidence/SOP decision.

## Workflow-refined additions (2026-09-01)

- **Target loading inversion:** the advisor may estimate the AA equivalent needed for a requested loading only from reviewed records matching the same resin and the same C-terminal amino acid. The estimate is bounded to the observed history and never extrapolates outside that range.
- **Context handling:** matching base-equivalent/time context may narrow the evidence when sufficient, but the advisor does not mix another amino acid or unrelated resin to fill gaps.
- **Post-cleavage rescue:** optional NH4I reduction is represented as a separate post-cleavage rescue calculation/state. It is not a cleavage cocktail row and is not automatically applied merely because oxidation risk exists.
- **Issue-centered coupling workflow:** coupling problems/deviations are recorded through synthesis issue/evidence logging; issue records do not automatically change conditions or become failure probabilities.

## Pepforge-specific behavior preserved

SPPS exports continue to use Pepforge result bundles rather than the standalone planner's timestamp-only export folder. Related CSV/XLSX/ZIP/manifest artifacts are kept together under the Pepforge result-bundle contract.

## Scientific/data guardrails

- No fabricated experimental history or model confidence.
- No unresolved-unit guessing.
- No cross-experiment cocktail synthesis presented as one historical condition.
- Model-only output is advisory and is not auto-applied.
- Public and Private runtime data remain separated.
- Unsupported chemistry remains explicit rather than silently canonicalized.
