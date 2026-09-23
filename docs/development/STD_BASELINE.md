# Pepforge Current STD Baseline

## Canonical baseline

- Pepforge suite version: `4.0.0`
- Release generation: `Design/Structure Theory + Evidence Workflow + SPPS V5 FAST_OPEN`
- Integrated SPPS component: `SPPS Planner V5.0.0`
- V4 STD date: `2026-09-02`
- V4 source basis: the validated Pepforge V3.0.0 Scientific Context & Ensemble Upgrade promoted to a new major release after result-bundle/version-architecture review.
- SPPS integration boundary: Public/Data-Sanitized code and empty public seed only; Private/Local data are not part of Pepforge.

The final distributable ZIP hash is generated after packaging and therefore is not hard-coded into this source baseline file. Release-time validation reports record the actual artifact hash.

## Required preservation rules

- Preserve Hot Spot Finder, PDE, Top-5 Structure Builder, SPPS, Docking Workbench, and external-validation workflows.
- Preserve separate conservative-manual versus tool-compatible interaction evidence profiles; do not silently replace legacy coarse Docking Workbench cutoffs.
- Preserve Hot Spot sequence-chemistry transfer as evidence only; it is not a 3D contact/affinity claim.
- Preserve V4 docking lineage/PyMOL preparation without claiming an actual docking backend; actual docking execution is a future V5 scope.
- Preserve stage-by-stage modified-peptide support and evidence provenance instead of silent canonical substitution or aggregate confidence scores.
- Preserve SPPS V5 FAST_OPEN run/work-item linkage and DB initialization fast-path while LOT/Batch remain unexposed in Pepforge.
- Preserve PDE objective modes and real Pareto NSGA-II behavior.
- Preserve supported chemical, tag, linker, non-natural amino-acid, D-residue, and terminal-modification parsing.
- Preserve explicit Generate/Update and Apply Change behavior in SPPS.
- Preserve the latest embedded SPPS Planner V5.0.0 evidence-first cleavage contract: exact cocktails come only from one complete reviewed compatible historical record; generic chemistry guidance must not fabricate or auto-apply an exact condition.
- Preserve the refined V5 loading-target contract: inverse AA-equivalent recommendations use only same-resin/same-C-terminal-AA reviewed history and interpolate only inside the observed range.
- Keep post-cleavage rescue separate from cleavage cocktail composition; operator-selected NH4I reduction must never be silently inserted into the cocktail.
- Keep LOT Number and Batch Manager outside the Pepforge operator surface.
- Preserve PDE→PSB/SPPS candidate traceability: normalize `pde_objective_mode` into downstream design intent and reuse a unique PDE candidate ID for the same construct.
- Preserve candidate-centered Summary Reports as evidence-only indexes; absent Docking/trajectory/experimental stages remain unavailable rather than being inferred.
- Preserve PSB requested-family truthfulness: Pro-rich PPII tolerates non-rotatable Pro ring torsions but is reclassified from measured relaxed geometry; only explicit literature-supported dP-G/Aib-G motifs receive turn search seeds and family calls still require measured relaxed geometry; coiled-coil remains monomeric preorganization only.
- Keep user-triggered result outputs in coherent `YYYY-MM-DD_<name-or-sequence>/` bundles; do not scatter run artifacts across the selected base directory.
- Do not introduce runtime monkey patches, placeholder/stub/dummy/fake behavior, fabricated scientific parameters, hidden fallbacks, or silent feature loss.

## Version boundary

Pepforge V4.0.0 and SPPS Planner V5.0.0 are independent version numbers. The suite version is defined centrally in `peptiforg_core/version.py`; the embedded SPPS component retains its own V5.0.0 metadata even though the backward-compatible internal namespace remains `spps_v4_gui`. Historical V3 release notes remain unmodified release history.

- Preserve V4.0.0 theory contract: Conformational Strategy is an optimizer policy, Hotspot Complementarity is coarse chemistry evidence, and neither may be presented as a binding mechanism, contact geometry, affinity, or structure probability.
