<div align="center">


## V3.0.0 Integrated Peptide Research Workflow

V3.0.0 connects sequence analysis, peptide candidate design, sequence-aware
structure generation, SPPS planning, docking-oriented screening, and external
validation export in one peptide-focused desktop workflow. The public build
integrates the sanitized SPPS Planner V4 evidence workflow and contains no
private experimental history.

<img src="assets/Pepforge_Icon.png" alt="Pepforge icon" width="150">

# Pepforge

### From peptide sequence to structure, synthesis planning, and validation hand-off

Desktop research software for designing **canonical and modified peptides**,
generating representative conformers, preparing editable SPPS plans, and
organizing downstream validation.

[![Release](https://img.shields.io/badge/release-V3.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#quick-start)
[![Release Gate](https://img.shields.io/badge/release_gate-23%2F23-16A34A?style=for-the-badge)](#verification)

**[한국어](README_KO.md) · [Quick start](#quick-start) · [Features](#what-it-does) · [Notation](#modified-peptide-notation) · [Manual](MANUAL_EN.md)**

</div>

---

## Why Pepforge?

Peptide research rarely ends with a sequence. Candidate regions, terminal
chemistry, non-natural residues, structural diversity, synthesis constraints,
and validation files must remain connected without turning unsupported
assumptions into scientific facts.

Pepforge keeps those decisions in one workflow:

```text
Protein or peptide sequence
            ↓
     Hotspot prioritization
            ↓
 Modified-peptide candidate design
            ↓
 Sequence-aware Top-5 conformer ensemble
            ↓
 Editable SPPS plan · Materials · Checklist
            ↓
 Docking-oriented screening
            ↓
 External PyMOL · Docking · MD hand-off
```

## What it does

| Area | Capabilities |
| --- | --- |
| **Hot Spot Finder** | Analyze pasted protein or peptide sequences, rank candidate regions, inspect the hotspot table, and export results |
| **Peptide Design Engine** | Generate canonical or supported modified-peptide candidates with explicit settings, per-run seeds, exact-repeat controls, and final sequence-diversity filtering |
| **Peptide Structure Builder** | Interpret supported peptide chemistry and generate a ranked, family-diverse Top-5 coordinate ensemble |
| **Sequence-aware structure search** | Explore α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, and coil/mixed families |
| **Modified-peptide handling** | Preserve supported terminal groups, D-residues, non-natural residues, tags, labels, linkers, chirality, and modifications |
| **α/β/γ peptidomimetics** | Recognize supported mixed-backbone patterns while keeping canonical α-residue assumptions separate from β/γ units |
| **SPPS Planner V4** | Generate an editable Plan, Materials, Total Materials, Checklist, cleavage review, literature guidance, and project exports |
| **Docking Workbench** | Screen peptide–target pose and contact hypotheses for prioritization without presenting internal scores as experimental affinity |
| **External Validation** | Prepare organized files and folders for separately installed PyMOL, docking, and molecular-dynamics tools |
| **Public release controls** | Exclude private experimental history, obsolete backups, hidden example targets, inactive synthetic priors, runtime monkey patches, and completed-looking placeholders |

## Operator-focused behavior

- **Hot Spot Finder** accepts direct pasted-sequence analysis instead of requiring a prepared input file.
- **PDE Apply Settings** validates and freezes the visible configuration before candidate generation.
- PDE starts without hidden target sequences or locked RGD/KLVFF examples.
- Exploratory PDE runs record a new seed; `Lock seed for exact repeat` and
  `Repeat Last Run` preserve reproducibility when requested.
- **PSB Analyze** shows how every supported chemistry token was interpreted
  before structure generation.
- A successful **Build Top 5 Structures** operation exports exactly five ranked
  coordinate candidates. A partial set is reported as incomplete.
- PSB `Fast`, `Balanced`, and `Thorough` presets change real sampling and retry
  budgets rather than acting as decorative options.
- Structure generation runs in an isolated worker so a failed build does not
  close the full PSB window.
- SPPS **Generate/Update** creates the connected Plan, Materials, Total
  Materials, Checklist, and cleavage result together.
- SPPS **Apply Change** remains the explicit action for committing reviewed Plan
  or cleavage changes.
- LOT Number and Batch Manager are intentionally excluded from the Pepforge
  integration.

## Modified-peptide notation

Examples:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

Important token rules:

| Input | Interpretation |
| --- | --- |
| `Ac-` or `AC-` | Acetyl terminal modifier |
| `Pal-` or `PAL-` | Palmitoyl terminal modifier |
| `A-C-` | Ala–Cys residue sequence |
| `P-A-L-` | Pro–Ala–Leu residue sequence |
| `FITC-` or `Biotin-` | Registered label/tag token when supported |
| `-AEEA-` | Registered linker token when supported |

Explicit separators distinguish residue spelling from terminal chemistry.
Unknown chemistry and recognized tokens without a curated buildable graph are
reported clearly instead of being replaced with fabricated canonical residues.
See the [token registry and sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md)
for the complete input contract.

## Sequence-aware Top-5 structures

Pepforge uses sequence evidence to prioritize relevant structural families and
then ranks diverse coordinate candidates within the supported chemistry model.
The Top 5 are plausible starting conformers for inspection and external
validation—not five experimentally proven physiological states.

Typical outputs:

```text
<name>_conformer_ensemble.sdf
<name>_conformer_families.csv
<name>_backbone_torsions.csv
<name>_rank_01.pdb ... <name>_rank_05.pdb
```

Condition presets record interpretation and export context. RDKit structure
generation is not constant-pH simulation, explicit-solvent molecular dynamics,
or an AlphaFold prediction.

## SPPS Planner V4 integration

Pepforge embeds the public, data-sanitized SPPS Planner V4 single-plan workflow.
Loading, coupling, and cleavage guidance follows conservative evidence rules:

- `verified` records may support exact-condition application.
- `parsed` records remain review evidence until explicitly confirmed.
- `incomplete` and `excluded` records cannot silently become actionable.
- Cleavage matching is sequence-first rather than product-name driven.
- One recommendation transfers one coherent reviewed condition; components from
  unrelated historical cocktails are not mixed.
- Loading and cleavage time are recorded independently and do not silently
  change reagent stoichiometry.
- No private laboratory record is bundled with the public release.

## Quick start

See the [complete English manual](MANUAL_EN.md) or
[complete Korean manual](MANUAL_KO.md) for the full workflow, exact button order,
output interpretation, and troubleshooting.

### Requirements

- Windows 10 or 11 recommended
- 64-bit Python 3.10 or newer
- Tk support
- RDKit for actual 3D structure generation

### Run from source

```bat
git clone https://github.com/SanghunWoo-23/Pepforge.git
cd Pepforge
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

PyMOL and external docking/MD applications are optional and must be installed
separately.

### Direct module launch

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

Run `python main_launcher.py --help` to confirm the current command-line options.

## Project structure

```text
Pepforge/
├─ main_launcher.py             # Desktop application entry point
├─ pepforge_cli.py              # Workflow and release-audit CLI
├─ suite_gui/                   # Active desktop module interfaces
├─ peptiforg_core/              # Shared scientific and workflow logic
├─ spps_v4_gui/                 # Integrated SPPS Planner V4 workflow
├─ apps/                        # Bundled application engines and data
├─ tests/                       # Unit, regression, and behavior contracts
├─ docs/                        # Scientific, API, grammar, and release docs
├─ installer/                   # Windows build configuration
├─ MANUAL_EN.md                 # Complete English user manual
└─ MANUAL_KO.md                 # Complete Korean user manual
```

Runtime outputs use separate workspaces for each tool. This is application-level
workspace isolation, not an operating-system security sandbox.

## Documentation

| Document | Purpose |
| --- | --- |
| [English complete manual](MANUAL_EN.md) | Installation, UI workflow, input grammar, outputs, and troubleshooting |
| [한국어 완전 매뉴얼](MANUAL_KO.md) | 설치, 버튼 순서, 입력 표기, 결과 해석, 문제 해결 |
| [Scientific scope](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md) | Claims supported and not supported by Pepforge output |
| [Token and sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md) | Residue, chemistry, tag, linker, and modifier input rules |
| [SPPS V4 evidence workflow](docs/SPPS_V4_EVIDENCE_WORKFLOW.md) | Evidence states and controlled application rules |
| [Public API contract](docs/PUBLIC_API_CONTRACT.md) | Stable programmatic interface |
| [Release notes](RELEASE_NOTES_V3.0.0.md) | V3.0.0 changes and verification summary |
| [Public-data policy](PUBLIC_DATA_POLICY.md) | Data sanitization requirements for public releases |

## Verification

The final public source baseline passed the integrated release gate:

- **23 passed / 0 failed**
- **224 Python files compiled / 0 errors**
- **0 runtime patch, placeholder, or duplicate-definition findings**
- **0 stale legacy-name findings**
- **0 packaging-artifact findings**

Run the public checks:

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Native Windows rendering, actual RDKit Top-5 generation, PyMOL opening, locally
built executables/installers, and third-party docking/MD execution must still be
verified on the target machine.

## Scientific scope

Pepforge outputs are research hypotheses and preparation artifacts. Internal
scores are not measured affinity or Kd; conformers are not proof of an in-vivo
native structure; synthesis guidance is not an automatically validated SOP.
Experimental identity, purity, structure, activity, and safety require
appropriate external and laboratory validation.

Unsupported building blocks, residue propensities, force-field parameters,
experimental outcomes, or optimum synthesis conditions are not invented.

## Contributing

Bug reports should include the Pepforge version, OS, Python version, launch
method, affected module, minimal input, reproduction steps, and relevant logs.
Remove confidential or unpublished data before posting.

Contributions must not introduce runtime monkey patches, incomplete placeholders
presented as finished features, fabricated scientific output, or silent feature
loss. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Version

This repository is the public standard release **Pepforge V3.0.0** with the
integrated **SPPS Planner V4.0.0** evidence workflow.

## Citation and license

If Pepforge materially contributes to academic work, cite the exact release
using the metadata in [CITATION.cff](CITATION.cff).

Pepforge uses the custom **Pepforge Public Academic Citation License** and is not
presented as an OSI-approved open-source license. Read [LICENSE](LICENSE) before
redistribution or commercial use.

---

<div align="center">

**Pepforge V3.0.0**  
Integrated peptide design, structure, synthesis planning, and validation hand-off.

</div>
