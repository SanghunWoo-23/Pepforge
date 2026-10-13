# Changelog

## V5.0.0 FINAL — UI Polish R4 (2026-10-12)

### Scrolling / UI stability
- Added a shared stable vertical page scroller for Structure & Docking Studio and Workflow Mode.
- Conventional mouse-wheel scrolling now works across long analysis pages without middle-button panning.
- Coalesced high-resolution wheel events and clamped redundant events at upper/lower page limits.
- Debounced scrollregion recalculation to reduce end-of-page stutter.
- Locked inner-page width to the viewport so dragging the scrollbar thumb cannot trigger width/stretch feedback.
- Preserved independent horizontal scrolling for long sequence editors and result tables.

### Workflow Mode
- Added full-page vertical scrolling with the same edge-clamped / debounced behavior as PSB.
- Added PageUp, PageDown, Home and End navigation through the shared page-scrolling layer.

### SPPS Planner reference
- Rechecked the supplied SPPS Planner V7.0.0 FINAL R2 package.
- Kept Pepforge-specific integration only; no SPPS handover/package material is copied into Pepforge release documentation.

### Validation
- V5 regression: 130 passed / 0 failed.
- V4 compatibility release/verify/integrity: 6 passed / 0 failed.
- V4 full-package/regression/source-integrity: 7 passed / 0 failed.
- Xvfb GUI smoke confirmed wheel scrolling from child widgets, stable outer-canvas width, and low-cost repeated wheel events at the lower page boundary.

## V5.0.0 FINAL — UI Polish R3 (2026-10-08)

### Desktop workflow
- Reworked Structure & Docking Studio page scrolling to conventional mouse-wheel navigation.
- Removed the requirement for middle-button page panning.
- Removed the nested resizable PanedWindow from the scrollable Studio page to prevent geometry/stretch feedback.
- Added independent horizontal scrolling for long peptide sequences and chemistry result tables.
- Kept PSB + Native Docking in the unified Structure & Docking Studio workflow.

### SPPS integration
- Integrated the supplied SPPS Planner V7.0.0 FINAL R2 public runtime as the primary planner target.
- Preserved its Project Manager / Batch Manager workspace.
- Source launches use an isolated subprocess; the earlier embedded planner remains an explicit frozen-build fallback.

### Validation
- 127 V5 tests passed.
- 13 V4 compatibility/audit tests passed.
- Direct release gate: 25 passed / 0 failed.
- 524 Python files compiled / 0 errors.

## V5.0.0 FINAL — UI Polish R2
- Unified PSB and docking into Structure & Docking Studio.
- Added large peptide sequence editor and large-window workflow.
- Added first-pass page scrolling and SPPS launch responsiveness improvements.

## V5.0.0 FINAL
- Native-first / quality-preserving / offline-capable V5 workflow finalized.
- Native docking, interaction review, mechanics/trajectory follow-up, shared result viewer, public benchmark/tuning infrastructure, RCSB/UniProt bridges and validation contracts completed.
