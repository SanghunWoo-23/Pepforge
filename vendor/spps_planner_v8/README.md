<div align="center">

<img src="assets/SPPS_Planner_Icon.png" alt="SPPS Planner" width="150">

# SPPS Planner V8.0.0

**Windows-first solid-phase peptide synthesis planning, calculation and evidence-aware laboratory decision support**

Project Manager · Optional Auto Plan · Sequence Risk Map · Editable Plan · Materials · Checklist · Batch Manager · Loading/Cleavage Recommendations · Workup · Laboratory History

[![Version](https://img.shields.io/badge/release-V8.0.0-2563EB?style=for-the-badge)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#quick-start)

**[한국어 README](README_KO.md) · [English manual](docs/USER_MANUAL_EN.md) · [한국어 매뉴얼](docs/USER_MANUAL_KO.md)**

**Repository:** [SanghunWoo-23/SPPS-PLANNER](https://github.com/SanghunWoo-23/SPPS-PLANNER)

</div>

> **Release: V8.0.0 PUBLIC SOURCE.** This ZIP contains source code and Windows build entry points, **not** a prebuilt EXE/Installer. Native Windows GUI, installer, upgrade and uninstall acceptance tests have **not** been completed in this environment.

## Overview

SPPS Planner prepares reviewable, editable solid-phase peptide synthesis plans. **Project Manager** remains the starting point and the existing chemistry engine remains the calculation authority. V8 adds optional confirmation-based Auto Plan, sequence risk explanations, improved evidence-aware Loading/Cleavage summaries, scrollable recommendation pages and safer project persistence. This is a planning tool, **not** an autonomous experiment optimizer or validated synthesis protocol.

```text
Project Manager → Add / Edit peptide
     ↓
Sequence + Scale + Copies + Resin + Loading + Exact bottles
     ↓
Generate   OR   Auto Plan (Optional) → Review → Generate Full Plan
     ↓
Plan ─── Materials ─── Checklist ─── Total Materials
  └──── Cleavage Cocktail ─── Workup
     ↓
Sequence Risk Map / Loading & Cleavage Recommendations / History
     ↓
Batch Manager · Export · Operator Review · Experimental Validation
```

## Highlights — V8.0.0

### Optional Auto Plan (not automatic protocol optimization)

The **Auto Plan (Optional)** action previews the *existing* sequence and setup — peptide identity, scale, copies, resin, loading, coupling chemistry and theoretical resin demand. It does not modify settings by merely opening the preview. **Generate Full Plan** confirms the setup and invokes the existing engine. Invalid or missing setup fields still require operator attention. The program does **not** establish optimal cleavage cocktail/time, chemical yields or success probabilities from a peptide sequence alone.

### Cleaner Project Manager toolbar

The Project Manager actions run **Generate → Apply Change → Auto Plan (Optional) → Recommendations & Lab History → Sequence Risk Map → Save Session Now**. Auto Plan is placed **immediately after Apply Change** and uses the same blue primary-button treatment as Generate. The former Loading Advice, Cleavage Advice, and Record Lab Data shortcuts were removed **from this toolbar only**: their functionality remains in **Recommendations & Lab History** (Recommendations → Loading/Cleavage; Advanced → History). No experimental data were deleted.

The **Recommendations & Lab History** toolbar follows the experiment lifecycle: **Preflight → Start Experiment → Add Result → Add Issue → Final Result → Finish → Repeat Run**. The maintenance actions (**Refresh → Data Store → Backup DB**) follow at the end. Add Issue is available when an issue occurs; it is not a required step in every run. Actual measurement records are linked to the frozen Run context once an experiment has started.

### Project Manager / Batch Manager

- Project and peptide identity, sequence, scale, copies, resin/loading, LOT tracking, coupling reagent/activator, additive/catalyst, base and solvent.
- Exact bottle setup and local **My Recipes** (save, load, rename, delete, favorite, backup/import and recent selections).
- Editable Plan and existing **Generate / Apply Change** behavior, with connected Materials, Checklist, Total Materials, Cleavage and Workup calculations.
- Batch Manager uses visible batch-preparation defaults; Project Manager's individual bottle selections do not silently overwrite them.

### Chemistry and cleavage/workup planning

- **2-CTC direct loading default:** resin **1 eq**, amino acid **2 eq**, DIEA **4 eq**. Disable this option for already-loaded resin. Other resins must not silently inherit it.
- Resin-specific, operator-editable process settings remain controlled by the existing engine and UI.
- Cleavage material calculations follow existing sequence and Cys-related rules, with separate accounting for cocktail and post-cleavage workup.
- Workup: ethyl ether, n-hexane, ether/n-hexane 1:1 or custom volume. Chemistry calculations are **not** promises of reaction completion.
- **NMM** (N-methylmorpholine, base) is distinct from **NMP** (N-methyl-2-pyrrolidone, solvent).

### Sequence Risk Map and Recommendation & Lab History

- Position-based rule findings, severity and rule descriptions; **not** a calibrated prediction of synthesis failure.
- Loading and Cleavage recommendation summaries emphasize suggested/available conditions, evidence class, applicability, and uncertainty.
- Chemistry defaults, operator anchors and experimental observations are distinct. Insufficient evidence remains insufficient; applying conditions still requires operator approval.
- Recommendation pages provide vertical scrolling and mouse-wheel/scrollbar-drag support; the primary Tkinter Step 1/Step 2 interfaces are retained.
- **Stable Plan-table headings:** opening the recommendation window no longer changes the global Tkinter Treeview font; Plan column headers remain bold.

### Storage and release hygiene

- Project JSON structure validation, atomic save, last-good backups and conflict checks reduce common accidental data loss.
- No guarantee against all simultaneous edits, power failure, OneDrive/cloud conflicts, antivirus interference or device-specific failures.
- Public and Private have distinct default runtime-data profiles. **This Public ZIP must not include Private experimental seed files, confidential sequences, user project/recipe history, or runtime databases.** Manual imports remain the operator's responsibility. See [PUBLIC_DATA_POLICY.md](PUBLIC_DATA_POLICY.md).

## Quick start

**Target:** Windows 10/11, 64-bit Python 3.11 or 3.12 with Tk support.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

### One-click Windows build — one BAT file

Extract the **complete** source ZIP on Windows 10/11, then double-click `INSTALL_BUILD_TOOLS_AND_BUILD.bat` (or run it with `--no-pause` for an unattended console session).

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

The script detects **64-bit Python 3.11/3.12** and **Inno Setup 6/7** and attempts to install missing tools with `winget`; installs Python dependencies, checks the V8 release contract, builds the EXE, runs packaged self-tests, builds the Installer, and checks the resulting files. Internet access and appropriate installation permissions may be needed. If `winget` is unavailable, install the tools manually and retry.

Expected outputs:

- `dist\SPPS_Planner\SPPS_Planner.exe` — application executable (keep the complete `dist\SPPS_Planner` directory for portable use).
- `installer\output\SPPS_Planner_Setup_V8.0.0.exe` — Windows Installer.

**The BAT builds the Installer; it does not install the application. No prebuilt EXE/Installer is bundled in this source ZIP.** Native Windows GUI use, upgrade/uninstall and installation behavior remain subject to real Windows acceptance testing. See [Windows build guide](docs/WINDOWS_BUILD_KO.md).

### Test from source

```bat
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python tools\verify_windows_release.py
```

## Lean release package — what stays and why

- **1 BAT file:** `INSTALL_BUILD_TOOLS_AND_BUILD.bat` consolidates tool preparation, EXE/Installer builds, self-tests, and artifact verification. The split build scripts have been removed.
- **2 root version labels** (`VERSION`, `VERSION.txt`) are intentionally retained because current application/build verifiers and PyInstaller resources consume them independently.
- **Internal `SPPS data v6.0.0` schema identifier** is retained for backward compatibility with stored data; it is not the V8.0.0 application release version.
- **`requirements.txt` / `requirements-dev.txt`:** runtime/build dependencies and source-test dependencies.
- **`installer/version_info.txt`:** PyInstaller Windows executable version resource; it is code-like build metadata, **not** a disposable note.
- **`apps/spps_planner_app/requirements.txt`:** separate optional subapplication dependency list, not a duplicate of the desktop requirements.
- **`RELEASE_NOTES_V8.0.0.txt`:** a single concise source-package release note; GitHub asset SHA-256 is published separately because it changes whenever the archive is rebuilt.
- Archived Beta/V7 development reports and duplicate package-cover notes are **not** shipped. Code, tests, manuals, build configuration, licenses and required reference data stay intact.

## Verification / limitations

See `RELEASE_NOTES_V8.0.0.txt` for the **current source regression result** and the explicit unverified Windows items. Headless pytest or static release checks are not equivalent to GUI acceptance, successful native EXE packaging, Installer deployment or laboratory experimental validation.

SPPS Planner does not replace approved SOPs, SDS and safety rules, trained operator review, validated analytical methods, or GMP/GLP documentation. Outputs do not establish yield, purity, coupling completion, cleavage success, optimized processing conditions, or biological activity.

## Development and release handover

For future development, README and GitHub Release drafting standards, tests, data boundaries, and packaging checks, see [Development handover (KO)](docs/DEVELOPMENT_HANDOVER_V8.0.0.md). This document supplements the user manuals.

## Documentation and citation

[English manual](docs/USER_MANUAL_EN.md) · [한국어 매뉴얼](docs/USER_MANUAL_KO.md) · [Architecture](docs/ARCHITECTURE.md) · [Windows build guide](docs/WINDOWS_BUILD_KO.md) · [Public data policy](PUBLIC_DATA_POLICY.md)

See [LICENSE](LICENSE) for the **custom academic-citation license** (not an OSI-approved open-source license) and [CITATION.cff](CITATION.cff) for citation metadata. Suggested citation: **Woo, S. SPPS Planner: Solid-Phase Peptide Synthesis Planning and Evidence-Driven Decision Support. V8.0.0 (2026).** https://github.com/SanghunWoo-23/SPPS-PLANNER
