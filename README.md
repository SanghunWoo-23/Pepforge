# Pepforge

**An integrated research platform for sequence-guided hotspot analysis, constrained peptide design, and SPPS-oriented synthesis planning**

## Overview

Pepforge is an integrated research software platform designed to support peptide-oriented discovery and synthesis workflows. The program combines three complementary modules within a single desktop environment: Hot Spot Finder, Peptide Design Engine, and SPPS Planner.

Pepforge was developed to connect computational peptide ideation with practical synthetic planning. The platform supports both standalone module execution and workflow-oriented use in which hotspot analysis, peptide candidate generation, and SPPS planning can be connected.

This release is intended as a research-preview and portfolio-oriented open-source edition. It is designed for transparent inspection, local execution, and extension by users working in peptide engineering, biochemical engineering, molecular design, and SPPS process planning.

## Modules

### Hot Spot Finder

Hot Spot Finder performs sequence-based hotspot prioritization. It reports compact residue-index outputs such as:

    (14K), (17Y), (19R)

The number is the 1-based residue position from the N-terminus, and the letter is the amino acid at that position. For local hotspot regions, multiple representative residues may be reported together:

    (158W), (161Y), (163Y), (167R), (168R)

Hotspot scores are relative sequence-derived prioritization scores. They should be interpreted as hypothesis-generating signals, not experimentally validated binding residues.

### Peptide Design Engine

The Peptide Design Engine generates peptide candidates under user-defined constraints. It supports fixed or random length generation, motif constraints, bridge-style constraints, optional D-amino acid handling, optional non-natural amino acids, N-terminal chemistry, labels, tags, linkers, and optional lightweight ML-prior scoring.

Chemistry toggles are explicit. If a system is unchecked, that system is not applied during candidate generation. For example, disabling linker usage prevents linker tokens from being inserted.

Motif constraints enforce sequence fragments such as RGD or EEMQR. Fixed motif placement uses syntax such as:

    RGD@1, EEMQR@4

where positions are counted from the N-terminus using 1-based indexing. Random motif placement enforces motif inclusion while allowing the location to vary.

Linker tokens such as Ahx, AEEA, PEG4, PEG8, G4S, SMCC, and DSS are treated as linker or spacer components, not as default N-terminal modifiers. Amino-acid-like units such as bAla and gAla may be treated as non-natural or amino-acid-like residues rather than linker-only units. N-terminal modifiers include chemical or label-type entries such as Ac, Pal, Myr, Biotin, FITC, and dye labels.

### SPPS Planner

SPPS Planner generates editable C-terminal to N-terminal synthesis plans for solid-phase peptide synthesis. It accepts peptide notation such as:

    Ac-EEMQRR-NH2
    EEMQRR-NH2
    EEMQRR

and parses the N-terminal modifier, core peptide, and C-terminal terminus separately. The parser is designed to correctly recognize the core peptide without requiring an artificial leading dash.

The editable SPPS table uses a unified Unit concept. A Unit may be an amino acid, D-amino acid, non-natural amino acid, chemical modifier, label, tag, or linker. The editable table includes per-row control of unit equivalent, repeat, coupling reagent 1, coupling reagent 2/catalyst, coupling base, deprotection, solvents, and counts.

Core editable fields include:

    Unit name
    Unit eq
    Unit amount
    Coupling reagent 1
    Coupling reagent 1 eq
    Coupling reagent 1 count
    Coupling reagent 2 / catalyst
    Coupling reagent 2 / catalyst eq
    Coupling reagent 2 / catalyst count
    Coupling base
    Coupling base eq
    Coupling base count
    Deprotection base
    Deprotection ratio
    Deprotection count
    Solvent 1
    Solvent 1 count
    Solvent 2
    Solvent 2 count
    Repeat

Usage is calculated from the current editable table state:

    Unit usage = resin scale × unit eq × repeat
    Coupling reagent 1 usage = resin scale × reagent 1 eq × reagent 1 count
    Coupling reagent 2 usage = resin scale × reagent 2 eq × reagent 2 count
    Base usage = resin scale × base eq × base count
    Solvent volume = resin scale × mL per mmol × solvent count

Solid reagents are reported by mass, while liquid reagents and solvents are reported by volume where density information is available.

## Resin-dependent synthesis logic

Pepforge distinguishes broad resin families.

For 2-CTC / trityl-type resin:

    initial Fmoc deprotection is not required
    swell solvent is DCM
    loading is DCM-based
    DIEA/DIPEA is treated as base, not duplicated as coupling reagent

For Wang / Rink Amide / amide-type Fmoc resin:

    initial Fmoc deprotection is required
    default workflow is DMF-based
    C-terminal amide behavior is expected for Rink/amide resins

Intermediate coupling steps primarily use DMF wash logic by default. Final deprotection or final N-terminal chemical/label/modifier coupling is followed by final wash logic such as DMF wash ×3 and DCM wash ×3.

## N-terminal acetylation

N-terminal acetylation is displayed as Ac in the editable synthesis plan. The default reagent used for calculation is:

    Acetic anhydride (Ac2O)
    MW = 102.09 g/mol
    density = 1.08 g/mL

The default volume calculation is:

    Ac2O volume (mL) = resin scale (mmol) × Ac eq × 102.09 / 1000 / 1.08

Ac is not treated as an Fmoc-amino acid coupling step and is not followed by an additional Fmoc deprotection step.

## Material usage and checklist outputs

The Material Usage Table summarizes solid reagent mass, liquid reagent volume, base usage, solvent usage, deprotection solution usage, and modifier usage. The Printable Checklist provides step-level rows for synthesis tracking, including deprotection, coupling, modifier coupling, wash steps, final wash, date, operator, checked status, and notes.

## ML-ready logging

SPPS Planner exports ML-ready logs containing sequence, resin type, loading, scale, unit identity, eq, repeat, coupling reagents, catalyst, base, solvents, deprotection condition, calculated usage, and blank fields for actual yield, purity, LC-MS, HPLC method, and operator notes. These logs are intended to support future modeling of synthesis difficulty, yield, purity, and failure risk.


### Last coupling and final wash logic

The SPPS Planner includes an explicit last coupling step rule. After the last Fmoc-amino acid coupling, the planner schedules DMF wash ×2, followed by final Fmoc deprotection, and then final wash with DMF ×3 and DCM ×3. If a laboratory additionally uses methanol washing, the Final MeOH wash count can be set to 3 to add MeOH ×3.

For final non-Fmoc steps such as Ac, chemical modifiers, labels, or dye attachments, no additional Fmoc deprotection is scheduled after the modifier reaction. Final wash logic is still applied after the final non-Fmoc step.

## Repository Structure

The recommended public GitHub repository structure is shown below. This layout separates the main launcher, module-specific applications, shared GUI components, documentation, tests, examples, installer configuration, and user manuals.

```text
Pepforge/
├── README.md
├── LICENSE
├── requirements.txt
├── environment.yml
├── INSTALL_BUILD_TOOLS_AND_BUILD.bat
├── RUN_SOURCE_DEV.bat
├── main_launcher.py
├── assets/
│   ├── Pepforge_Icon.png
│   └── Pepforge_Icon.ico
├── apps/
│   ├── hotspot_finder/
│   ├── peptide_design_engine/
│   └── spps_planner_app/
├── suite_gui/
├── peptiforg_core/
├── docs/
│   ├── HOTSPOT_METHOD.md
│   ├── PEPTIDE_ENGINE_METHOD.md
│   ├── SPPS_METHOD.md
│   ├── SPPS_PROCESS_RULES.md
│   ├── SPPS_COUPLING_COCKTAIL_RULE.md
│   ├── SPPS_BRANCH_MODE.md
│   ├── INSTALLATION_GUIDE.md
│   └── RELEASE_NOTES.md
├── tests/
│   ├── test_spps_parser_contract.py
│   ├── test_spps_cycle_contract.py
│   └── test_peptide_engine_constraints.py
├── installer/
│   └── Pepforge_Setup.iss
├── examples/
│   ├── example_hotspot_input.txt
│   ├── example_peptide_design_config.csv
│   ├── example_spps_sequence.txt
│   └── example_outputs/
├── MANUAL_KO.txt
├── MANUAL_EN.txt
└── FEATURE_DIFFERENTIATION_ANALYSIS.txt
```

### Directory Description

- `README.md`  
  Main public-facing project document describing Pepforge, its modules, installation, usage, outputs, limitations, and repository structure.

- `LICENSE`  
  Open-source license file for the public research-preview release.

- `requirements.txt`  
  Python package requirements for source-level execution and build preparation.

- `environment.yml`  
  Optional Conda environment definition for users who prefer environment-based installation.

- `INSTALL_BUILD_TOOLS_AND_BUILD.bat`  
  Windows batch script used to install build requirements, build the desktop application, and generate the installer when Inno Setup is available.

- `RUN_SOURCE_DEV.bat`  
  Development-mode script for launching Pepforge directly from source without generating the installer.

- `main_launcher.py`  
  Main desktop launcher for accessing Hot Spot Finder, Peptide Design Engine, and SPPS Planner.

- `assets/`  
  Program icons, visual assets, installer icons, splash-screen resources, and other visual files used by the desktop application.

- `apps/hotspot_finder/`  
  Sequence-based hotspot analysis module.

- `apps/peptide_design_engine/`  
  Peptide candidate generation module with motif, chemistry, constraint, optional ML-prior logic, and SPPS-ready output metadata.

- `apps/spps_planner_app/`  
  Editable SPPS planning module for synthesis step generation, material usage calculation, coupling cocktail handling, branch mode, checklist export, and ML-ready logging.

- `suite_gui/`  
  Shared desktop GUI components and module-level graphical interfaces.

- `peptiforg_core/`  
  Shared core utilities, data structures, and common logic used across modules.

- `docs/`  
  Detailed method notes and technical documentation for each module.

- `tests/`  
  Parser, SPPS cycle, and peptide design constraint tests.

- `installer/`  
  Windows installer configuration files.

- `examples/`  
  Public-safe example inputs and outputs for demonstration.

- `MANUAL_KO.txt` and `MANUAL_EN.txt`  
  Korean and English user manuals.

- `FEATURE_DIFFERENTIATION_ANALYSIS.txt`  
  Comparative analysis describing Pepforge's features, intended use, differences from related tool categories, and limitations.

### Repository Notes

1. The repository structure should match the actual uploaded project as closely as possible.
2. If a listed file does not exist, either create a simple placeholder file or remove that line from the README.
3. Private data, protected beta files, password hashes, API keys, tokens, raw synthesis logs, and internal laboratory records should not be uploaded.
4. The public GitHub repository should use the GitHub Public version, not the Protected Beta version.
5. The Protected Beta version should be used only for internal installer creation and laboratory/team distribution.

## Installation

From the root Pepforge folder, run:

    INSTALL_BUILD_TOOLS_AND_BUILD.bat

The script installs required Python packages, builds the Windows application, detects Inno Setup, and generates a Windows installer.

After a successful build, the installer is generated at:

    installer/output/Pepforge_Setup_v0.1.0.exe

The installer can be distributed to end users. The default installed location is:

    C:\Users\<UserName>\AppData\Local\Programs\Pepforge

Pepforge can be removed through Windows Programs and Features or Windows Settings > Apps.

## Output files

Typical outputs include:

    hotspot_top_display_only.csv
    candidate_results_full.csv
    candidate_results_top.csv
    editable_spps_plan.csv
    material_usage_from_editable_plan.csv
    operation_form_from_editable_plan.csv
    printable_synthesis_checklist.csv
    spps_ml_ready_log_from_editable_plan.csv
    spps_plan.xlsx

## Limitations

Pepforge is intended for research planning, educational use, and workflow prototyping. Sequence-only hotspot results should not be interpreted as experimentally validated binding residues. ML-prior scoring is a ranking aid, not a validated affinity predictor. Chemical calculations must be reviewed by trained users before experimental use. Exact reagent conditions depend on resin type, protecting groups, reagent form, laboratory practice, and safety requirements.

## Author

Woosanghun Woo  
Department of Biochemical Engineering  
Tech University of Korea

## Disclaimer

Pepforge is provided for research, educational, and planning purposes. The software does not guarantee biological activity, binding affinity, synthesis success, purity, yield, or experimental safety. Users are responsible for validating designs, calculations, reagent conditions, and laboratory procedures according to institutional and chemical safety standards.


## Intermediate coupling wash rule

In the SPPS Planner, ordinary intermediate coupling-to-next-coupling transitions use DMF wash x2 by default. DCM wash and optional MeOH wash are treated as final wash or resin-specific operations rather than default washes after every intermediate coupling.


### N-terminal linker restriction

Linker tokens are not allowed to occupy the N-terminal modifier position. N-terminal chemistry is reserved for terminal modifiers or labels such as Ac, Pal, Myr, Biotin, FITC, CY dyes, FAM, or TAMRA. Linker and spacer units such as PEG4, PEG8, Ahx, AEEA, G4S, SMCC, DSS, and related tokens are treated as internal or bridge/spacer elements only. Amino-acid-like units such as bAla and gAla may be used as amino-acid-like residues depending on the selected design settings.
