# Pepforge

**A public research workbench for peptide hotspot analysis, SPPS-aware peptide design, synthesis planning, docking-oriented screening, contact analysis, and molecular dynamics validation bridging**

**Public Research Release 1.0.0**

**Author:** Sanghun Woo  
**Repository:** `https://github.com/poowsh1407/Pepforge`

\---

## Citation Notice

If you use **Pepforge**, Pepforge-generated outputs, or Pepforge-derived workflows in academic work, including papers, theses, posters, presentations, reports, grant materials, or research-derived software, please cite this repository and the corresponding release DOI when available.

Recommended citation:

```text
Woo, S. Pepforge: An Integrated Peptide Research Workbench.
Public Research Release 1.0.0. GitHub repository.
```

BibTeX:

```bibtex
@software{woo\_pepforge\_2026,
  author  = {Woo, Sanghun},
  title   = {Pepforge: An Integrated Peptide Research Workbench},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/poowsh1407/Pepforge}
}
```

Suggested methods sentence:

```text
Peptide candidates and synthesis planning outputs were generated and analyzed using Pepforge, a public research workbench for hotspot analysis, SPPS-aware peptide design, synthesis planning, docking-oriented screening, contact analysis, and molecular dynamics validation bridging.
```

\---

## Overview

**Pepforge** is an integrated research software platform designed to support peptide-oriented discovery and synthesis workflows. It connects sequence-level peptide analysis, peptide candidate design, SPPS-aware synthesis planning, docking-oriented contact screening, and molecular-dynamics validation preparation in a single local desktop workflow.

Pepforge was developed to bridge the gap between computational peptide ideation and practical synthetic planning. Many peptide design tools focus on sequence generation or physicochemical scoring, while many synthesis tools focus only on reagent calculation after a peptide has already been selected. Pepforge is intended to connect these stages so that peptide candidates can be evaluated not only by design score, but also by practical synthesis constraints, terminal modification logic, contact plausibility, and downstream validation readiness.

Pepforge is especially useful for workflows involving:

* canonical L-amino acids,
* D-form residues,
* selected non-natural amino acids,
* linkers and spacer units,
* N-terminal and C-terminal modifications,
* chemical labels and lipid-like moieties,
* SPPS-compatible synthesis logic,
* peptide-target contact interpretation,
* traceable output folders for research documentation,
* exported validation packages for external all-atom MD or experimental follow-up.

This release is intended as a **public research and portfolio-oriented edition**. It is designed for transparent inspection, local execution, extension, and academic citation.

\---

## Core Modules

Pepforge contains four main modules.

1. **Hot Spot Finder**
2. **Peptide Design Engine**
3. **SPPS Planner**
4. **Docking and Molecular Dynamics Workbench**

Each module can be used independently, but the intended workflow is connected:

```text
Hotspot analysis
→ peptide design
→ SPPS-aware filtering
→ synthesis planning
→ docking/contact screening
→ molecular-dynamics validation bridging
→ export and citation
```

\---

## 1\. Hot Spot Finder

**Hot Spot Finder** performs sequence-based hotspot prioritization. It reports compact residue-index outputs such as:

```text
(14K), (17Y), (19R)
```

The number is the 1-based residue position from the N-terminus, and the letter is the amino acid at that position. For local hotspot regions, multiple representative residues may be reported together:

```text
(158W), (161Y), (163Y), (167R), (168R)
```

Hotspot scores are relative sequence-derived prioritization scores. They should be interpreted as **hypothesis-generating signals**, not experimentally validated binding residues.

Typical use cases include:

* scanning a protein or peptide sequence,
* ranking candidate hotspot positions,
* identifying residues useful for motif design,
* selecting regions for downstream peptide generation,
* preparing design hypotheses before structure-oriented screening.

\---

## 2\. Peptide Design Engine

The **Peptide Design Engine** generates or evaluates peptide candidates under user-defined constraints. It supports sequence-level, chemistry-aware, and SPPS-aware design rules.

Supported design features include:

* fixed or random length generation,
* motif constraints,
* bridge-style constraints,
* optional D-amino acid handling,
* optional non-natural amino acids,
* linkers and spacer tokens,
* N-terminal and C-terminal chemistry,
* labels and tags,
* candidate ranking,
* SPPS-aware pass/fail filtering,
* exportable result tables.

A central principle of the Peptide Design Engine is that peptide candidates should not only look good computationally, but should also remain plausible for practical synthesis.

Important output fields may include:

```text
SPPS\_status
SPPS\_reason
Nterm\_available
Cterm\_mode
modification\_validity
```

Example supported peptide notation:

```text
Ac-EEMQRR-NH2
AHP-8
Ac-dK-Aib-PEG2-FAM-R-NH2
```

`AHP-8` is treated as an alias for:

```text
Ac-EEMQRR-NH2
```

### Motif Constraints

Motif constraints enforce sequence fragments such as `RGD` or `EEMQR`.

Fixed motif placement can use syntax such as:

```text
RGD@1, EEMQR@4
```

Positions are counted from the N-terminus using 1-based indexing.

### Linker and Modifier Logic

Linker tokens such as:

```text
Ahx, AEEA, PEG4, PEG8, G4S, SMCC, DSS
```

are treated as linker or spacer components, not as default N-terminal modifiers.

Amino-acid-like units such as:

```text
bAla, gAla
```

may be treated as non-natural or amino-acid-like residues depending on the selected design settings.

N-terminal modifiers include chemical or label-type entries such as:

```text
Ac, Pal, Myr, Biotin, FITC, FAM, TAMRA
```

### N-terminal Chemistry Rule

If a candidate requires an N-terminal free amine but the N-terminus is already capped, the candidate should be blocked or flagged.

For example:

```text
Ac-EEMQRR-NH2
```

has an N-terminal Ac cap and should not be treated as having a free N-terminal amine.

\---

## 3\. SPPS Planner

The **SPPS Planner** generates editable C-terminal to N-terminal synthesis plans for solid-phase peptide synthesis.

It accepts peptide notation such as:

```text
Ac-EEMQRR-NH2
EEMQRR-NH2
EEMQRR
```

and parses the N-terminal modifier, core peptide, and C-terminal terminus separately. The parser is designed to correctly recognize the core peptide without requiring an artificial leading dash.

### Main SPPS Planner Outputs

The SPPS Planner can generate:

* editable synthesis plan,
* material usage tables,
* amino acid / unit usage,
* reagent / base / catalyst usage,
* solvent usage,
* printable synthesis checklist,
* project metadata table,
* log table,
* output folder with export files,
* citation notice.

### Editable Unit Concept

The editable SPPS table uses a unified **Unit** concept. A Unit may be:

* canonical amino acid,
* D-amino acid,
* non-natural amino acid,
* chemical modifier,
* label,
* tag,
* linker,
* terminal cap.

Core editable fields include:

```text
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
```

### Material Usage Logic

Usage is calculated from the current editable table state:

```text
Unit usage = resin scale × unit eq × repeat
Coupling reagent 1 usage = resin scale × reagent 1 eq × reagent 1 count
Coupling reagent 2 usage = resin scale × reagent 2 eq × reagent 2 count
Base usage = resin scale × base eq × base count
Solvent volume = resin scale × mL per mmol × solvent count
```

Solid reagents are reported by mass, while liquid reagents and solvents are reported by volume where density information is available.

### N-terminal Acetylation

N-terminal acetylation is displayed as `Ac` in the editable synthesis plan.

Default reagent:

```text
Acetic anhydride (Ac2O)
MW = 102.09 g/mol
density = 1.08 g/mL
```

Default volume calculation:

```text
Ac2O volume (mL) = resin scale (mmol) × Ac eq × 102.09 / 1000 / 1.08
```

`Ac` is not treated as an Fmoc-amino acid coupling step and is not followed by an additional Fmoc deprotection step.

### Resin-dependent Synthesis Logic

Pepforge distinguishes broad resin families.

For **2-CTC / trityl-type resin**:

```text
initial Fmoc deprotection is not required
swell solvent is DCM
loading is DCM-based
DIEA/DIPEA is treated as base, not duplicated as coupling reagent
```

For **Wang / Rink Amide / amide-type Fmoc resin**:

```text
initial Fmoc deprotection is required
default workflow is DMF-based
C-terminal amide behavior is expected for Rink/amide resins
```

Intermediate coupling steps primarily use DMF wash logic by default. Final deprotection or final N-terminal chemical/label/modifier coupling is followed by final wash logic such as:

```text
DMF wash ×3
DCM wash ×3
```

If a laboratory additionally uses methanol washing, the final MeOH wash count can be set manually.

\---

## 4\. Docking and Molecular Dynamics Workbench

The **Docking and Molecular Dynamics Workbench** is a structure-oriented screening and interpretation module.

It is not a full replacement for AutoDock Vina, PRODIGY, GROMACS, AMBER, NAMD, AlphaFold, or experimental assays. Instead, it provides an integrated screening environment that can:

* parse target and peptide inputs,
* interpret terminal modifications such as `Ac` and `NH2`,
* handle peptide sequence or peptide PDB input,
* generate contact-oriented docking summaries,
* estimate contact-based affinity metrics,
* report estimated Delta G and Kd using conventional thermodynamic units,
* classify residue and atom contacts,
* export PDB files with contact annotations,
* create validation folders for external all-atom workflows.

### Simplified Tab Structure

The public workflow is organized into five tabs:

```text
1. Input
2. Results
3. Contacts
4. Molecular Dynamics
5. Export / Import
```

### Recommended Workflow

```text
Enter target
→ enter peptide
→ Analyze
→ Run
→ review Results
→ review Contacts
→ review Molecular Dynamics
→ Export
```

### Supported Target Inputs

Target may be provided as:

```text
protein sequence
FASTA sequence
PDB structure
mmCIF structure
previous output folder
```

### Supported Peptide Inputs

Peptide may be provided as:

```text
peptide sequence
modified peptide notation
peptide PDB
```

Example:

```text
AHP-8
Ac-EEMQRR-NH2
```

Pepforge interprets AHP-8 as:

```text
N-terminal = Ac
Core sequence = EEMQRR
C-terminal = NH2
```

If a peptide PDB does not explicitly encode terminal cap information, Pepforge attempts to preserve terminal metadata from the peptide notation.


### Modified Peptide Handling in Docking Workbench

The Docking and Molecular Dynamics Workbench is designed to preserve and analyze modified peptide notation whenever possible. This includes D-form residues, selected non-natural amino acids, linkers, chemical labels, lipid-like moieties, and terminal caps.

Examples include:

```text
Ac-dK-Aib-PEG2-FAM-R-NH2
FITC-dK-Ahx-EEMQRR-NH2
Ac-E-dM-Q-Orn-R-NH2
```

Pepforge handles these tokens using **token-preserving, screening-level surrogate logic**. In practice, this means that modified units are not simply discarded during Docking Workbench analysis. Instead, Pepforge attempts to classify them by their approximate screening role:

```text
D-form residue       → native side-chain class + D-form flag
Aib                  → compact neutral non-natural residue approximation
Orn                  → Lys-like cationic side-chain approximation
Cit                  → polar neutral side-chain approximation
Nle                  → hydrophobic aliphatic approximation
Hyp                  → Pro-like constrained residue approximation
PEG / Ahx / AEEA     → flexible linker-like unit
FAM / FITC / TAMRA   → bulky aromatic or label-like unit
Pal / Myr            → hydrophobic lipid-tail-like unit
Ac / NH2             → terminal state metadata
```

With this approach, modified peptides can still be used for:

- input parsing,
- terminal-state recognition,
- contact screening,
- residue and atom/proxy contact reporting,
- estimated Delta G and Kd screening reports,
- molecular-dynamics screening,
- PDB export,
- all-atom validation package export.

However, these modified units are **not treated as fully parameterized all-atom residues inside Pepforge**. Publication-grade all-atom simulation of D-form residues, non-natural amino acids, linkers, and chemical labels requires external force-field parameterization and validation. Pepforge therefore reports these cases as screening-compatible but validation-dependent.

Recommended interpretation:

```text
Modified peptide workflow support: yes
Screening-level contact and affinity estimation: yes
Final all-atom accuracy without external parameters: no
External parameterization and validation: recommended for quantitative claims
```


\---

## Affinity Report Interpretation

Pepforge reports estimated Delta G and estimated Kd values in conventional thermodynamic form.

The relationship used is:

```text
Delta G = RT ln(Kd)
Kd = exp(Delta G / RT)
```

where:

```text
R = 0.001987204 kcal mol^-1 K^-1
T = 298.15 K
```

The estimated Delta G is reported in:

```text
kcal/mol
```

The estimated Kd is reported using one representative unit depending on magnitude, for example:

```text
nM
uM
mM
M
```

Pepforge intentionally avoids repeating the same Kd value in multiple units in the main report because this can make the table harder to read.

### Important Limitation

The reported Delta G is an internal contact-based screening estimate. It is not equivalent to a directly measured binding free energy and should not be treated as final proof of binding affinity.

Appropriate use:

* candidate comparison,
* early triage,
* ranking,
* identifying candidates with poor contact or excessive clash,
* preparing external validation.

Inappropriate use:

* claiming experimental binding affinity,
* reporting final Kd without validation,
* replacing all-atom MD or binding assays.

\---

## Contact Analysis Interpretation

Pepforge can report residue-level and atom-level contacts.

Typical contact classes include:

```text
generic contact
hydrogen-bond proxy
hydrophobic contact
salt-bridge-like contact
steric clash
```

Representative screening cutoffs include:

```text
hydrogen-bond donor-acceptor proxy: approximately 3.9 Angstrom
hydrophobic contact: approximately 5.0 Angstrom
generic interface contact: approximately 5.0 Angstrom
steric clash: approximately 2.0 Angstrom
```

These cutoffs are intended for screening and interpretation. When hydrogen atoms are missing from PDB files, hydrogen bonding is treated as a heavy-atom distance proxy rather than a full geometric hydrogen-bond definition.

Residue-level contact labels may appear as:

```text
4Q -> A:134D
```

This means:

```text
peptide residue 4Q contacts target chain A residue 134D
```

\---

## Output Folders

Pepforge modules generate output folders to support traceability.

Typical Docking Workbench export files include:

```text
affinity\_scoring\_summary.csv
molecular\_dynamics\_summary.csv
molecular\_dynamics\_frames.csv
best\_docking\_complex.pdb
contact\_annotated\_complex.pdb
OUTPUT\_MANIFEST.txt
CITATION\_NOTICE.txt
all\_atom\_validation\_package/
```

Typical SPPS Planner export files may include:

```text
editable\_spps\_plan.csv
material\_usage\_from\_editable\_plan.csv
printable\_synthesis\_checklist.csv
spps\_ml\_ready\_log\_from\_editable\_plan.csv
spps\_plan.xlsx
OUTPUT\_MANIFEST.txt
CITATION\_NOTICE.txt
```

\---

## All-Atom Validation Bridge

Pepforge can export an all-atom validation package to support external validation.

A typical validation package may include:

```text
all\_atom\_validation\_package/
├── README\_ALL\_ATOM\_VALIDATION.txt
├── token\_parameter\_requirements.csv
├── complex\_candidate.pdb
├── target\_input.pdb
├── peptide\_input.pdb
├── gromacs/
├── amber/
└── namd/
```

This package is intended to help users move from Pepforge screening to external validation.

Important examples:

```text
D-form residue: topology/chirality check required
Aib: non-standard residue parameter may be required
PEG linker: linker topology may be required
FAM/FITC/TAMRA: small-molecule parameter may be required
Ac/NH2: terminal patch check may be required
```

\---

## Repository Structure

The recommended public GitHub repository structure is:

```text
Pepforge/
├── README.md
├── LICENSE
├── CITATION.cff
├── CITATION\_NOTICE.txt
├── MANUAL\_EN.txt
├── MANUAL\_KO.txt
├── requirements.txt
├── environment.yml
├── main\_launcher.py
├── assets/
│   ├── Pepforge\_Icon.png
│   └── Pepforge\_Icon.ico
├── apps/
│   ├── hotspot\_finder/
│   ├── peptide\_design\_engine/
│   └── spps\_planner\_app/
├── suite\_gui/
├── peptiforg\_core/
├── docs/
├── tests/
├── installer/
└── examples/
```

### Directory Description

* `README.md`  
Main public-facing project document describing Pepforge, its modules, installation, usage, outputs, limitations, and citation policy.
* `LICENSE`  
License file for the public research release.
* `CITATION.cff`  
GitHub-compatible citation metadata.
* `CITATION\_NOTICE.txt`  
Human-readable citation notice.
* `MANUAL\_EN.txt` and `MANUAL\_KO.txt`  
Detailed user manuals.
* `requirements.txt`  
Python package requirements.
* `environment.yml`  
Optional Conda environment definition.
* `main\_launcher.py`  
Main desktop launcher.
* `assets/`  
Program icons and visual resources.
* `apps/`  
Module-specific application code.
* `suite\_gui/`  
Shared GUI components.
* `peptiforg\_core/`  
Shared core utilities and common logic.
* `docs/`  
Technical documentation and method notes.
* `tests/`  
Regression and validation tests.
* `installer/`  
Installer configuration files.
* `examples/`  
Public-safe example inputs and outputs.

\---

## Installation

From the root Pepforge folder:

```bash
pip install -r requirements.txt
python main\_launcher.py
```

If multiple Python versions are installed:

```bash
py main\_launcher.py
```

Individual module launch examples:

```bash
python main\_launcher.py --tool design
python main\_launcher.py --tool spps
python main\_launcher.py --tool docking
```
```For users:
Run from source using Python.

For Windows installer:
A prebuilt installer will be provided in the GitHub Releases section when available.
```

\---

## Validation and Testing

Pepforge public releases are tested using the included test suite.

Typical validation includes:

* launch path checks,
* peptide parser checks,
* terminal modification parsing,
* SPPS planner output generation,
* material table generation,
* docking input parsing,
* contact report generation,
* PDB export generation,
* citation notice generation,
* cache cleanup.

Users can run tests with:

```bash
pytest
```

or:

```bash
python -m pytest
```

A passing test suite does not imply biological validation. It means the software functions are operating according to the included programmatic checks.

\---

## Recommended GitHub Release Workflow

For public release:

1. Keep the program UI title clean as `Pepforge`.
2. Use repository release tags for version tracking.
3. Use `v1.0.0` for the first public research release.
4. Include `CITATION.cff`.
5. Include `CITATION\_NOTICE.txt`.
6. Create a GitHub Release.
7. Attach the ZIP release asset.
8. Optionally connect GitHub to Zenodo to obtain a DOI.

Recommended release title:

```text
Pepforge Public Research Release 1.0.0
```

Recommended tag:

```text
v1.0.0
```

\---

## Suggested GitHub Description

```text
Integrated peptide research workbench for hotspot analysis, SPPS-aware peptide design, synthesis planning, docking-oriented screening, contact analysis, and molecular dynamics validation bridging.
```

Suggested topics:

```text
peptide-design
spps
bioinformatics
docking
molecular-dynamics
peptide-synthesis
computational-biology
drug-discovery
research-software
```

\---

## Limitations

Pepforge should be interpreted as a research-support and screening workbench.

Known limitations:

* contact-based docking scores are approximate,
* embedded molecular dynamics screening is not equivalent to full all-atom MD,
* non-natural amino acids and chemical labels may require external parameterization,
* estimated Delta G and Kd values are not experimental measurements,
* SPPS material usage should be reviewed by a trained researcher before laboratory execution,
* reagent equivalents and solvent volumes may need adjustment depending on laboratory protocol, resin, scale, peptide hydrophobicity, and protecting groups.

Pepforge is intended to help organize and accelerate research reasoning, not to remove the need for expert review.

\---

## Disclaimer

Pepforge is provided for research, educational, and planning purposes. The software does not guarantee biological activity, binding affinity, synthesis success, purity, yield, or experimental safety. Users are responsible for validating designs, calculations, reagent conditions, and laboratory procedures according to institutional and chemical safety standards.

\---

## Author

**Sanghun Woo**  
Department of Biochemical Engineering  
Korea Polytechnic University

GitHub: `https://github.com/poowsh1407`

Project: **Pepforge**

