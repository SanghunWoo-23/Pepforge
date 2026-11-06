<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge icon" width="150">

# Pepforge

### Modified-peptide design, molecular structures, ensemble docking, thermodynamic workflows, and SPPS planning

**Pepforge V6.0.0 · Public Research Source Release**

[![Release](https://img.shields.io/badge/release-V6.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/desktop-Windows-0078D4?style=for-the-badge)](#quick-start)
[![Status](https://img.shields.io/badge/status-research%20source-64748B?style=for-the-badge)](docs/RELEASE_STATUS_V6.0.0.md)

**[한국어](README_KO.md) · [Quick start](#quick-start) · [Capabilities](#capabilities) · [Structure & Docking](#structure--docking-studio) · [Modified peptides](#modified-peptide-chemistry) · [SPPS Planner](#spps-planner-v800) · [Verification](#verification) · [Manual](MANUAL_EN.md)**

</div>

---

## Overview

**Pepforge** is a Windows-first desktop research workbench for connecting peptide design, chemical structure preparation, protein–peptide docking, interaction review, and synthesis planning. V6.0.0 expands the V5 Structure & Docking Studio workflow with supported modified-peptide conformers, ensemble docking, optional physics/MD and ABFE tooling, and the original **SPPS Planner V8.0.0 (Public)** launched in a normal separate window.

> **Core scientific rule:** Computational hypotheses, internal docking scores, simulation-derived estimates, and experimental evidence must remain clearly distinguishable.

```text
Target sequence / experimental or predicted receptor structure
                         ↓
                   Hot Spot Finder
                         ↓
                Peptide Design Engine
                         ↓
              Structure & Docking Studio
          ├─ supported modified-peptide chemistry
          ├─ conformer generation / MMFF94s screening
          ├─ receptor & peptide file preparation
          ├─ native / conformer-ensemble docking
          ├─ interaction evidence & interface refinement
          └─ optional MD / ABFE / PyMOL review
                         ↓
           SPPS Planner V8.0.0 (Public)
                         ↓
         Evidence export / experimental validation
```

Generated conformers and docking poses are **testable structural hypotheses**, not proof of a native conformation, experimental binding affinity, or biological effect.

---

## Capabilities

| Module | Public V6.0.0 scope |
| --- | --- |
| **Workflow Mode** | Target → hotspot → design → structure/docking → synthesis-planning hand-off |
| **Hot Spot Finder** | Target sequence/structure review and candidate region screening |
| **Peptide Design Engine (PDE)** | Candidate generation, design objectives, sequence/chemistry-aware handling |
| **Structure & Docking Studio** | Structure preparation, conformers, native docking, interaction evidence, optional analyses |
| **Modified-peptide tools** | Supported D-residue, non-natural residue, terminal modification, linker and tag handling with explicit unsupported states |
| **Ensemble / torsion workflows** | RDKit/MMFF94s conformer sampling, diversity screening, candidate-wise geometric docking |
| **Scientific backends (optional)** | OpenMM/OpenFE/OpenFF/GAFF/PyMBAR installation helpers and selected MD/ABFE execution/audit entry points |
| **PyMOL review (optional)** | Structures, token-to-residue mapping, optional separate full-token panel |
| **SPPS Planner V8.0.0** | Original V8 Project/Batch/Materials/Cleavage UI launched in its own desktop window from Pepforge |
| **Benchmark & provenance** | Receptor-aligned pose RMSD, family-aware summaries, output hashes and audit utilities |

### PDE design objectives

- Interaction Only
- Interaction First
- Balanced
- Structure Guided
- Structure Exploration

Structure-guided modes require meaningful structural inputs; missing target structures are not silently treated as a reliable predicted fold.

---

## Structure & Docking Studio

In the **Docking & Simulation** tab, molecular inputs are arranged as **Receptor (source → PDB/mmCIF → sequence)** followed by **Peptide (source → PDB/mmCIF/SDF/MOL → sequence)**; docking settings are below them. The peptide sequence is shared with Structure Builder and persists across tab switches. Each Studio tab remains within the **same Studio window**.

The primary V6 workflow retains V5's unified structure/docking workspace and extends its *optional* modified-peptide and research execution routes.

### Structure generation and conformer review

Supported exploratory conformational families, where chemically applicable, include **α-helix, 3₁₀-helix, β-extended, β-hairpin-like, PPII, turns, and coil/mixed**. Additional tools generate multiple 3D conformers with ETKDG and MMFF94s where parameters are available, then screen energy, convergence, stereochemistry, and structural diversity.

**Important:** A low MMFF94s conformer energy is not a protein-binding ΔG and is not a calibrated population estimate.

### Native, ensemble, and interface docking

The public source contains pathways for:

- protein/receptor structure files (including preparation from PDB/mmCIF where supported);
- peptide structure files including supported PDB/mmCIF and SDF/MOL inputs;
- blind, manual, and hotspot-guided native pose search;
- multiple candidate conformers and torsion-sampled ensemble search;
- clash/contact inspection, ranked pose hypotheses, and receptor-conditioned interface refinement;
- receptor-aligned peptide RMSD and audit-ready manifests.

The native docking score is an **internal, dimensionless structural-screening score**. It is **not** ΔG_bind, Kd, an experimental affinity, or biological activity. Conformer-wise docking and empirical interface refinement do not establish validated simultaneous receptor/peptide flexibility.

### Interaction analysis

The geometry-based evidence layer can inspect supported candidates for hydrogen bonds, hydrophobic contacts, salt bridges, aromatic interactions (π–π/cation–π), van der Waals contacts/clashes, disulfide geometry, water-mediated contacts, metal coordination, halogen bonds and other specialized contact geometries. These are **screening signals, not measured interaction energies**.

---

### Tabbed Studio workspace (V6.0.0)

The Studio now uses **three tabs within the same window**, rather than one long scrollable page:

| Tab | Main actions |
| --- | --- |
| **1. Structure Builder** | Sequence, conditions, conformer generation, token map and output |
| **2. Docking & Simulation** | Receptor selection, binding site, docking/ensemble settings, optional mechanics and MD |
| **3. Results & Analysis** | Chemistry table, conformer evidence, shared native docking result viewer |

Switch by clicking a tab or using `Ctrl+1`, `Ctrl+2`, or `Ctrl+3`. Each tab scrolls separately; values persist across tabs. No extra top-level windows are opened when changing Studio tabs; all form state is shared. Analysis automatically selects the Results tab in the same window. Explanatory paragraphs have moved to this README and `MANUAL_EN.md`.

## Modified-peptide chemistry

Pepforge distinguishes registered terminal modifications, residue identities, stereochemistry, tags, and linkers when supported. Examples of **notation**, not guarantees of all-atom force-field coverage:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

| Construct component | Treatment |
| --- | --- |
| `Ac-`, `Pal-` | Explicit N-terminal modification notation when registered |
| D-form residue (e.g. `dK`) | Stereochemical identity preserved/checked where structure generation is supported |
| Aib / Dab / other non-natural residue | Explicit token with stage-specific structure and parameter support |
| AEEA / Ahx / PEG linkers | Registered linker components when available |
| FITC / Biotin / chemical tags | Distinct chemical tokens; structural support must be checked per construct |

A token can be **parsed successfully** while still lacking validated 3D coordinates or force-field parameters. Pepforge must not fabricate unsupported atom types, charges, parameters, or stereochemical assignments.

### PyMOL visualization

Structure exports can include residue/token mapping information. An optional PyMOL **separate chemical-token panel** displays full labels and assists residue selection. This is *not* a patch that makes PyMOL's native sequence strip support arbitrary-length labels. Verify the optional panel against your installed PyMOL distribution.

---

## Optional molecular dynamics and ABFE research workflows

Pepforge includes source integrations, installation helpers, and auditing utilities for supported OpenMM/OpenFE/OpenFF/GAFF/PyMBAR workflows. The preferred ABFE pathway uses an **OpenFE complete protocol**; manually calculated Boresch restraint corrections must **not** be added again to the completed OpenFE result.

| Task | Scope and boundary |
| --- | --- |
| MMFF94s conformer evaluation | Internal peptide force-field minimization where parameterized |
| GAFF/OpenMM complex preparation | Optional protocol pathway; chemistry and execution environment require validation |
| Solvated MD | Optional execution and trajectory/log-quality analysis tools |
| OpenFE ABFE | Optional transformation creation and execution/audit bridge, not a benchmark-certified predictor |
| Boresch / MBAR / replica checks | Protocol-aware correction and uncertainty analysis of genuine simulation data |
| Experimental comparison | Compare traceable computed ΔG_bind with independently supplied Kd data; does not create experimental evidence |

**Do not interpret:** an ABFE JSON file, completed trajectory, low internal docking score, or software unit-test pass as proof of converged binding free energy. Modified-peptide parameterization and independent replicate/experimental validation must be demonstrated on the actual system.

See [scientific release status](docs/RELEASE_STATUS_V6.0.0.md) and [science-engine installation guide](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md).

---

## SPPS Planner V8.0.0

**Normal SPPS Planner V8 window:** In the Pepforge main launcher, select **4 · SPPS Planner** and click **Open SPPS Planner**. The original V8 Public GUI opens in a **normal independent desktop window**, just like PDE or Structure Builder. This avoids cross-process Windows `SetParent` limitations (window focus, modal dialogs and DPI). Pepforge stays available for other work; saving and closing the Planner follows V8's native Project Manager workflow.

The bundled V8 retains Project Manager, Batch Manager, Plan, Materials, Checklist, Cleavage, Sequence Risk, and Recommendations & Lab History. Removed redundant shortcuts (Loading Advice / Cleavage Advice / Record Lab Data) are not re-added. The original calculation engine is not modified.

**Source:** `python -m pip install -r vendor/spps_planner_v8/requirements.txt`, then `python main_launcher.py` → **SPPS Planner** → **Open**, or `python main_launcher.py --tool spps`. Source and packaged startup errors are logged to the Pepforge launcher log `spps_v8_launch.log`.

**Installed Windows build:** The unified builder must include `SPPS_Planner/SPPS_Planner.exe` alongside `Pepforge.exe` inside the installation directory; the frozen Pepforge executable is not itself a Python interpreter. Keep the full installer folder. Only Pepforge is V6.0.0; SPPS Planner retains its own V8.0.0 version.

**Scientific boundary:** SPPS results are decision support, not guaranteed yield or purity.

The planner supports laboratory planning and decision making, **not guaranteed yield, purity, reaction completion, or cleavage success**. [V8 integration notes (KO)](SPPS_V8_INTEGRATION_README_KO.md).

### V8 Recommendations / Plan Treeview style isolation

The bundled **SPPS Planner V8.0.0** has been refreshed from the latest supplied **Treeview Style Fixed** source. When **Recommendations & Lab History** is opened, its tables use the namespaced `SPPS.History.Treeview` and `SPPS.History.Treeview.Heading` styles, rather than changing Tk's global `Treeview` styles. This preserves the **bold Project Manager Plan/Materials headings** and the main table row height when switching between panels. The original V8 planning calculations and Project/Batch flows remain unchanged.

To verify the fix on a computer with Tk/display support, run the vendored test from its own directory (do not accidentally import Pepforge's `suite_gui` module):

```bat
cd vendor\spps_planner_v8
python -m pytest -q tests/test_v8_recommendations_style_isolation.py
```

If running from source, install the SPPS requirements and test dependency `pytest` first. An automated Treeview-style check is not a substitute for inspecting the actual Windows GUI at 100%, 125%, and 150% scaling.

---

## Benchmark, provenance, and evidence

Tools include public-data provenance, receptor alignment, structural RMSD, candidate screening, family-aware bootstrap summaries, leakage/split auditing, SHA-256 input-output records, and explicit error/incomplete states.

**Reproducible evaluation infrastructure is not equivalent to independently demonstrated accuracy.** Independent public benchmark execution and experimental ΔG_bind accuracy for this integrated release have not been certified.

---

## Quick start

### Requirements

- **Windows 10/11** recommended for desktop usage; Python **3.10+** and Tk support.
- Install the core packages in [`requirements.txt`](requirements.txt). RDKit is used for supported 3D chemistry workflows.
- Scientific backends may require compatible versions beyond the core environment; OpenFE on Windows is intended for a **WSL2/Linux** science environment.
- PyMOL is optional and installed separately. No dedicated GPU is required for CPU-compatible core paths.

### Launch from source (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

Or double-click `RUN_PEPFORGE_SOURCE.bat` after dependencies are installed. For a specific workspace:

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool docking
python main_launcher.py --tool spps
python main_launcher.py --tool workflow
```

### One-entry Windows build and optional science setup

Double-click `INSTALL_BUILD_TOOLS_AND_BUILD.bat` and select a mode:

| Menu | Action |
| --- | --- |
| **1 — Windows build** | Builds the Pepforge EXE and Inno Setup installer. Does not install science engines. |
| **2 — Build + Science** | Builds the Windows installer, provisions missing WSL Ubuntu/Miniforge when possible, then installs / verifies the science stack. |
| **3 — Science only** | Sets up missing WSL Ubuntu/Miniforge when possible, then installs or updates `pepforge-science`. |
| **4 — Verify** | Verifies scientific imports and the OpenFE CLI without downloading packages. |
| **5 — Exit** | Closes the menu. |

Scripted options: `--build`, `--all`, `--science`, `--verify-science`. **Ubuntu and Miniforge are now bootstrapped when missing** after the user selects science installation (menu 2 or 3). The installer invokes `wsl --install -d Ubuntu` only for an explicitly selected install; Windows administrator approval, a reboot and first-launch Linux user creation may require manual action. On rerun, missing Miniforge is downloaded from conda-forge with a pinned SHA-256 check before science packages are installed. Verification-only mode never installs. Failures are never reported as success. OpenFE remains in Linux and is **not** bundled into the Windows EXE. See [science setup](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md).

SPPS V8 separate window from source: install `vendor/spps_planner_v8/requirements.txt`, run `python main_launcher.py`, select **SPPS Planner** and click **Open**. Direct launch: `python main_launcher.py --tool spps`. When bundled as an EXE, keep the full `dist/Pepforge/` folder; the `SPPS_Planner/SPPS_Planner.exe` companion is required. Launch failures are recorded in `workspace/launcher/logs/spps_v8_launch.log` (source mode), or under the user-local Pepforge launcher log directory (installed mode).

### Selected research CLI entry points

```bat
python RUN_MODIFIED_PEPTIDE_FF.py --help
python RUN_ENSEMBLE_DOCKING.py --help
python RUN_RELEASE_READINESS.py --help
python RUN_ABFE_EXPERIMENTAL_VALIDATION.py --help
```

Refer to [English manual](MANUAL_EN.md) and [한국어 매뉴얼](MANUAL_KO.md) for tool-specific inputs.

---

## Verification

**Research-source verification remains bounded.** The V6.0.0 installer, version, SPPS V8 hand-off and packaging contracts have been checked; the full test suite and actual Windows/WSL2 installations have **not** been certified.

| Check | Verified result |
| --- | --- |
| Focused installer / release / SPPS compatibility tests | **41 passed / 0 failed** (2026-10-28 focused regression) |
| Pepforge release gate | **25 / 25 passed** (2026-10-27) |
| Python compile via release gate | **780 files / 0 compile errors** |
| Static V6 packaging and document inventory | **Passed** (source-only checks) |
| Complete Pepforge regression | **Not completed**; extended run stopped before full completion |
| Native Windows GUI / installer and WSL2 package installation | **Not verified on an actual target PC** |
| OpenFE production ABFE and experimental ΔG_bind accuracy | **Not verified** |

Historical V3 menu-label mismatch has been addressed in the legacy compatibility route, but **this is not equivalent to completion of the full regression suite**.

Run local validation on your target environment:

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Passing these checks establishes only their respective test coverage. See [release status](docs/RELEASE_STATUS_V6.0.0.md) and [publication checklist](PUBLICATION_CHECKLIST.md).

---

## Scientific scope and limitations

Intended for **research prioritization, computational preparation, conformer hypotheses, docking/interaction screening, synthesis planning, and validation hand-off**.

Output alone does **not** establish experimental Kd/Ki, validated binding free energy, native in-vivo conformation, biological efficacy, reaction yield/purity, or production MD convergence. ESMFold/AF3-class accuracy and superiority over other docking engines are **not claimed**.

For confidential targets and unpublished chemistry, check whether selected external structure-prediction or service integrations transmit sequence data before enabling them.

---

## Repository layout

```text
Pepforge_V6.0.0/
├─ main_launcher.py             # desktop entry point
├─ pepforge_cli.py             # workflow and verification CLI
├─ suite_gui/                  # integrated GUIs
├─ peptiforg_core/             # calculation, provenance and audits
├─ pepforge_structure_tool/    # structure-related tools
├─ apps/                       # hotspot, PDE, compatibility modules
├─ vendor/spps_planner_v8/     # SPPS Planner V8.0.0 Public (separate module)
├─ tests/                      # automated checks
├─ docs/                       # technical references and policies
├─ installer/                  # build/installer support
├─ README_KO.md
├─ MANUAL_EN.md
├─ MANUAL_KO.md
└─ LICENSE
```

Runtime outputs, experimental data, private records, credentials, and training artifacts must not enter public commits.

---

## Documentation

| File | Description |
| --- | --- |
| [README_KO.md](README_KO.md) | Korean GitHub overview and quick start |
| [MANUAL_EN.md](MANUAL_EN.md) / [MANUAL_KO.md](MANUAL_KO.md) | Detailed workflow and usage references |
| [SPPS V8 integration guide](SPPS_V8_INTEGRATION_README_KO.md) | Public planner process and version boundary |
| [Scientific installation guide](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md) | WSL2/Linux optional OpenFE/OpenMM science stack |
| [Scientific release status](docs/RELEASE_STATUS_V6.0.0.md) | Supported/unsupported and unverified claims |
| [Public data policy](PUBLIC_DATA_POLICY.md) | Sensitive-data exclusion from GitHub |
| [Publication checklist](PUBLICATION_CHECKLIST.md) | Repository-owner release review |
| [Changelog](CHANGELOG.md) | Version history |

---

## Citation and license

If Pepforge or a Pepforge-derived workflow materially contributes to academic work, cite the **exact release used**, as applicable. GitHub citation metadata is provided in [`CITATION.cff`](CITATION.cff).

> Woo, S. *Pepforge: An Integrated Peptide Research Workbench*. V6.0.0 (source release candidate), 2026. https://github.com/SanghunWoo-23/Pepforge

**License:** [Pepforge Public Academic Citation License](LICENSE) (custom source-available license; **not** an OSI-approved open-source license). Embedded third-party components have their own notices; review them before redistribution. This documentation edit is not a licensing or redistribution clearance.

For bug reports, provide the Pepforge version, OS, Python version, minimal *nonconfidential* input, and redacted logs. See [CONTRIBUTING](CONTRIBUTING.md) and [SECURITY](SECURITY.md).

---

<div align="center">

**Pepforge V6.0.0**  
*From modified-peptide design to structures, docking hypotheses, thermodynamic analysis, SPPS Planner V8.0.0, and validation hand-off.*

</div>


## V6.0.0 native docking input and results update (2026-10-30)

- **Receptor file input** accepts `.pdb`, `.cif`, and `.mmcif`. mmCIF is converted into a validated PDB coordinate adapter with Biopython; Gemmi is available as a fallback. Preserve the original mmCIF as the authoritative source. Check chain identifiers, alternate conformers, ligands, and atom coverage after conversion.
- **Peptide file input** accepts PDB, mmCIF, SDF, or MOL when suitable 3D coordinates are present. Structure Builder and Docking tabs share the modified-peptide sequence.
- **BUILD + DOCK + ANALYZE** uses the native rigid-body docking engine for direct file inputs. The Docking tab reports real search-trial completion (not an estimated MD duration); the Results & Analysis tab now loads verified poses and geometric interaction evidence. Failed/no-pose runs display an explicit error rather than a success message.
- **Native Results toolbar** displays the essentials (results, selected pose, 3D review, export, interpretation). A/B comparison, advanced filters, pose matrix and selected follow-up remain available behind **Advanced tools**.
- **Progress bars:** known completed stages and native-search iteration counts fill a left-to-right bar. Operations without stage telemetry do **not** claim a fabricated percent-complete or ETA.
- **What is verified:** automated native-docking PDB/mmCIF tests and a Tk GUI smoke run in a Linux virtual display with generated test structures. **What is not verified:** every user-supplied PDB/mmCIF, Windows installer/EXE, force-field validity, experimental affinity, OpenMM/ABFE performance, or full project regression.

See [MANUAL_EN.md](MANUAL_EN.md) for use and troubleshooting.
