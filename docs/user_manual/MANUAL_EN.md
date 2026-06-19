# Pepforge v2.0.0 User Manual

## 1. Overview

Pepforge v2.0.0 is a desktop-oriented research package that links five practical peptide workflows:

1. sequence hotspot analysis,
2. SPPS-aware peptide candidate design,
3. production-style SPPS planning,
4. modified-peptide structure generation for PyMOL inspection,
5. docking/MD/external-validation bridge reporting.

The software is organized as a public research workbench. The intended outputs are planning tables, candidate summaries, bridge packages, diagnostic reports, and claim-bounded evidence documents. The software should not be used as the sole basis for biological efficacy, final binding affinity, production release, or clinical/scientific claims.

## 2. Launching the program

### 2.1 Integrated launcher

```bash
python main_launcher.py
```

The launcher opens cards for Hotspot Finder, Peptide Design Engine, SPPS Planner, Docking Workbench, PyMOL Structure Builder, and Workflow Mode.

### 2.2 Windows batch launchers

```text
RUN_PEPFORGE_SOURCE.bat
RUN_SPPS_PLANNER_SOURCE.bat
```

These are intended for source-mode use without building an installer.

### 2.3 CLI utilities

```bash
python pepforge_cli.py version
python pepforge_cli.py validate-runtime --output-dir outputs/runtime_validation
python pepforge_cli.py audit-package --output-dir outputs/package_audit
python pepforge_cli.py release-gate --output-dir outputs/release_gate
```

## 3. Sequence grammar

Pepforge accepts simple amino acid sequences and modified notation. Common examples:

```text
EEMQRR-NH2
Ac-EEMQRR-NH2
FITC-Ahx-EEMQRR-NH2
Biotin-Ahx-EEMQRR-NH2
Pal-dG-dH-dK-NH2
Caf-EEMQRR-NH2
Gal-EEMQRR-NH2
Caffeic acid-EEMQRR-NH2
```

General interpretation:

- uppercase one-letter tokens are standard amino acids,
- `dX` indicates D-form residue where supported,
- `NH2` is a C-terminal amide control token,
- linkers are AA-like coupling units,
- labels/caps/tags/terminal chemicals are chemical modifier units.

## 4. SPPS Planner

### 4.1 Objective

SPPS Planner generates editable production-style synthesis plans, material usage estimates, project metadata, checklists, logs, and transfer/output tables.

### 4.2 Terminal reaction logic

For terminal chemical, label, tag, or cap reactions, v2.0.0 uses this last-stage rule:

```text
final Fmoc removal
DMF wash x6
terminal reaction
final wash DMF x3
final wash DCM x3
```

The previous redundant final `post-coupling wash DMF x2` is removed for the last reaction context.

### 4.3 Linker and label classification

- Linker: amino-acid-like coupling unit. Examples: `Ahx`, `AEEA`, `PEG`, `Cha` when configured as linker/non-natural AA-like unit.
- Label/chemical/tag/cap: chemical modifier. Examples: `Ac`, `Pal`, `Caf`, `Gal`, `FITC`, `FAM`, `Biotin`, `DOTA`, `His6`, `FLAG`, `HA`.

### 4.4 Reagent mass policy

`Reagent MW` is for material usage. `Product MW contribution` is for final peptide mass contribution. These are not the same for many modifiers.

Examples:

- Acetic anhydride reagent MW is not the same as acetyl contribution.
- Caffeic acid reagent MW is not the same as caffeoyl residue contribution.
- Generic dye labels are not reliable unless vendor form is specified.

### 4.5 Adding new compounds

Use:

```text
apps/spps_planner_app/data/new_compound_template.csv
```

Add vendor-specific rows when possible. Do not overwrite generic manual-required rows with vendor-specific values unless the form is unambiguous.

## 5. Docking Workbench

### 5.1 Objective

Docking Workbench organizes target and peptide information, generates target summaries, contact-oriented screening outputs, affinity-style summaries, MD-style tables, and external validation export/import formats.

### 5.2 Input visibility

If the upper Input area occupies too much vertical space, use:

```text
Collapse Input / Expand Input
```

For complete tables, use:

```text
Input data full
Results data full
MD data full
```

### 5.3 PRODIGY/GROMACS/MD-style data

The workbench can show fields such as estimated delta G, estimated Kd, contact counts, clash summaries, RMSD-like imported fields, contact persistence, and external-style validation summaries. These are organized for comparison and reporting. They are not final values unless produced by a validated external workflow and imported with traceable metadata.

## 6. PyMOL Structure Builder

### 6.1 Objective

PyMOL Structure Builder generates SDF/PDB/CIF/PML-style outputs for modified peptide notation.

Recommended workflow:

```text
Analyze
Build SDF/PDB/PML
Open Output
token_map.csv inspection
Bridge export if external validation is needed
```

### 6.2 Bridge concept

Bridge buttons generate hand-off packages. They do not run Vina, PRODIGY, GROMACS, AMBER, or OpenMM by themselves.

Bridge outputs may include:

- token maps,
- diagnostic JSON/TXT/CSV files,
- docking config templates,
- MD parameterization checklists,
- result import schemas,
- publication report fragments.

## 7. Recommended GitHub release procedure

1. Replace the repository contents with this v2.0.0 package or merge with care.
2. Do not commit local outputs, projects, build folders, exe files, or caches.
3. Confirm version:

```bash
python pepforge_cli.py version
```

4. Run a basic validation:

```bash
python pepforge_cli.py validate-runtime --output-dir outputs/runtime_validation
```

5. Commit:

```bash
git add .
git commit -m "Release Pepforge v2.0.0"
git tag v2.0.0
git push origin main --tags
```

## 8. Troubleshooting

- If a modified peptide shows `UNL/HETATM`, inspect structure geometry and token map before treating it as failure.
- If a label mass is blank, check whether the row is manual-required.
- If target summary is hidden, collapse the Input area or open Input data full.
- If Bridge seems to do nothing, first run Build SDF/PDB/PML and inspect bridge package folders.
