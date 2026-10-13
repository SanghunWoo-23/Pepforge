<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge" width="150">

# Pepforge

### Integrated peptide design, structure generation, docking, SPPS planning, and interaction analysis

**Pepforge V5.0.0 · Public Research Source Release**

[![Release](https://img.shields.io/badge/release-v5.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#quick-start)
[![Release Gate](https://img.shields.io/badge/release_gate-25%2F25-16A34A?style=for-the-badge)](#verification)

**[한국어](README_KO.md) · [Quick start](#quick-start) · [Capabilities](#capabilities) · [Structure & Docking Studio](#structure--docking-studio) · [SPPS Planner](#spps-planner) · [Scientific scope](#scientific-scope) · [Manual](MANUAL_EN.md)**

</div>

---

## Overview

Pepforge is a Windows-first desktop research workbench that connects the peptide workflow from **sequence-level prioritization** to **candidate design**, **3D conformer generation**, **protein–peptide docking**, **interaction analysis**, and **SPPS planning**.

V5.0.0 extends the V4 workflow into a more integrated native protein–peptide analysis environment while preserving the same core principle:

> **Computational evidence must remain distinguishable from experimental evidence.**

Pepforge supports canonical peptides and, where explicitly supported, terminal chemistry, D-residues, non-natural residues, linkers, labels, and other modified-peptide notation.

```text
Target / protein sequence
        ↓
Hot Spot Finder
        ↓
Peptide Design Engine (PDE)
        ↓
Structure & Docking Studio
   ├─ peptide structure generation
   ├─ receptor / peptide preparation
   ├─ native docking
   ├─ interaction analysis
   ├─ mechanics / trajectory review
   └─ result interpretation
        ↓
SPPS Planner
        ↓
Evidence export / downstream validation
```

Pepforge does **not** convert an internal docking score into experimental affinity, does **not** fabricate unsupported chemistry, and does **not** treat generated structures as proof of a native biological state.

---

## Capabilities

| Module | What it does |
| --- | --- |
| **Workflow Mode** | Connects Hot Spot → PDE → Structure & Docking → SPPS while preserving project/session and candidate lineage |
| **Hot Spot Finder** | Screens protein/peptide sequences and ranks candidate regions |
| **Peptide Design Engine (PDE)** | Generates and evaluates peptide candidates with explicit design objectives, chemistry-aware handling, and candidate tracking |
| **Structure & Docking Studio** | Combines peptide structure generation, receptor preparation, native docking, interaction analysis, mechanics/trajectory review, and result interpretation |
| **SPPS Planner** | Provides synthesis planning, materials, checklist, cleavage review, project handling, and decision-support workflows |
| **Validation / benchmark tools** | Supports benchmark preparation, provenance tracking, calibration, release auditing, and external validation hand-off |

### Design modes

PDE retains explicit scientific-design objectives rather than hiding them inside one opaque score:

- **Interaction Only**
- **Interaction First**
- **Balanced**
- **Structure Guided**
- **Structure Exploration**

Structure-guided modes require explicit structural intent. Pepforge does not invent a target conformation when one has not been supplied.

---

## Structure & Docking Studio

V5 consolidates the peptide structure and docking workflow into a single primary workspace.

The Studio is designed to move from sequence to structural hypotheses without forcing the user to switch repeatedly between disconnected windows.

### Main workflow

```text
Peptide sequence / modified construct
        ↓
Conformer generation
        ↓
Candidate structure review
        ↓
Target / receptor loading
        ↓
Native docking
        ↓
Interaction evidence
        ↓
Optional mechanics / trajectory review
        ↓
Interpretation / export
```

### Peptide structure generation

Supported conformational families include, where chemically applicable:

- α-helix
- 3₁₀-helix
- β-extended / strand-like
- β-hairpin-like
- PPII
- turn-rich
- coil / mixed

Generated conformers are **starting hypotheses for inspection and downstream validation**, not experimentally established conformational populations.

### Native docking

Pepforge V5 includes a native docking path intended for pose generation and structural screening.

The native docking score is an **internal dimensionless pose-search / ranking score**.

It must **not** be reported as:

- ΔG,
- Kd,
- experimental affinity,
- biological activity,
- or a validated free-energy estimate.

### Interaction analysis

Pepforge can inspect residue-centered structural evidence including:

- hydrogen-bond candidates,
- hydrophobic contacts,
- salt bridges / ionic interactions,
- π–π interactions,
- cation–π interactions,
- van der Waals contacts / clashes,
- disulfide geometry,
- water-mediated contact candidates,
- metal coordination,
- halogen-bond geometry,
- aromatic–sulfur interactions,
- weak C–H···O/N interactions,
- NH–π / amino–aromatic interactions.

Geometry-based interaction evidence is **structural screening evidence**, not automatic proof of binding strength.

### Native Mechanics / trajectory review

V5 provides a native mechanics and trajectory-analysis path for exploratory structural review.

It is **not presented as production-grade molecular dynamics**. Production MD requires validated force-field parameters, timestep / ensemble controls, and a validated simulation backend.

---

## Modified-peptide support

Pepforge uses explicit tokenization so terminal chemistry, residue identity, and linker/tag notation remain distinguishable.

Examples:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

Important examples:

| Input | Interpretation |
| --- | --- |
| `Ac-` / `AC-` | N-terminal acetyl modifier |
| `Pal-` / `PAL-` | N-terminal palmitoyl modifier |
| `A-C-` | Ala–Cys residue sequence |
| `P-A-L-` | Pro–Ala–Leu residue sequence |
| `FITC-` / `Biotin-` | Registered label / tag token when supported |
| `AEEA`, `Ahx`, PEG tokens | Registered linker chemistry when supported |
| D / non-natural residue tokens | Preserved as explicit chemistry rather than silently converted to canonical L-residues |

Support remains **stage-specific**. A construct may be parsed and preserved even when a unique all-atom derivative or force-field parameter set is unavailable.

Pepforge reports that limitation instead of fabricating a structure or parameter set.

---

## SPPS Planner

Pepforge integrates an SPPS planning workflow as part of the peptide research environment.

The current integration provides:

- Project Manager workflow
- Batch-oriented project handling
- editable synthesis Plan
- step-wise Materials
- Total Materials
- Checklist
- cleavage review
- sequence / construct transfer from Pepforge workflows
- project/session persistence
- literature/evidence guidance
- user-provided experimental evidence support

The SPPS Planner remains a synthesis-planning and decision-support tool. It does not guarantee:

- synthesis yield,
- purity,
- reaction completion,
- cleavage success,
- or laboratory safety.

Public Pepforge packages must not include private laboratory history, credentials, local experimental databases, or internal operator records.

---

## Public benchmark and provenance support

V5 includes infrastructure for public protein–peptide benchmark preparation and validation.

Supported provenance workflows include:

- public benchmark registry handling,
- RCSB PDB coordinate retrieval / local cache use,
- receptor / peptide chain normalization,
- SHA-256 provenance records,
- UniProtKB sequence / identity metadata,
- train / holdout split auditing,
- leakage checks,
- docking-score / structural-recovery calibration,
- validation workspace auditing,
- release dossiers.

RCSB or UniProt provenance does **not** by itself establish correctness of a docking result.

A deterministic holdout split also does **not** automatically prove sequence-independent generalization.

---

## UI / workflow improvements in the final V5 build

The final V5 UI polish focuses on making the application behave more like a conventional desktop scientific workbench.

Highlights include:

- integrated **Structure & Docking Studio** instead of exposing overlapping PSB / Docking paths as separate primary workflows,
- larger peptide-sequence editing area,
- larger default workspaces,
- standard mouse-wheel scrolling in long analysis pages,
- scroll handling in both **Structure & Docking Studio** and **Workflow Mode**,
- stabilized canvas / viewport sizing to avoid layout stretching while dragging scrollbars,
- reduced end-of-page scroll event accumulation,
- updated SPPS Planner launch integration,
- compatibility access to legacy / advanced docking review where needed.

---

## Quick start

### Requirements

- Windows 10 or 11 recommended
- 64-bit Python **3.10+**
- Tk support
- RDKit for 3D structure generation

Optional external tools may be used for downstream review or validation, but are installed separately.

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

If several Python installations are present on Windows:

```bat
py main_launcher.py
```

### Direct module launch

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool spps
python main_launcher.py --tool workflow
python main_launcher.py --tool external
```

Compatibility / advanced routes may remain available for specific review workflows, but the primary V5 structural workflow is **Structure & Docking Studio**.

For full UI instructions, inputs, outputs, and troubleshooting, use [MANUAL_EN.md](MANUAL_EN.md) or [MANUAL_KO.md](MANUAL_KO.md).

---

## Typical workflow

1. **Create or open a project/session.**
2. **Enter a target/protein sequence** and run Hot Spot Finder when sequence-level prioritization is needed.
3. **Generate or evaluate peptide candidates in PDE.**
4. **Open the selected candidate in Structure & Docking Studio.**
5. **Generate and review peptide conformers.**
6. **Load the receptor / target structure.**
7. **Run native docking and inspect ranked pose hypotheses.**
8. **Review interaction evidence and, where appropriate, mechanics / trajectory outputs.**
9. **Transfer the active construct to SPPS Planner for synthesis planning.**
10. **Export results for external review, benchmark comparison, or downstream validation.**

Evidence generated at different stages remains distinguishable rather than being collapsed into an unsupported universal confidence score.

---

## Repository structure

```text
Pepforge/
├─ main_launcher.py
├─ pepforge_cli.py
├─ suite_gui/
├─ peptiforg_core/
├─ pepforge_structure_tool/
├─ apps/
├─ tests/
├─ docs/
├─ data/
├─ installer/
├─ MANUAL_EN.md
├─ MANUAL_KO.md
├─ README.md
└─ README_KO.md
```

Runtime workspaces, generated outputs, caches, credentials, private experimental history, and internal development handover material are excluded from the public source package.

---

## Verification

The final V5 public build was regression-tested after the UI and packaging cleanup.

| Check | Result |
| --- | ---: |
| V5 regression tests | **130 passed / 0 failed** |
| Legacy V4 release / verify / integrity audit | **6 passed / 0 failed** |
| Legacy full-package / regression / source-integrity audit | **7 passed / 0 failed** |
| Release Gate | **25 / 25 passed** |
| Compile errors | **0** |

Representative UI checks also covered:

- normal mouse-wheel scrolling in Structure & Docking Studio,
- normal mouse-wheel scrolling in Workflow Mode,
- stable outer canvas width while dragging scrollbars,
- prevention of repeated end-of-page wheel-event accumulation,
- SPPS Planner launch-path compatibility.

You can run the included checks with:

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Native Windows rendering, packaged installer / EXE behavior, third-party simulation engines, GPU-specific paths, and external applications remain environment-specific checks.

---

## Scientific scope

Pepforge is intended for:

- research prioritization,
- reproducible computational preparation,
- peptide-structure hypothesis generation,
- docking / interaction screening,
- synthesis planning,
- validation hand-off.

Pepforge output alone does **not** establish:

- experimental binding affinity or Kd,
- binding free energy,
- native in-vivo peptide conformation,
- biological efficacy,
- synthesis yield or purity,
- validated laboratory SOPs,
- production-grade MD validity.

Unsupported building blocks, force-field parameters, experimental results, or optimum synthesis conditions must not be invented.

---

## Documentation

| Document | Purpose |
| --- | --- |
| [English manual](MANUAL_EN.md) | Installation, workflow, inputs, outputs, troubleshooting |
| [한국어 매뉴얼](MANUAL_KO.md) | 설치, 워크플로우, 입력, 출력, 문제 해결 |
| [Public Data Policy](PUBLIC_DATA_POLICY.md) | Public/private data boundary |
| [Changelog](CHANGELOG.md) | Public development / release history |
| [Contributing](CONTRIBUTING.md) | Bug reports and contribution guidance |
| [Security](SECURITY.md) | Security reporting and public-package precautions |

Detailed internal handover notes and future-version roadmaps are intentionally maintained **outside the public GitHub source package**.

---

## Citation

If Pepforge or Pepforge-generated workflows materially contribute to academic work, cite the **exact release used**.

If `CITATION.cff` is included in the repository, GitHub can expose the citation metadata directly.

Recommended repository citation:

> Woo, S. *Pepforge: An Integrated Peptide Research Workbench*. Version 5.0.0, 2026. https://github.com/SanghunWoo-23/Pepforge

If a DOI-backed release becomes available, prefer the DOI-linked citation for that exact release.

---

## License

Pepforge uses the license distributed with the public repository.

Read [LICENSE](LICENSE) before redistribution, derivative distribution, or commercial use.

---

## Contributing and security

Bug reports should include:

- Pepforge version,
- operating system,
- Python version,
- launch method,
- affected module,
- minimal reproducible input,
- reproduction steps,
- relevant logs with confidential or unpublished information removed.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

---

<div align="center">

**Pepforge V5.0.0**  
From peptide sequence to design, structure, docking, synthesis planning, interaction review, and validation hand-off.

</div>
