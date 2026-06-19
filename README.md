# Pepforge Public Research Release v2.0.0

**Integrated peptide research workbench for hotspot analysis, peptide design, SPPS planning, modified-peptide structure generation, docking-oriented screening, external validation bridging, and publication-oriented evidence reporting.**

**Current release:** `v2.0.0`  
**Author:** Sanghun Woo  
**Repository:** `https://github.com/poowsh1407/Pepforge`  
**Status:** public research package; screening/planning/bridge workflow; not a replacement for experimental validation.

---

## 1. Purpose

Pepforge was built to connect peptide discovery and peptide production tasks that are often handled in separate spreadsheets, scripts, molecular viewers, and docking/MD packages. The v2.0.0 line consolidates the stabilized desktop workflow into a GitHub-ready upgrade package. It keeps the previous v4.2.x functionality while introducing a clearer version baseline, normalized SPPS reagent data, improved Docking Workbench data visibility, and safer modified-peptide bridge exports.

The package is intended for research planning and prioritization. It helps users answer practical questions such as:

- Which peptide regions or motifs should be prioritized from sequence/target information?
- Can a peptide candidate be represented with SPPS-aware tokens such as D-amino acids, linkers, labels, caps, or terminal amides?
- What synthesis plan, material usage table, and checklist are implied by the notation?
- Can a modified peptide be exported to PyMOL-readable SDF/PDB/PML files?
- What screening-level target, contact, affinity-style, and MD-style summary data can be organized before external validation?
- Which files should be passed to external tools such as PRODIGY-like analysis, AutoDock-family docking tools, or GROMACS/OpenMM/AMBER-style MD workflows?

---

## 2. What is new in v2.0.0

v2.0.0 should be treated as the new public baseline after the v4.2.x stabilization branch.

### 2.1 SPPS Planner stabilization

- Terminal last-wash logic is corrected.
- Last deprotection and final terminal chemical/label/tag/cap coupling now proceed to final wash only:

```text
final wash DMF x3
final wash DCM x3
```

- The redundant final `post-coupling wash DMF x2` row has been removed from the last reaction context.
- Linkers such as `Ahx`, `AEEA`, `PEG`, and related linker tokens are treated as amino-acid-like coupling units.
- Labels, dyes, tags, caps, and terminal chemicals are treated as chemical modifiers.
- `Ac` uses separated reagent and final product contribution masses.
- Compound database handling separates `Reagent MW` from `Product MW contribution`.
- Liquid density is applied only to liquid reagents; solid reagents remain density-free.
- Ambiguous vendor forms are marked as manual-required rather than assigned false precision.

### 2.2 Compound database normalization

The v2.0.0 package includes the normalized compound database located at:

```text
apps/spps_planner_app/data/compounds.csv
```

Current active token count: **212**  
Manual-required active tokens: **38**  
Active tokens with blank reagent MW: **85**  
Active tokens with blank product contribution: **37**

Blank values are intentional when the exact vendor form is not determined. For example, generic labels such as `FAM`, `TAMRA`, `CY5`, and `DOTA` can represent different acid/NHS/protected/salt forms. Pepforge therefore prefers form-specific rows such as `5-FAM`, `6-FAM`, `FAM-NHS`, `DOTA-NHS`, or user-added vendor-specific rows.

Important examples:

| Token | Reagent MW use | Product contribution use | Notes |
|---|---:|---:|---|
| `Ac` | 102.09 g/mol for acetic anhydride usage | 42.04 Da acetyl contribution | reagent/product masses separated |
| `Caf` | 180.16 g/mol caffeic acid | 162.14 Da caffeoyl residue | corrected from conflicting older value |
| `Gal` | Gallic acid row | galloyl-type contribution | check vendor form if protected/activated |
| `Pal` | palmitic acid/palmitoyl form | palmitoyl cap contribution | N-terminal lipid cap handling |
| `Ahx`, `AEEA` | linker reagent row | AA-like linker contribution | treated as coupling units |
| generic dyes/tags | manual-required when form is ambiguous | sequence/product contribution may be available | avoid false material calculations |

### 2.3 Docking Workbench completion

- The Input section can be collapsed or expanded to recover vertical screen space.
- Target summary visibility is improved; fallback rows are shown instead of empty panes.
- Full-data buttons are provided in a SPPS Planner-like style:

```text
Input data full
Results data full
MD data full
```

- Results now expose PRODIGY-like, GROMACS-like, and MD-style summary tables for comparison and reporting.
- These summaries are evidence-organization outputs, not final measured binding constants.
- Export includes external-style validation summaries for downstream review.

### 2.4 PyMOL Structure Builder and Bridge workflow

- Modified-peptide Build SDF/PDB/PML remains the primary structure export path.
- Bridge buttons are treated as hand-off package generators rather than hidden external docking/MD executors.
- Quick-safe bridge export reuses existing Build outputs instead of repeating heavy structure generation.
- Bridge packages can include token maps, parameter requirement checklists, docking config templates, MD import schemas, and publication/reporting summaries.
- Alias handling is improved for case-insensitive input such as `pal`, `PAL`, `Palmitic acid`, `caf`, `Caffeic acid`, `gal`, and `Gallic acid`.

---

## 3. Scope boundary and safe interpretation

Pepforge is a **planning, screening, bridge-export, and evidence-reporting tool**.

It does **not** claim to replace:

- experimental Kd/IC50/EC50 measurement,
- synthesis QC,
- final prep-HPLC/MS analysis,
- AutoDock Vina/Smina/Gnina execution,
- PRODIGY server/tool execution,
- GROMACS/OpenMM/AMBER/NAMD production MD,
- publication-grade all-atom validation.

Recommended wording:

```text
screening-level contact evidence
PRODIGY-like summary field for external comparison
MD-style screening summary
validation bridge package generated
external validation required
```

Avoid wording such as:

```text
Pepforge proves nM binding
Pepforge replaces PRODIGY/GROMACS
Pepforge provides final measured Kd
Pepforge performed publication-grade MD internally
```

---

## 4. Repository layout

```text
Pepforge/
├─ main_launcher.py                         # integrated desktop launcher
├─ pepforge_cli.py                          # command-line utilities
├─ requirements.txt                         # pip dependency list
├─ environment.yml                          # conda environment template
├─ apps/
│  ├─ hotspot_finder/                       # hotspot analysis module
│  ├─ peptide_design_engine/                # peptide design module
│  └─ spps_planner_app/                     # SPPS engine, data, examples
├─ suite_gui/
│  ├─ hotspot_gui.py
│  ├─ spps_tk_gui.py
│  ├─ docking_workbench_gui.py
│  └─ pymol_structure_builder_gui.py
├─ peptiforg_core/                          # shared engines and bridge tools
├─ docs/
│  ├─ user_manual/                       # extended user manuals
│  ├─ data_dictionary/                   # compound/token database policy
│  ├─ pymol_structure_tool/              # structure-builder token/template guides
│  └─ DOCKING_WORKBENCH_USER_GUIDE.md    # docking workbench guide
├─ outputs/                                 # local runtime outputs, gitignored
├─ projects/                                # local project files, gitignored
└─ models/                                  # optional local model files, gitignored
```

---

## 5. Installation

### 5.1 Python source mode

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell/CMD style may vary
pip install --upgrade pip
pip install -r requirements.txt
python main_launcher.py
```

Alternative on Windows:

```bash
RUN_PEPFORGE_SOURCE.bat
```

SPPS Planner only:

```bash
RUN_SPPS_PLANNER_SOURCE.bat
```

### 5.2 Conda mode

```bash
conda env create -f environment.yml
conda activate pepforge
python main_launcher.py
```

### 5.3 CLI check

```bash
python pepforge_cli.py version
python pepforge_cli.py validate-runtime --output-dir outputs/runtime_validation
```

---

## 6. Typical workflow

### 6.1 Modified peptide to SPPS plan

1. Open `SPPS Planner`.
2. Enter a peptide notation, for example:

```text
Ac-EEMQRR-NH2
FITC-Ahx-EEMQRR-NH2
Pal-dG-dH-dK-NH2
Caf-EEMQRR-NH2
```

3. Build/Rebuild.
4. Check Plan, Materials, Project, Checklist, and Log tabs.
5. Confirm terminal wash logic.
6. Export project outputs.

### 6.2 Modified peptide to PyMOL structure

1. Open `PyMOL Structure Builder`.
2. Enter notation such as:

```text
Pal-dG-dH-dK-NH2
Gal-EEMQRR-NH2
Caffeic acid-EEMQRR-NH2
FITC-Cha-AEEA-dK-NH2
```

3. Click Analyze.
4. Click Build SDF/PDB/PML.
5. Open output folder and inspect token map/report.
6. Use Bridge buttons only when preparing hand-off packages for external docking/MD/result import.

### 6.3 Docking-oriented screening

1. Open `Docking Workbench`.
2. Provide target PDB/mmCIF/CIF and peptide sequence/notation.
3. Click Analyze.
4. Collapse Input if the lower tables need more space.
5. Use Input data full / Results data full / MD data full for large tables.
6. Export external-style validation summaries.

---

## 7. Data policy

Pepforge tries to avoid false precision. If a reagent form is ambiguous, the database marks the row as manual-required or leaves the reagent mass blank. This is intentional. Users should add a vendor-specific row using the exact catalog form when using activated dyes, salts, protected derivatives, or proprietary labels.

Recommended additions should be made through:

```text
apps/spps_planner_app/data/new_compound_template.csv
```

or by editing `compounds.csv` with version control.

---

## 8. Citation

If you use Pepforge in a report, thesis, poster, manuscript, internal workflow, or derivative tool, cite the repository and release version.

```text
Woo, S. Pepforge: An Integrated Peptide Research Workbench. Public Research Release v2.0.0. GitHub repository.
```

```bibtex
@software{woo_pepforge_2026,
  author  = {Woo, Sanghun},
  title   = {Pepforge: An Integrated Peptide Research Workbench},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/poowsh1407/Pepforge}
}
```

---

## 9. License and responsibility

See `LICENSE` and `CITATION.cff`. This package is provided for research planning and computational screening. Users are responsible for verifying reagent identity, vendor form, synthesis conditions, purification, analytical confirmation, and external computational validation before making scientific or production claims.
