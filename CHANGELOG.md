# Changelog

## v2.0.0 - Public Research Baseline

### Added

- Docking Workbench Input collapse/expand control.
- Docking Workbench full-data windows: Input data full, Results data full, MD data full.
- PRODIGY-like, GROMACS-like, and MD-style screening summaries for report comparison.
- Quick-safe PyMOL bridge package export based on existing Build SDF/PDB/PML outputs.
- Compound database audit files for manual-required and vendor-form-dependent entries.
- GitHub upgrade documentation and v2.0.0 baseline release notes.

### Changed

- Version line reset from v4.2.x patch branch to v2.0.0 public baseline.
- SPPS final wash logic: last deprotection or terminal modifier coupling now ends with DMF x3 followed by DCM x3; redundant terminal post-coupling DMF x2 removed.
- Linkers are treated as amino-acid-like coupling units.
- Labels, dyes, caps, terminal chemicals, and tags are treated as chemical modifiers.
- Reagent MW and product contribution MW are separated in SPPS data handling.
- Generic vendor-dependent labels and tags are marked manual-required where exact material calculations are unsafe.
- Case-insensitive and full-name aliases improved for Pal, Caf, Gal, Nic, and related chemical tokens.

### Fixed

- Caffeic acid MW conflict normalized to 180.16 g/mol for reagent MW.
- Acetyl contribution separated from acetic anhydride reagent MW.
- DIC density conflict cleaned from the database policy.
- Docking Workbench target summary visibility restored through collapsible input and full-data windows.
- PyMOL Structure Builder bridge buttons generate diagnostic/export packages instead of failing silently.

### Preserved

- Hotspot Finder.
- Peptide Design Engine.
- SPPS Planner plan/material/checklist/log workflow.
- Docking Workbench target/contact/affinity/external-validation workflow.
- PyMOL Structure Builder SDF/PDB/PML generation.
- CLI validation/audit/release-gate utilities.
