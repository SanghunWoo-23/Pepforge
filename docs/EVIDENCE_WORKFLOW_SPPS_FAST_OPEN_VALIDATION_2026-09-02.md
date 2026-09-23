# Pepforge V4.0.0 — Evidence Workflow + SPPS V5 FAST_OPEN Validation

Date: 2026-09-02

Status: validated development snapshot. The Pepforge suite version remains `4.0.0`. This document validates software behavior and public-package integrity only; it is not experimental/native-structure/binding validation and does not declare the final GitHub V4.0.0 release complete.

## Included refinement

- Preserves the previously validated Design/Structure Theory Refined baseline.
- Integrates the Public/Data-Sanitized SPPS Planner V5 `FAST_OPEN` workflow without exposing Pepforge LOT Number or Batch Manager controls and without bundling Private/local experimental history.
- Preserves the SPPS V5 Cys hard rule, bounded target-loading inversion, separate post-cleavage rescue workflow, issue/evidence logging, and linked `run_id` / `work_item_id` records.
- Adds geometry-aware interaction-evidence profiles separately from the legacy coarse Docking Workbench contact table.
- Adds Hot Spot weighted chemistry-profile export and PDE evidence hand-off.
- Adds stage-wise modified-peptide support reporting.
- Extends Structure Consensus with local-backbone, nonlocal-contact-map, and hotspot-region diagnostics.
- Adds candidate evidence-matrix export without collapsing independent evidence into a fabricated global score.
- Adds V4 candidate -> PSB -> future docking lineage and PyMOL review preparation only; actual docking execution remains future V5 scope.
- Keeps MD execution claims guarded: imported real trajectories may be analyzed, while protocol/backend readiness is not reported as completed MD.

## No-placeholder / no-monkey-patch integrity contract

The production source tree was statically audited after the final integration.

- Runtime class/function monkey-patch architecture: **0 findings**.
- Module-level attribute reassignment used as runtime patching: **0 findings**.
- Duplicate top-level definitions: **0 findings**.
- Placeholder/dummy implementation markers in production source: **0 findings**.
- Pass-only functions: **0 findings**.
- `NotImplementedError`-only functions: **0 findings**.

Ordinary `pass` statements used only inside exception-cleanup / optional UI cleanup paths are not incomplete function implementations and are allowed.

## Complete regression coverage before packaging

The package collects **327 tests**. Because several legacy subprocess/bridge tests can keep a combined pytest process alive for a long time after individual checks finish, the complete suite was executed in bounded functional groups. Every collected test was covered.

- Total collected: **327**
- Passed: **326**
- Skipped: **1**
- Failed / unresolved: **0**
- Intentional skip: Public build has no private empirical cleavage anchors (`tests/test_spps_v5_empirical_cleavage.py`).

Major grouped checks included:

- SPPS V5 / FAST_OPEN / Pepforge SPPS workflow: **54 passed / 1 skipped**.
- PDE scientific/objective/literature contracts: **28/28 passed**.
- Core structure contracts: **29/29 passed**.
- PSB/design-theory/candidate-lineage/result-bundle group: **67/67 passed**.
- Interaction evidence + Hot Spot integration: **11/11 passed**.
- V1/V2 compatibility and external-bridge contracts: **31/31 passed**.
- V3 evidence/project/workflow contracts: **31/31 passed**.
- General V4 startup/parser/public-stability/functional contracts: **25/25 passed**.
- V4 structure/runtime/package/source-integrity group: **16/16 passed**.
- V5/V6 historical docking/UI/structure contracts retained by V4: **18/18 passed**.
- V7/V8 historical validation/UI/cutoff contracts retained by V4: **12/12 passed**.
- Release verify + release gate tests: **4/4 passed** after clean-tree execution.

## Release-verification self-cache fix

A real packaging-validation bug was found during the final clean-tree check: importing/running the release verification under pytest could create `__pycache__` / `.pytest_cache`, which the verification then counted as distributable artifacts. The verification implementation was corrected to remove only transient Python/test cache artifacts immediately before its package-artifact scan. No test was disabled or bypassed.

## Public / Private boundary

- `apps/spps_planner_app/data/actual_runs.csv`: header only, **0 data rows**.
- `apps/spps_planner_app/data/experimental_seed/`: public `README.md` only.
- Private/local experimental history and private model seed/history are not bundled.
- Pepforge LOT Number controls and Batch Manager remain outside the public operator surface.

## Scientific claim boundary

- PDE outputs are design-ranking/evidence hypotheses, not affinity or efficacy predictions.
- PSB outputs are generated/relaxed conformer hypotheses, not experimentally validated native structures.
- Geometry-aware contacts are structural evidence under the selected screening profile, not measured binding energy.
- Structure Consensus reports agreement/disagreement diagnostics; external predictors are not ground truth.
- Actual MD-derived metrics require an actual imported trajectory or an actually available/executed supported backend.
- V5 docking lineage/PyMOL preparation in this V4 snapshot does not mean a docking calculation was executed.
