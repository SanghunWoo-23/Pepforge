# Pepforge Release History

## v3.0.0 Current STD + SPPS Planner V4 Integration (2026-08-13)

- Established Pepforge V3.0.0 + SPPS Planner V4 as the current project STD.
- Preserved Hot Spot Finder, Peptide Design Engine, Top-5 Structure Builder, SPPS planning, Docking Workbench, and external-validation export workflows.
- Added conservative experimental-evidence states and sequence-first cleavage advice without applying model-invented conditions.
- Preserved the confirmed `Ac-EEMQRR-NH2` 30 eq, TFA 95% / water 5%, no-TIS contract.
- Excluded LOT Number and Batch Manager from the Pepforge operator surface.
- Removed private/runtime data from the GitHub package and retained empty public templates only.

> Historical component documents below may use their own development-series numbers. The repository-level public version and current STD are V3.0.0.

## v2.0.0 GUI/SPPS Planner Patch (2026-06-16)

- Added direct source launchers for Pepforge and native Tk SPPS Planner.
- Split pre-modifier Fmoc removal from non-Fmoc N-terminal modifier/cap rows.
- Fixed Ac modifier rows so deprotection is not duplicated in the final cap row.
- Aligned installer/build metadata to v2.0.0.


## v3.4.1 Internal Cleanup and Documentation Maintenance

- Patch-level cleanup release.
- No scientific claim expansion.
- Removed redundant rebuild QA logs and smoke-test log text files from the public package.
- Preserved source code, tests, templates, examples, and current manuals.
- README/MANUAL metadata updated to v3.4.1.

## Current major workflow

```text
Design Engine
→ SPPS Planner
→ PyMOL/Structure Builder
→ RCSB target fetch
→ Target Preparation
→ Binding Site Selector
→ Docking Workbench
→ External Docking/MD Import
→ Calibration Dataset Mode
→ Calibration Model Cards
→ Evidence Engine
```

## Claim boundary

Pepforge is a screening, planning, evidence-organization, and validation-bridge workbench.
It does not prove final Kd, true nM binding, or replace external docking/MD/experimental validation.


## v3.5.0 Workflow Session / Project Resume

- Added project/session manager.
- Added project stage progress CSV.
- Added next-action checklist.
- Added portable `pepforge_project_session.json`.
- Added Docking Workbench Project Session / Resume UI.


## v3.6.0 Candidate Comparison Dashboard

- Added candidate comparison dashboard.
- Added ranked dashboard CSV/Markdown/SVG summary.
- Added Docking Workbench dashboard UI.
- Added candidate-level evidence merge across design/docking/external/calibration outputs.


## v3.7.0 Experimental Data Import

- Added experimental assay CSV template/import.
- Added normalized experimental data and candidate-level median summary.
- Connected experimental candidate summary to Candidate Comparison Dashboard.


## v3.7.1 Internal Cleanup and Direction

- Patch-level cleanup according to n.o.p patch increment rule.
- Preserved all simulation/calculation data and functional modules.
- Removed only nonessential packaging/runtime noise.
- Added improvement roadmap after v3.7.1.
- Recommended v3.8.0 Workflow Automation Runner as next functional release.


## v3.9.0 Candidate Evidence Diff / Compare Runs

- Added run comparison module.
- Added changed file inventory.
- Added candidate rank delta report.
- Added evidence delta summary.
- Added Docking Workbench Run Comparison / Evidence Diff panel.


## v4.0.0 Public Release Stabilization

- Added stable CLI entry point.
- Added public API re-export module.
- Added public output contract and stability report module.
- Added public API/output contract documentation.
- Stabilized release metadata for public research package.


## v4.0.1 Patch Cleanup

- Patch-level cleanup after public stabilization.
- Preserved all functional modules, tests, templates, examples, and simulation/calculation data.
- Removed only nonessential packaging/runtime noise.
- Updated public API version metadata to v4.0.1.
- Updated README/MANUAL/CITATION metadata.


## v4.0.2 Runtime Validation Patch

- Added runtime validation module.
- Added CLI command `validate-runtime`.
- Added public API export `run_runtime_validation`.
- Added runtime validation report outputs.
- Verified core public execution paths without adding new scientific claims.


## v4.0.3 Full Package Audit

- Added full package audit module.
- Added CLI command `audit-package`.
- Added public API export `audit_package`.
- Added required public-file, compile, CLI, runtime, stale-name, and artifact checks.
- No new scientific claims.


## v4.0.4 Regression Audit

- Added representative dataflow regression audit.
- Added CLI command `regression-audit`.
- Added public API export `run_regression_audit`.
- Checked experimental import → candidate dashboard → run comparison flow.
- Checked workflow automation, validate-runtime, and audit-package commands.
- No new scientific claims.


## v4.0.5 Release Integrity Audit

- Added release integrity audit module.
- Added CLI command `release-integrity`.
- Added public API export `audit_release_integrity`.
- Added release file manifest with SHA256 hashes.
- No new scientific claims.


## v4.0.6 Release Verify Matrix

- Added release verification matrix module.
- Added CLI command `verify-matrix`.
- Added public API export `verify_release_matrix`.
- Rechecked public entrypoints and packaging artifacts.
- No new scientific claims.


## v4.0.7 Release Gate

- Added final release gate module.
- Added CLI command `release-gate`.
- Added public API export `release_gate_check`.
- Rechecked metadata, docs, Python compilation, direct public API smoke checks, stale names, and artifacts.
- No new scientific claims.


## v4.1.0 Functional Fix

- Fixed PyMOL Structure Builder export on non-ASCII/Windows paths by staging RDKit writes.
- Fixed Docking Workbench target recognition with a centralized resolver.
- Fixed SPPS Planner N-terminal cap handling so final Fmoc removal is not a separate unit row.
- Added functional regression tests for the three reported issues.
