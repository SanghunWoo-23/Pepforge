<div align="center">
  <img src="assets/Pepforge_Icon.png" alt="Pepforge logo" width="132">
  <h1>Pepforge</h1>
  <p><strong>From peptide sequence to structure, synthesis planning, and validation hand-off.</strong></p>
  <p>A Windows-first desktop research workbench for canonical and modified peptides.</p>
  <p>
    <a href="VERSION.txt"><img src="https://img.shields.io/badge/Pepforge-v3.0.0-2563EB?style=flat-square" alt="Pepforge v3.0.0"></a>
    <a href="docs/SPPS_V4_EVIDENCE_WORKFLOW.md"><img src="https://img.shields.io/badge/SPPS_Planner-v4.0.0-7C3AED?style=flat-square" alt="SPPS Planner v4.0.0"></a>
    <a href="requirements.txt"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.10+"></a>
    <a href="#installation"><img src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&amp;logo=windows&amp;logoColor=white" alt="Windows"></a>
    <a href="RELEASE_NOTES_V3.0.0.md"><img src="https://img.shields.io/badge/Release_gate-23%2F23-16A34A?style=flat-square" alt="Release gate 23/23"></a>
  </p>
  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="#workflow">Features</a> ·
    <a href="#modified-peptide-notation">Notation</a> ·
    <a href="#documentation">Documentation</a> ·
    <a href="README_KO.md">한국어</a>
  </p>
</div>

---

## Overview

Pepforge connects six peptide-research tasks in one desktop workflow. It can prioritize sequence regions, generate peptide candidates, build a sequence-aware Top-5 conformer ensemble, prepare an editable SPPS plan, screen docking-oriented poses, and export files for external validation.

The public standard is **Pepforge V3.0.0**, integrating the sanitized **SPPS Planner V4.0.0** evidence workflow.

> [!IMPORTANT]
> Pepforge is research software. Structures, scores, contacts, and synthesis recommendations are hypotheses and planning aids—not experimental measurements, proof of a native in-vivo structure, a validated laboratory SOP, or medical guidance.

## Why Pepforge?

| Chemistry-aware | Sequence-aware | Evidence-bounded |
| --- | --- | --- |
| Preserves supported terminal groups, tags, linkers, D-residues, non-natural residues, chirality, and modifications. | Searches helix, beta/extended, hairpin-like, turn, PPII, and coil/mixed conformational families. | Unsupported chemistry is blocked explicitly; missing structures, parameters, affinities, or experimental conditions are not invented. |

## Workflow

| Step | Module | What it does | Main output |
| :---: | --- | --- | --- |
| **1** | **Hot Spot Finder** | Prioritizes candidate regions from a pasted protein or peptide sequence | Ranked hotspot table and exports |
| **2** | **Peptide Design Engine** | Generates canonical and supported modified-peptide candidates | Diverse, reproducible candidate sets |
| **3** | **Peptide Structure Builder** | Interprets peptide chemistry and generates representative conformers | Exactly five ranked coordinate candidates on success |
| **4** | **SPPS Planner V4** | Builds an editable synthesis plan, material estimate, checklist, and cleavage review | Plan, materials, checklist, and evidence exports |
| **5** | **Docking Workbench** | Screens pose and contact hypotheses for prioritization | Docking-oriented result package |
| **6** | **External Validation** | Prepares hand-off files for downstream tools | PyMOL, docking, and MD-ready workspace |

```text
Sequence / target
      │
      ├─ Hotspot prioritization
      ├─ Peptide candidate design
      ├─ Sequence-aware Top-5 structure ensemble
      ├─ SPPS plan and material calculation
      ├─ Docking-oriented screening
      └─ External validation hand-off
```

## Key capabilities

### Peptide Design Engine

- Starts without hidden targets or locked example motifs.
- Uses a newly recorded seed for each exploratory run.
- Provides `Lock seed for exact repeat` and `Repeat Last Run` for reproducibility.
- Applies a final sequence-distance diversity filter so Top-K results are not needlessly repetitive.
- Requires explicit settings validation before candidate generation.

### Peptide Structure Builder

- A successful Top-5 build exports **exactly five real coordinate candidates**; a partial set is reported as incomplete.
- `Fast`, `Balanced`, and `Thorough` presets control real sampling and retry budgets.
- Searches α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, and coil/mixed families.
- Includes guarded α/β/γ-peptidomimetic and BH3-helical design context without transferring canonical α-residue assumptions to β/γ units.
- Runs structure generation in an isolated worker so a failed build does not close the entire PSB window.

Typical structure outputs:

```text
<name>_conformer_ensemble.sdf
<name>_conformer_families.csv
<name>_backbone_torsions.csv
```

### SPPS Planner V4

- Generates and updates Plan, Materials, Total Materials, Checklist, and cleavage output together.
- Keeps operator edits explicit through `Apply Change`.
- Records loading and cleavage time without silently changing stoichiometry.
- Uses sequence-first cleavage review and transfers only one coherent reviewed condition at a time.
- Separates evidence states into `verified`, `parsed`, `incomplete`, and `excluded`.
- Excludes LOT Number and Batch Manager from the Pepforge-integrated interface.
- Ships without private laboratory history in the public experimental-data area.

## Quick start

### Installation

Requirements: **Python 3.10+**, Tk support, and RDKit for actual 3D structure generation. A dedicated virtual environment is recommended.

```bash
git clone https://github.com/SanghunWoo-23/Pepforge.git
cd Pepforge
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

On macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

PyMOL and external docking/MD applications are optional and must be installed separately.

### First run

1. Paste a sequence into **Hot Spot Finder** and run the analysis.
2. Review PDE settings, click **Apply Settings**, and generate candidates.
3. Enter a selected peptide in **Peptide Structure Builder**, click **Analyze**, review token interpretation, and build the Top 5.
4. Generate the **SPPS Planner** workflow and review Plan, Materials, Total Materials, Checklist, and cleavage guidance before applying changes.
5. Use Docking Workbench and external exports as screening and validation hand-off steps.

<details>
<summary><strong>Launch an individual module</strong></summary>

```bash
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

Run `python main_launcher.py --help` for the current command-line options.

</details>

## Modified-peptide notation

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

| Input | Interpretation |
| --- | --- |
| `Ac-` or `AC-` | Acetyl terminal modifier |
| `Pal-` or `PAL-` | Palmitoyl terminal modifier |
| `A-C-` | Ala–Cys residues |
| `P-A-L-` | Pro–Ala–Leu residues |
| `FITC-`, `Biotin-`, `-AEEA-` | Registered tag/linker tokens when supported |

Explicit separators disambiguate residue spelling from chemistry tokens. Unknown or recognized-but-unbuildable chemistry is reported instead of being replaced with a fabricated canonical surrogate. See the [sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md) for the complete contract.

## Verification

The public source baseline passed the integrated **23/23 release gate**, including Python compilation, source-integrity inspection, public API checks, and packaging checks.

```bash
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Target-machine validation is still required for native Windows GUI behavior, actual RDKit Top-5 generation, PyMOL session opening, locally built installers/executables, and third-party docking or MD execution.

## Documentation

| Document | Purpose |
| --- | --- |
| [Complete manual — English](MANUAL_EN.md) | Installation, UI workflow, notation, outputs, and troubleshooting |
| [Complete manual — Korean](MANUAL_KO.md) | 한국어 설치·사용·결과 해석·문제 해결 안내 |
| [Scientific scope and validation](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md) | What Pepforge results can and cannot support |
| [Sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md) | Chemistry-token and residue-input contract |
| [SPPS V4 evidence workflow](docs/SPPS_V4_EVIDENCE_WORKFLOW.md) | Experimental-evidence and application rules |
| [Public API contract](docs/PUBLIC_API_CONTRACT.md) | Stable public programmatic interface |
| [Release notes](RELEASE_NOTES_V3.0.0.md) | V3.0.0 changes and verification snapshot |
| [Public-data policy](PUBLIC_DATA_POLICY.md) | Data sanitization requirements for public releases |

## Dependency profiles

| File | Profile |
| --- | --- |
| `requirements.txt` | Core desktop runtime, including RDKit |
| `requirements-ml.txt` | Optional ML components |
| `requirements-research.txt` | Optional research stack |
| `requirements-web.txt` | Optional web components |

<details>
<summary><strong>Repository map</strong></summary>

```text
apps/                    Bundled application engines
peptiforg_core/          Shared scientific and workflow logic
spps_v4_gui/             SPPS Planner V4 workflow and evidence layer
suite_gui/               Desktop module interfaces
tests/                   Unit, regression, and contract tests
docs/                    Scientific, API, and release documentation
installer/               Windows build configuration
main_launcher.py         Desktop entry point
pepforge_cli.py          Workflow and release-audit CLI
```

Runtime outputs use per-tool workspaces. This is application-level workspace isolation, not an operating-system security sandbox.

</details>

## Contributing

Bug reports should include the Pepforge version, OS, Python version, launch method, affected module, minimal input, reproduction steps, and relevant logs. Remove confidential or unpublished data before posting.

Contributions must not introduce runtime monkey patches, incomplete placeholders presented as finished features, fabricated scientific output, or silent feature loss. Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## Citation and license

If Pepforge materially contributes to academic work, cite the exact release using the metadata in [CITATION.cff](CITATION.cff).

Pepforge uses the custom **Pepforge Public Academic Citation License** and is not represented as an OSI-approved open-source license. Review [LICENSE](LICENSE) before redistribution or commercial use.

---

<div align="center">
  <strong>Pepforge V3.0.0</strong><br>
  Developed by Sanghun Woo for transparent, peptide-focused research workflows.
</div>
