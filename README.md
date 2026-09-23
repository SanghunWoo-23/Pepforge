<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge" width="150">

# Pepforge

### Integrated peptide design, structure generation, SPPS planning, and interaction review

**Pepforge V4.0.0 · Public research source release**

[![Release](https://img.shields.io/badge/release-v4.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#quick-start)
[![Release Gate](https://img.shields.io/badge/release_gate-25%2F25-16A34A?style=for-the-badge)](#verification)

**[한국어](README_KO.md) · [Quick start](#quick-start) · [Capabilities](#capabilities) · [Modified peptides](#modified-peptide-support) · [Scientific scope](#scientific-scope) · [Manual](MANUAL_EN.md)**

</div>

---

## Overview

Pepforge is a Windows-first desktop research workbench that keeps the peptide workflow connected from **sequence-level prioritization** to **candidate design**, **3D conformer generation**, **SPPS planning**, and **protein–peptide interaction review**.

It is designed for workflows where ordinary amino-acid sequences are not enough. Pepforge preserves supported terminal chemistry, D-residues, non-natural residues, linkers, labels, and other modified-peptide notation while keeping computational screening clearly separated from experimental evidence.

```text
Target / protein sequence
        ↓
Hot Spot Finder
        ↓
Peptide Design Engine (PDE)
        ↓
Peptide Structure Builder (PSB)
        ↓
SPPS Planner
        ↓
Docking Workbench / interaction review
        ↓
Evidence export / external validation hand-off
```

Pepforge does **not** turn an internal score into an experimental affinity claim, does **not** invent unsupported chemistry, and does **not** treat generated conformers as proof of a native biological structure.

---

## Capabilities

| Module | What it does |
| --- | --- |
| **Workflow Mode** | Connects Hot Spot → PDE → PSB → SPPS with candidate lineage and project/session state |
| **Hot Spot Finder** | Screens pasted protein/peptide sequences, ranks candidate regions, and exports hotspot evidence |
| **Peptide Design Engine** | Generates and evaluates canonical or supported modified peptides with Pareto NSGA-II selection, explicit design-objective modes, chemistry-aware diversity, and stable candidate IDs |
| **Peptide Structure Builder** | Interprets supported peptide chemistry and builds up to five ranked, sterically screened coordinate candidates aligned to explicit structure intent when provided |
| **SPPS Planner** | Produces editable Plan, Materials, Total Materials, Checklist, cleavage review, evidence guidance, and project exports using the embedded Public/Data-Sanitized SPPS Planner V5 workflow |
| **Docking Workbench** | Reviews peptide–target pose/contact hypotheses with readable residue-centered contacts and conservative interaction evidence |
| **Structure / validation tools** | Compares compatible PDB/SDF structures, prepares PyMOL review material, and supports external docking/MD hand-off without pretending that external validation has already been performed |

### Design modes

PDE supports five explicit scientific-design objectives:

- **Interaction Only**
- **Interaction First**
- **Balanced**
- **Structure Guided**
- **Structure Exploration**

`Interaction Only` removes structure preference from the active optimization objective instead of hiding it behind a zero-weight score. Structure-guided modes require explicit structure intent rather than inventing one.

### Structure search

PSB can explore supported sequence-aware conformational families including:

- α-helix
- 3₁₀-helix
- β-extended / strand-like
- β-hairpin-like
- PPII
- turn-rich
- coil / mixed

Returned structures are **starting hypotheses for inspection and downstream validation**, not experimentally established conformational populations.

---

## What is new in R14

R14 closes an important PSB → Docking interoperability gap.

PSB-generated PDB files now preserve both **ordinary peptide sequence information** and the **exact Pepforge modified construct**:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
```

The PDB export now includes:

- peptide `SEQRES` records,
- `REMARK 901 PEPFORGE_EXACT_SEQUENCE` metadata,
- token/modifier metadata,
- existing residue-aware `ATOM` / `HETATM` coordinates,
- continuation support for long exact-sequence metadata.

Docking Workbench restores peptide identity in this order:

```text
Pepforge exact-sequence metadata
        ↓
SEQRES
        ↓
ATOM / HETATM residue extraction
```

Modifiers and linkers do **not** consume peptide residue numbering. Chemistry with a curated coordinate graph remains coordinate-bearing; recognized chemistry without a unique curated derivative/attachment graph is not assigned fabricated all-atom coordinates.

R14 also preserves the R12/R13 SPPS fixes that make the visible Project Manager Sequence the source of truth and prevent automatic startup/idle refresh from raising `Core sequence is empty` while no sequence has been entered.

See [R14 validation](docs/validation/VALIDATION_R14_2026-09-21.md) and [GitHub-ready validation](docs/validation/GITHUB_READY_VALIDATION_R14_2026-09-22.md).

---

## Modified-peptide support

Pepforge uses explicit tokenization so terminal chemistry is not confused with ordinary residue spelling.

Examples:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

Important examples:

| Input | Interpretation |
| --- | --- |
| `Ac-` / `AC-` | Acetyl terminal modifier |
| `Pal-` / `PAL-` | Palmitoyl terminal modifier |
| `A-C-` | Ala–Cys residue sequence |
| `P-A-L-` | Pro–Ala–Leu residue sequence |
| `FITC-` / `Biotin-` | Registered label/tag token when supported |
| `AEEA`, `Ahx`, PEG tokens | Registered linker chemistry when supported |
| D/non-natural residue tokens | Preserved as explicit chemistry rather than silently converted to canonical L-residues |

A compact canonical sequence such as `ACDE-NH2` means **A-C-D-E**, while `AC-D-E-NH2` uses the explicit `AC-` acetyl token under the Pepforge grammar.

Support is stage-specific. Some chemistry can be parsed and preserved even when a unique all-atom derivative or attachment graph is not available. Pepforge reports that distinction instead of fabricating a structure.

See [Modified Peptide Support](docs/MODIFIED_PEPTIDE_SUPPORT_V4.md) and [Token Registry / Sequence Grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md).

---

## SPPS Planner

Pepforge embeds the **SPPS Planner V5.0.0 Public/Data-Sanitized** workflow while keeping Pepforge at suite version **V4.0.0**.

The integrated planner provides:

- editable synthesis Plan,
- step-wise Materials,
- Total Materials,
- Checklist,
- cleavage review,
- project/session persistence,
- literature/evidence guidance,
- experimental-data decision support using user-provided local records.

Public releases do not contain private laboratory history, private seed databases, or local operator records. Evidence states remain explicit; incomplete or unreviewed historical data are not silently promoted into exact synthesis conditions.

LOT Number and Batch Manager are intentionally excluded from the Pepforge operator-facing integration.

See [SPPS V5 Integration](docs/SPPS_V5_INTEGRATION.md) and [Public Data Policy](PUBLIC_DATA_POLICY.md).

---

## Docking and interaction review

Docking Workbench is a **screening and interpretation layer**, not a replacement for validated docking engines, all-atom MD, or binding experiments.

It can report residue-centered contacts and conservative interaction candidates such as:

- hydrogen bonds,
- hydrophobic contacts,
- salt bridges / ionic interactions,
- π–π interactions,
- cation–π interactions,
- van der Waals contacts / steric clashes,
- disulfide geometry,
- water bridges,
- metal coordination,
- halogen bonds,
- aromatic–sulfur interactions,
- weak C–H···O/N interactions,
- NH–π / amino-aromatic interactions.

Geometry-aware interaction evidence remains separate from coarse contact triage. Distances and internal scores are screening evidence and should not be reported as experimentally measured affinity.

---

## Quick start

### Requirements

- Windows 10 or 11 recommended
- 64-bit Python **3.10+**
- Tk support
- RDKit for actual 3D structure generation

PyMOL and external docking/MD applications are optional and are installed separately.

### Run from source

```bat
git clone https://github.com/poowsh1407/Pepforge.git
cd Pepforge
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

If several Python installations are present on Windows, `py main_launcher.py` can also be used.

### Direct module launch

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool workflow
python main_launcher.py --tool external
```

`--tool pymol` is retained as a compatibility alias for the structure-builder route.

For complete UI instructions, input grammar, outputs, and troubleshooting, use [MANUAL_EN.md](MANUAL_EN.md) or [MANUAL_KO.md](MANUAL_KO.md).

---

## Typical workflow

1. **Create or open a project/session.**
2. **Enter a target/protein sequence** and run Hot Spot Finder if sequence-level prioritization is needed.
3. **Generate or evaluate candidates in PDE**, then choose the candidate to transfer downstream.
4. **Build ranked structures in PSB** and review the generated PDB/SDF outputs.
5. **Open SPPS Planner** with the active sequence, resin/loading, and scale for synthesis planning.
6. **Use Docking Workbench** for residue-level contact/interaction review and prepare downstream validation artifacts.

Generated evidence remains traceable to the active construct/candidate rather than being merged into an unsupported all-in-one confidence score.

---

## Result and project files

User-generated result bundles follow a date/name convention such as:

```text
YYYY-MM-DD_<name-or-sequence>/
```

Depending on the workflow, bundles may include CSV, JSON, PDB, SDF, XLSX, text/Markdown reports, PyMOL review scripts, and packaged ZIP outputs.

For modified chemistry, **SDF/JSON are authoritative for exact graph/connectivity where applicable**. PDB is primarily an interoperability and structural-review representation, with R14 metadata preserving exact Pepforge notation for round-trip recovery.

---

## Repository structure

```text
Pepforge/
├─ main_launcher.py             # Desktop entry point
├─ pepforge_cli.py              # Workflow / release-audit CLI
├─ suite_gui/                   # Active desktop module interfaces
├─ peptiforg_core/              # Shared scientific/workflow logic
├─ pepforge_structure_tool/     # Structure-generation support
├─ spps_v4_gui/                 # SPPS V5 component under compatibility namespace
├─ apps/                        # Bundled application engines and data
├─ tests/                       # Unit/regression/behavior contracts
├─ docs/                        # Scientific, grammar, validation, and release docs
├─ installer/                   # Windows build configuration
├─ MANUAL_EN.md
└─ MANUAL_KO.md
```

Runtime workspaces, generated outputs, local databases, credentials, caches, and private experimental history are excluded from the public source package.

---

## Verification

The GitHub-ready R14 public source tree was validated after packaging cleanup.

| Check | Result |
| --- | ---: |
| Release Gate | **25 / 25 passed** |
| Release Verify Matrix | **16 / 16 passed** |
| Release Integrity | **18 / 18 passed** |
| Full Package Audit | **20 / 20 passed** |
| Source-integrity audit | **0 findings** |
| Focused GitHub-readiness regression | **32 / 32 passed** |
| Python files compiled by Release Gate | **325** |
| Compile errors | **0** |
| R14 representative coordinate round-trip | **20 / 20 passed** |
| Explicit/buildable chemistry round-trip | **47 / 47 passed** |

The R14 functional groups additionally recorded focused PSB/notation, UI/lineage, Docking, release-integrity, and compile checks. See [GitHub-ready validation](docs/validation/GITHUB_READY_VALIDATION_R14_2026-09-22.md).

You can run the included checks with:

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Native Windows rendering, locally built installer/EXE behavior, external PyMOL, and third-party docking/MD execution remain environment-specific checks.

---

## Scientific scope

Pepforge is intended for **research prioritization, reproducible computational preparation, synthesis planning, and validation hand-off**.

Do not interpret Pepforge output as automatic proof of:

- experimental binding affinity or Kd,
- binding free energy,
- native in-vivo peptide conformation,
- biological efficacy,
- synthesis yield or purity,
- laboratory safety or protocol suitability.

Production MD and trajectory analysis are **not exposed as V4 user functionality**. External simulation workflows can be prepared, but production simulation/trajectory analysis belongs to the future V5 simulation scope.

Unsupported building blocks, force-field parameters, experimental results, or optimum synthesis conditions are not invented.

See [Scientific Scope and Validation](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md).

---

## Documentation

| Document | Purpose |
| --- | --- |
| [English manual](MANUAL_EN.md) | Installation, UI workflow, inputs, outputs, troubleshooting |
| [한국어 매뉴얼](MANUAL_KO.md) | 설치, UI 워크플로우, 입력, 출력, 문제 해결 |
| [Modified Peptide Support](docs/MODIFIED_PEPTIDE_SUPPORT_V4.md) | Stage-wise modified chemistry support and limitations |
| [Token Registry / Sequence Grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md) | Canonical, modified, linker, tag, and terminal notation rules |
| [Design / Structure Theory](docs/DESIGN_STRUCTURE_THEORY_V4.md) | V4 design-objective and structure-evidence framework |
| [PSB Conformer Engine](docs/PSB_CONFORMER_ENGINE.md) | Conformer generation, steric audit, and Top-5 path |
| [Simulation / Structure Evidence](docs/SIMULATION_STRUCTURE_EVIDENCE.md) | Structure comparison and external simulation hand-off boundary |
| [SPPS V5 Integration](docs/SPPS_V5_INTEGRATION.md) | Embedded evidence-driven SPPS workflow |
| [Public Data Policy](PUBLIC_DATA_POLICY.md) | Public/private data boundary |
| [Release Notes](RELEASE_NOTES_V4.0.0.md) | V4.0.0 release summary |
| [Changelog](CHANGELOG.md) | Development history |

---

## Citation

If Pepforge or Pepforge-generated workflows materially contribute to academic work, cite the **exact release used**. GitHub can read the repository metadata directly from [CITATION.cff](CITATION.cff).

Recommended repository citation:

> Woo, S. *Pepforge: An Integrated Peptide Research Workbench*. Version 4.0.0, 2026. https://github.com/poowsh1407/Pepforge

If a DOI-backed release becomes available, prefer the DOI-linked citation for that release.

---

## License

Pepforge uses the custom **Pepforge Public Academic Citation License**. It is not presented as an OSI-approved open-source license. Read [LICENSE](LICENSE) before redistribution, derivative distribution, or commercial use.

---

## Contributing and security

Bug reports should include the Pepforge version, operating system, Python version, launch method, affected module, minimal reproducible input, reproduction steps, and relevant logs with confidential or unpublished information removed.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

---

<div align="center">

**Pepforge V4.0.0**  
From peptide sequence to structure, synthesis planning, interaction review, and validation hand-off.

</div>
