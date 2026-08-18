# Pepforge

Peptide-focused desktop workbench for sequence analysis, modified-peptide design, conformational ensemble generation, SPPS planning, and docking-oriented screening.

**Public baseline:** 3.0.0 · **Platform focus:** Windows · **Author:** Sanghun Woo

**Current STD:** Pepforge V3.0.0 with the integrated SPPS Planner V4 evidence workflow (2026-08-13).

[한국어](README_KO.md) · [STD baseline](STD_BASELINE.md) · [Complete user manual](MANUAL_EN.md) · [Scientific scope](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md) · [SPPS V4 method](docs/SPPS_V4_EVIDENCE_WORKFLOW.md) · [Release notes](RELEASE_NOTES_V3.0.0.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

> Pepforge is research software. Its structures, scores, contacts, and synthesis recommendations are hypotheses or planning aids—not experimental measurements, native-structure proof, or medical guidance.

## Workflow

The V3 Modern/Classic hybrid launcher presents the six active modules in one workflow sidebar and shows the selected module's purpose, outputs, workspace, and explicit launch action. Docking Workbench appears once.

```text
sequence / target
  → hotspot prioritization
  → modified-peptide candidate design
  → peptide conformational ensemble (Top 5 representatives)
  → SPPS plan and material estimate
  → docking-oriented screening
  → export for external validation
```

| Module | Purpose | Important boundary |
| --- | --- | --- |
| Hot Spot Finder | Prioritize candidate sequence regions | Scores are prioritization evidence |
| Peptide Design Engine | Generate canonical and selected modified-peptide candidates | Candidates require chemistry and synthesis review |
| Structure Builder | Generate and classify peptide conformers | It does not determine one physiological structure |
| SPPS Planner V4 | Prepare editable synthesis steps, materials, process times, evidence review, and literature-aware warnings | Recommendations are planning evidence, not a validated laboratory SOP |
| Docking Workbench | Screen poses and contacts for prioritization | Internal scores are not experimental affinity or Kd |
| External Tools | Prepare hand-off files and directories | External programs must be installed separately |

## Sequence-to-structure scope

Pepforge searches multiple peptide backbone families, including α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, and coil/mixed states. A successful public Top-5 build ranks and exports exactly five real coordinate candidates; an incomplete set is reported as a failure, not silently accepted.

Canonical L-peptides can receive torsion-basin seeds so a short stochastic search does not miss a major family. Sequence context, terminal chemistry, D-residues, supported modifications, cyclization/disulfide constraints, and α/β/γ-peptidomimetic patterns are handled only where the parser and evidence rules support them. A seed is a search candidate—not a predicted equilibrium population.

PDE starts with no active target or locked example motifs. Its default exploratory mode records a new seed for every run and applies an explicit final sequence-diversity filter; lock the seed or use `Repeat Last Run` for exact reproducibility.

Typical outputs:

```text
<name>_conformer_ensemble.sdf
<name>_conformer_families.csv
<name>_backbone_torsions.csv
```

See the [complete user manual](MANUAL_EN.md) and [scientific scope](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md).

## Install and run

Requirements: Python 3.10+ with Tk support. A dedicated virtual environment is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

Launch one module directly:

```bash
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

Use `python main_launcher.py --help` to confirm options. RDKit is required for real 3D generation. PyMOL and external docking/MD programs are optional external applications.

For installation checks, every module, exact button order, notation grammar, output interpretation, and troubleshooting, read the [English complete manual](MANUAL_EN.md) or [Korean complete manual](MANUAL_KO.md).

## SPPS V4 evidence workflow

Pepforge embeds the sanitized SPPS Planner V4 single-plan workflow. Generate/Update creates the editable Plan, Materials, Total Materials, Checklist, and cleavage output. `Apply Change` commits reviewed table edits explicitly.

Loading, coupling, and cleavage advice follows conservative evidence rules:

- `verified` records may support exact-condition Apply; `parsed` records remain review evidence unless the operator explicitly confirms the exact record.
- `incomplete` and `excluded` records cannot silently become actionable.
- Cleavage matching is sequence-first. Product names are descriptive metadata, not the action key.
- One recommendation transfers one coherent historical condition. Cocktail components are never mixed across records, and a fitted model never supplies an invented optimum for Apply.
- Loading and cleavage time are recorded independently and do not change reagent stoichiometry.

LOT Number and Batch Manager are intentionally excluded from the Pepforge integration. No real laboratory history is bundled in the public experimental seed directory.

## Verification

```bash
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

The consolidated source baseline passed automated compile, source-integrity, runtime-validation, regression, verification-matrix, and release-gate checks in the development environment. Native Windows GUI, real RDKit 3D export, PyMOL session opening, and third-party docking/MD execution must still be verified on the target machine.

## Public-data policy

This repository contains source code, curated public chemical catalogs, empty schemas/templates, examples, and tests. It does not contain private laboratory history, company records, credentials, unpublished datasets, local models, or runtime project files. Read [PUBLIC_DATA_POLICY.md](PUBLIC_DATA_POLICY.md) before publishing a fork or attaching a release asset.

## Modified-peptide notation

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Gal-GH-dab(EEEK)-NH2
```

PSB resolves `Ac-/AC-` as acetyl and `Pal-/PAL-` as palmitoyl. Enter individual residues with explicit separators, such as `A-C-` or `P-A-L-`.

Unsupported building blocks or parameters remain explicitly unsupported or estimated. Pepforge does not invent residue propensities, force-field parameters, or experimental results.

## Dependency profiles

| File | Profile |
| --- | --- |
| `requirements.txt` | Core desktop runtime, including RDKit |
| `requirements-ml.txt` | Optional ML components |
| `requirements-research.txt` | Optional research stack |
| `requirements-web.txt` | Optional web components |

## Repository map

```text
apps/                    bundled application engines
peptiforg_core/          shared scientific and workflow logic
spps_v4_gui/             SPPS Planner V4 workflow and experimental-data layer (LOT/Batch excluded)
suite_gui/               desktop module interfaces
tests/                   unit, regression, and contract tests
docs/                    scientific, API, and release documentation
installer/               Windows build configuration
main_launcher.py         desktop entry point
pepforge_cli.py          workflow and release-audit CLI
```

Runtime outputs use per-tool workspaces. This is application-level workspace isolation, not an operating-system security sandbox.

## Contributing, citation, and license

Bug reports should include version, OS, Python version, launch method, module, minimal input, reproduction steps, and relevant logs. Remove confidential or unpublished data before posting.

Changes must not introduce runtime monkey patches, placeholder features presented as complete, fabricated scientific output, or silent feature loss. See [CONTRIBUTING.md](CONTRIBUTING.md).

If Pepforge materially contributes to academic work, cite the exact release. Metadata is in [CITATION.cff](CITATION.cff).

Pepforge uses the custom **Pepforge Public Academic Citation License** and is not represented as OSI-approved. Read [LICENSE](LICENSE) before redistribution or commercial use.
