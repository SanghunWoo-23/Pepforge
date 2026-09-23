# Pepforge V4.0.0 — Design / Structure Theory Refinement Validation

Date: 2026-09-02  
Status: development snapshot validation; not experimental/native-structure validation and not a final GitHub-release declaration.

## Scope

This checkpoint validates the 2026-09-02 Design/Structure Theory refinement layered on the existing Pepforge V4.0.0 + SPPS Planner V5 refined workflow. Existing functionality is preserved; the suite version remains `4.0.0`.

Main refinement areas:

- PDE `PREORGANIZED / ADAPTIVE / FLEXIBLE` Conformational Strategy.
- Family-specific structure evidence and explicit claim guards.
- Pace–Scholtz alpha context and N-cap/acetylation separation.
- PPII residue/context handling and Pro-aromatic cis/trans risk reporting.
- Explicit Aib 3_10 search without canonical substitution.
- Literature-guided `dP-G` / `Aib-G` local turn search seeds.
- Beta-hairpin measured post-relaxation geometry with bidirectional nonlocal backbone-contact checks.
- Hotspot Complementarity `OFF / REPORT_ONLY / EVIDENCE_AND_SELECTION` as coarse chemistry evidence only.
- PDE -> manifest -> Workflow -> PSB/SPPS -> candidate Summary Report traceability for theory fields.

## Focused regression results

- Design/PSB/candidate-traceability tests: **41/41 passed**.
- SPPS V5 refined tests: **44 passed / 1 skipped**.
- Structure/simulation tests: **32/32 passed**.
- Hot Spot Finder tests: **5/5 passed**.

The skipped SPPS test is an optional-environment path and is not an unresolved failure.

## Preferred-structure probe

Representative PSB build probes are recorded in `docs/PSB_PREFERRED_STRUCTURE_PROBE_2026-09-02.md`.

- Alpha helix: 3/3 requested-family matches.
- Amphipathic alpha: 3/3 alpha-backbone requested-family matches.
- Explicit-Aib 3_10: 3/3 requested-family matches.
- `LVV-dP-G-LVV-NH2` beta-hairpin: 3/3 requested-family matches.
- Beta strand: 3/3 requested-family matches.
- PPII: 3/3 requested-family matches.
- `N-Aib-G-S-N-NH2` turn-rich: 2/3 requested-family matches + 1 explicit clean fallback.
- Coiled-coil request: 3/3 monomeric alpha-preorganization matches; no oligomeric-state claim.
- Severe-clash selected count: 0 for the recorded Top-3 probe selections.

These are regression/sanity probes, not experimental accuracy benchmarks.

## Clean-tree release checks

Before packaging:

- Pepforge suite version: **4.0.0**.
- Python files compiled by release gate: **261**.
- Python compile errors: **0**.
- Source-integrity findings: **0**.
- Stale active release-name findings: **0**.
- Packaging-artifact findings: **0**.
- Release verification matrix: **16/16 passed**.
- Release gate: **25/25 passed**.
- Public `apps/spps_planner_app/data/actual_runs.csv`: **0 data rows**.
- Public experimental seed directory: documentation only; no private experimental history bundled.

## Scientific claim boundary

The validation above checks software behavior, regression contracts, package readiness, and selected conformer-search sanity cases. It does not validate experimental binding affinity, Kd/Delta G, peptide efficacy, solution-state populations, synthesis yield, native structure, pharmacology, safety, or trajectory convergence. PDE values remain design-ranking evidence; PSB structures remain generated/relaxed conformer hypotheses.

## Distribution check

The final distribution ZIP must be unpacked into a fresh directory and re-run through the core theory/PSB/SPPS regressions, release verification matrix, release gate, version/boundary checks, and source parse/compile checks. The external artifact validation report accompanying the ZIP records those exact-artifact results and SHA-256.
