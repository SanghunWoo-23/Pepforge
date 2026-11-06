## V6.0.0 — 2026-10-29 SPPS V8 Treeview style refresh

## V6.0.0 — Native docking input, progress, and result-view repair (2026-10-30)

- Fixed a **reproduced Tkinter thread-access crash** in direct file docking by snapshotting widget variables on the UI thread.
- Added verified mmCIF receptor conversion (Biopython with Gemmi fallback) and explicit runtime requirements.
- Connected successfully generated direct native docking poses and interaction evidence to Results & Analysis; no-verified-pose cases report failure.
- Added determinate Native search-trial progress and conservative progress display for other workflows, including PDE import and Hot Spot Finder stage milestones.
- Simplified Unified Native Results to essential actions with optional Advanced tools.
- Added engine, mmCIF and opt-in GUI end-to-end smoke regression tests.
- Native scores are not physical binding energies; production MD/ABFE and Windows installation remain independently unverified.


- Updated vendored SPPS Planner **V8.0.0** (matching Public/Private edition) from the supplied Treeview Style Fixed source.
- Recommendations/Lab History now uses its own ttk Treeview styles instead of changing global Plan/Materials headers.
- Added Pepforge and V8 regression tests verifying heading and row-height isolation; unchanged peptide calculation engine.
- Kept standalone V8 GUI launch, Studio three-tab UI, independent version labels, and Public/Private boundary.
- This is a V6.0.0 **maintenance refresh**, not a verified scientific performance upgrade.

# Changelog

## Pepforge V6.0.0 — Docking molecular-input layout and standalone SPPS V8 (2026-10-29)

- In Studio's **Docking & Simulation** tab, moved receptor file and sequence into one Receptor section; moved peptide file and peptide sequence into one adjacent Peptide section. Docking options now follow molecular inputs.
- Shared the peptide sequence between Structure Builder and Docking via a single `StringVar`, retaining values when switching in-window tabs.
- Removed the Windows cross-process SPPS embedded surface. SPPS V8 now opens as its original standalone window, similar to PDE and PSB, from the same Pepforge launcher.
- Preserved V8 synthesis engine, native Project/Batch/Materials/Checklist/Cleavage workflows and its independent V8.0.0 version. Public/Private datasets remain separated.
- Updated user-facing READMEs, manuals, SPPS integration guide, release notes and verification boundaries. Historic changelog entries below describe prior builds, not current behavior.

## Pepforge V6.0.0 — SPPS V8 embedded workspace (historical, 2026-10-28; superseded)

- Added integrated SPPS workspace inside the **same Windows Pepforge launcher** using Win32 cross-process window parenting; preserved the original V8 UI and chemistry engine. `Open separately` fallback remains available.
- Added same-window navigation from Pepforge sidebar to SPPS and back, persistent session while switching views, resize handling, restart and unsaved-work confirmation.
- Updated vendored **SPPS Planner V8.0.0** to 2026-10-28 Public source. Independent V8 build maintained. Public/Private datasets remain isolated.
- Added a Pepforge title/header and spacing above the Studio's three in-window tabs.
- Updated README/Manual and standalone compatibility guidance. Windows-native UI embedding and installer behavior require real-machine acceptance; software tests do not certify ABFE predictions.

## Pepforge V6.0.0 — Unified Windows Build / Optional WSL2 Science Setup (2026-10-27)

### Windows and scientific installation
- Unified `INSTALL_BUILD_TOOLS_AND_BUILD.bat`: interactive build / build + science / science only / verification routes and scripted flags.
- Science installer delegates from Windows to WSL2 and creates or updates an isolated `pepforge-science` Conda environment; validates imports, CLI and OpenMM platforms.
- Corrected Inno Setup application and output installer versions to **6.0.0**.
- Added SPPS Planner V8 Public assets to the PyInstaller build specification. The V8 source launch in frozen builds still needs a separately installed compatible Python/runtime; standalone V8 bundling has not been established.
- Removed redundant top-level science/SPPS BAT wrappers and legacy release TXT; retained necessary Python scientific installer, dependency files, and original vendor files.

### Testing boundaries
- Offline launcher/install contracts are tested; actual Windows `.exe`/Inno build, WSL2 downloads and full OpenFE simulations require target-machine verification.

## Pepforge V6.0.0 — Public Research Source Release Candidate (2026-10-26)

### Added / expanded
- Supported modified-peptide conformer and stereochemical validation paths, MMFF94s sampling and diversity filtering.
- Native/ensemble docking, optional torsion ensemble and interface refinement, PyMOL token review and docking benchmark diagnostics.
- Optional OpenFE/OpenMM/OpenFF/GAFF/PyMBAR scientific execution, provenance and accuracy-audit entry points.
- Public SPPS Planner **V8.0.0** launch integration as a separate process.

### Documentation / packaging
- GitHub README and Korean README rewritten using the V5 structure and V6 capabilities.
- Version labels and source launch banner updated to V6.0.0; backward-compatible `v5-*` CLI names remain historical APIs.
- Obsolete root-level internal development notes removed from this public source presentation (private source archives remain unchanged).

### Validation boundary
- SPPS V8 Public launch contract: **3 passed** (recorded in the 2026-10-23 integration input archive).
- Complete V6 integrated test suite, Windows GUI/EXE acceptance, production OpenFE ABFE, and experimental ΔG_bind accuracy are **not certified**.

## Pepforge V5.0.0 — 2026-10-13

### Added
- Integrated Structure & Docking Studio for peptide structure generation, native docking, interaction analysis, mechanics/trajectory review, and result interpretation.
- Public protein–peptide benchmark/provenance workflow with RCSB PDB and UniProtKB support.
- Native docking calibration/tuning and validation-workspace tooling.
- Updated SPPS Planner integration using the current V7.0.0 Final runtime path.

### Improved
- Standard mouse-wheel page scrolling in Structure & Docking Studio and Workflow Mode.
- Stable viewport sizing during scrollbar movement and reduced lower-boundary scroll stutter.
- Larger sequence editing and analysis workspaces.
- Public packaging, release metadata, installer metadata, and documentation for V5.0.0.

### Scientific boundaries
- Native docking scores remain internal pose-search/ranking scores, not affinity, ΔG, or Kd.
- Native Mechanics is not presented as production molecular dynamics.
- Predicted/generated structures remain hypotheses requiring external validation.

## Pepforge V4.0.0

V4 established the integrated peptide design, structure-generation, modified-peptide, SPPS-planning, and interaction-review foundation carried forward into V5.

## V6.0.0 — Windows/WSL2 science bootstrap hardening (2026-10-27)

- Unified BAT now optionally provisions missing Ubuntu when Science install is explicitly selected.
- Incomplete WSL setup is reported with reboot/first-user-setup instructions, not marked successful.
- Pinned official SHA-256 Miniforge download for WSL2 Linux where package manager is missing.
- Explicit Ubuntu distribution choice, UTF-16 Windows WSL output handling, and verification-only no-install policy.
- Focused offline installer/embedded-SPPS checks: 37 passed; Windows execution and actual OpenFE installation remain unverified.
