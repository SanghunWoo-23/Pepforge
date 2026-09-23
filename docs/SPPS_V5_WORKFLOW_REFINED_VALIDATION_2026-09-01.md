# Pepforge V4.0.0 — SPPS Planner V5.0.0 WORKFLOW_REFINED Integration Validation

Date: 2026-09-01
Status: validated development snapshot; Pepforge V4.0.0 remains under active refinement and is not yet declared the final GitHub V4.0.0 release.

## Upgrade source and boundary

- Active suite: Pepforge `4.0.0`.
- Embedded synthesis component: SPPS Planner `5.0.0` Public/Data-Sanitized workflow.
- Upgrade source: user-supplied `SPPS_Planner_V5.0.0_PUBLIC_GitHub_WORKFLOW_REFINED_2026-09-01.zip`.
- The corresponding Private package was used only to confirm shared-source intent; the 10 refined shared runtime files are byte-identical between Public and Private packages.
- No Private seed/history/runtime data was copied into Pepforge.
- The internal `spps_v4_gui` package name is retained only as a backward-compatible namespace; it does not indicate the embedded component version.
- LOT Number controls and Batch Manager remain outside the Pepforge operator surface.

## Refined workflow changes integrated

### 1. Bounded target-loading inversion

- Uses reviewed loading history for the same resin and the same C-terminal amino acid.
- Requires sufficient observed AA-equivalent/loading evidence.
- May narrow by compatible base-equivalent/time context when enough evidence remains.
- Interpolates only inside the observed loading/AA-equivalent range.
- Does not extrapolate outside the observed range.
- Does not mix another amino acid or unrelated resin to manufacture an estimate.

### 2. Separate post-cleavage rescue

- Adds explicit post-cleavage rescue state/calculation.
- Operator-selected NH4I reduction remains separate from the cleavage cocktail.
- Rescue is not auto-applied merely because an oxidation risk is present.
- Rescue metadata persists with the active SPPS item/workspace state.

### 3. Issue-centered coupling workflow

- Coupling problems/deviations are routed to synthesis issue/evidence logging.
- An issue record does not automatically change coupling conditions and is not converted into a failure probability.

## Preserved contracts

- Cys cleavage-equivalent rule remains synchronized: positive manual override first; otherwise Cys gives `100 TFA eq × Cys count` without peptide-length addition; Cys-free sequences use the length baseline.
- Evidence-first cleavage behavior remains sequence-first and does not mix components from unrelated historical cocktails.
- Public experimental history remains empty/sanitized.
- Pepforge result-bundle exports remain the active integrated export convention.
- Existing PDE → PSB → SPPS → Docking/validation workflow remains intact.
- No runtime monkey patch, placeholder, dummy scientific result, or silent Private-data inclusion was introduced.

## Regression results

The full root test set was executed in bounded groups because some older structure/external-bridge test combinations exceed the execution-time limit when run as one large process.

- Root test collection: **274 tests**.
- Complete grouped result: **273 passed, 1 skipped, 0 unresolved failures**.
- SPPS refined + existing V5 targeted group: **35 passed, 1 skipped**.
- PSB helix geometry: **2/2 passed**.
- PDE intent-aware PSB selection: **4/4 passed**.
- Result-bundle + structure/simulation group: **11/11 passed**.
- Runtime/full-package/regression/release-integrity group: **8/8 passed**.
- Release verification matrix test: **2/2 passed** after clean-tree artifact removal.
- Release gate test: **2/2 passed**.
- Additional Hot Spot Finder application tests: **5/5 passed**.

## Clean-tree release checks

- Release verification matrix: **14/14 passed**.
- Release gate: **23/23 passed**.
- Python source files checked/compiled: **256**.
- Python parse/compile errors: **0**.
- Runtime patch/placeholder/duplicate-definition findings: **0**.
- Stale legacy-name findings: **0**.
- Packaging-artifact findings: **0**.

## Public data audit

- `apps/spps_planner_app/data/actual_runs.csv`: header only, **0 data rows**.
- `apps/spps_planner_app/data/experimental_seed/`: Public `README.md` only.
- Pepforge suite version: `4.0.0`.
- Embedded standalone SPPS engine metadata: `5.0.0`.

## Claim boundary

This validation demonstrates source integration, deterministic workflow contracts, regression behavior, package cleanliness, and public/private separation. It does not establish experimental synthesis yield, purity, chemical rescue efficacy, peptide binding affinity, native-state structure, MD convergence, or biological efficacy.
