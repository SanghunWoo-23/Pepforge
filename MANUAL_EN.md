# Pepforge Complete User Manual

**Suite version:** Pepforge V3.0.0  
**Embedded synthesis component:** SPPS Planner V4.0.0  
**Document baseline:** 2026-08-13

Pepforge connects peptide sequence analysis, candidate design, peptide-only conformer generation, SPPS planning, docking-oriented screening, and external-validation hand-off in one desktop workflow. This manual explains the controls, input grammar, outputs, limitations, and recovery steps needed by a first-time user.

> Pepforge outputs are research hypotheses and prioritization aids. Structures, scores, contacts, and synthesis conditions are not experimental measurements, medical advice, or proof of efficacy.

## Contents

1. Version and scope
2. Installation
3. Launch and interface
4. 15-minute quick start
5. Peptide sequence grammar
6. Hot Spot Finder
7. Peptide Design Engine
8. Peptide Structure Builder
9. SPPS Planner V4
10. Docking Workbench
11. External Validation
12. Project and output management
13. Scientific interpretation
14. Troubleshooting
15. CLI and release verification
16. Publication and citation

## 1. Version and scope

### 1.1 Version contract

| Item | Version | Meaning |
| --- | --- | --- |
| Integrated suite | Pepforge V3.0.0 | Launcher and public release version |
| Synthesis component | SPPS Planner V4.0.0 | Component embedded in Pepforge |
| Historical internal labels | Some v1.x/v2.x names | Component lineage, not the suite version |

Use **Pepforge V3.0.0 with SPPS Planner V4.0.0** in releases and citations. Do not call the suite “Pepforge V4.”

### 1.2 What each module does

| Step | Module | Purpose | Boundary |
| --- | --- | --- | --- |
| 1 | Hot Spot Finder | Prioritize sequence windows | Does not prove a binding site |
| 2 | Peptide Design Engine | Generate and filter canonical/modified candidates | Does not guarantee potency, safety, or affinity |
| 3 | Peptide Structure Builder | Generate up to five representative peptide conformers | Does not determine one in-vivo native structure |
| 4 | SPPS Planner V4 | Build editable plans, quantities, checklists, and evidence views | Does not create a validated laboratory SOP |
| 5 | Docking Workbench | Compare pose/contact hypotheses | Does not replace Vina, MD, or binding assays |
| 6 | External Validation | Prepare hand-off folders | Does not execute external engines |

The public package contains code, curated public catalogs, empty schemas, examples, and tests. It excludes private laboratory history, credentials, unpublished datasets, runtime projects, and bundled local models. `actual_runs.csv` contains only its schema/header.

## 2. Installation

### 2.1 Recommended environment

- Windows 10/11, 64-bit
- Python 3.10 or later with Tk/Tcl
- 8 GB RAM or more recommended
- RDKit for real 3D generation
- Optional external applications: PyMOL, AutoDock Vina, Open Babel, GROMACS

The core desktop workflow does not require a GPU. External high-cost docking or MD needs its own environment.

### 2.2 Extract and install

Extract the ZIP to a short writable path such as `C:\Pepforge_V3.0.0`. For the first test, avoid a read-only directory or heavily synchronized cloud folder.

Windows:

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

macOS/Linux source run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

The primary GUI validation target is Windows. Linux may require a separate OS Tk package.

### 2.3 Verify the environment

```bash
python -c "import tkinter; print('Tk OK')"
python -c "import rdkit; print('RDKit OK')"
python pepforge_cli.py version
```

The version command must report `3.0.0`. The SPPS window title should report `SPPS Planner V4.0.0`.

### 2.4 Dependency profiles

| File | Use |
| --- | --- |
| `requirements.txt` | Core desktop runtime |
| `requirements-ml.txt` | Optional user-data ML features |
| `requirements-research.txt` | Optional research stack |
| `requirements-web.txt` | Optional web-related stack |

Install the core file first. Add only the profile you need.

## 3. Launch and interface

Run the integrated launcher:

```bash
python main_launcher.py
```

It opens the `Modern / Classic Hybrid Workspace`. Select a module in the left `WORKFLOW` sidebar; the center pane explains its purpose, workflow, outputs, and explicit launch action, while the right `CONTEXT` pane shows the selected tool and isolated workspace. Use `File` for project/log folders, `View > Display Density` for Compact/Standard/Comfortable spacing, and `Tools` for the advanced Workflow Mode. Docking Workbench appears once as workflow step 5.

Direct launch commands:

```bash
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

Common control meaning:

- `Browse` selects a path.
- `Analyze` parses and validates input.
- `Apply` explicitly commits edited settings.
- `Generate`, `Build`, or `Run` starts computation or file generation.
- `Open Output Folder` opens the destination.

Do not click a long-running action repeatedly. Check progress and the module log.

## 4. 15-minute quick start

Start with a short canonical peptide before adding modifications.

1. Open Hot Spot Finder, paste a canonical sequence in `Protein or Peptide Sequence`, and click `Analyze Sequence`.
2. Open PDE, enter target/settings, click `1. Apply Settings`, then `2. Generate Candidates`.
3. Open PSB, enter one candidate, choose `Physiological aqueous` and `Fast Top 5 (recommended)`, click `Analyze`, then `Build Top 5 Structures`.
4. Open SPPS Planner, enter sequence/scale/resin/loading, click `Generate`, edit the tables, and click `Apply Change`.
5. Open Docking Workbench, validate target and peptide input, then click `Run Screening`.
6. Use External Validation to create a Vina or GROMACS hand-off folder when quantitative external work is required.

At every step, review warnings before passing an output forward.

## 5. Peptide sequence grammar

### 5.1 Canonical residues

Compact one-letter sequences are supported:

```text
EEMQRR
WKWLKK
```

Use explicit separators when residue identity could be confused with a multi-letter modifier:

```text
A-C-D-E
P-A-L
```

Sequence-only input is safest. Remove FASTA headers, numbering, and comments unless a specific module explicitly accepts them.

### 5.2 Terminal chemistry and delimiter rule

```text
Ac-EEMQRR-NH2
Pal-AEEA-KKLL-NH2
Biotin-GGGK-NH2
FITC-KKLL-NH2
```

| Input | Interpretation |
| --- | --- |
| `Ac-`, `AC-`, `ac-` | N-terminal acetyl modifier |
| `Pal-`, `PAL-`, `pal-` | N-terminal palmitoyl modifier |
| `FITC-` and accepted case variants | FITC modifier when supported |
| `Biotin-` and accepted case variants | Biotin modifier when supported |
| `-NH2` | C-terminal amidation |

The dash after a modifier is significant:

- `AC-EEMQRR` means an acetylated peptide.
- `ACEEMQRR` means residues A-C-E-E-M-Q-R-R.
- `PAL-EEMQRR` means a palmitoylated peptide.
- `PALEEMQRR` means residues P-A-L-E-E-M-Q-R-R.
- Use `A-C-...` or `P-A-L-...` when you mean explicit residues.

### 5.3 Linkers, tags, and non-natural units

```text
Pal-AEEA-dab(KKEK)-dG-NH2
Gal-GH-dab(EEEK)-NH2
Ac-K(AEEA-Biotin)-KLL-NH2
```

`AEEA` is one linker token when present in the registry. `-AEEA-` is the safest boundary form. Parentheses express a supported branch/substitution location.

Support levels differ by module:

| Status | Meaning | Action |
| --- | --- | --- |
| Recognized + graph supported | Name and explicit atom graph are available | Inspect atoms, bonds, chirality, and mass |
| Planning only | SPPS catalog entry exists, but no 3D graph | Do not expect PSB structure export |
| Manual required | Exact reagent form, MW, or attachment is ambiguous | Verify the CoA and enter the exact form |
| Unsupported | No parser/computation contract | Define the token; do not substitute a surrogate |

PSB must not silently replace unknown chemistry with glycine or an arbitrary carbon chain. A blocked build is safer than a fabricated structure.

Recommended practice:

1. Separate modifiers and residues with dashes.
2. Use registry spelling for multi-letter tokens.
3. Specify branch position with the supported grammar.
4. Run `Analyze` or inspect the parser preview first.
5. Read every `raw`, `token`, `class`, `note`, and `warning` field.

## 6. Hot Spot Finder

### 6.1 Inputs and settings

- `Sequence file (optional)`: supported FASTA/sequence input.
- `Output folder`: destination.
- `Protein or Peptide Sequence`: direct paste input; no file is required.

Direct sequence analysis is a core contract. An empty file field must not disable pasted input.

| Setting | Meaning | Starting value |
| --- | --- | --- |
| `Use ESM (optional, slower)` | Optional embedding assistance | Off |
| `Window` | Candidate window length | 15 |
| `Overlap` | Overlap between windows | 5 |
| `Top N` | Number of candidates displayed | 30 |
| `Min score` | Minimum retained score | 0.0 |

For a short peptide, reduce the window to a sensible length. Excessive overlap creates redundant candidates.

### 6.2 Run and export

1. Paste a sequence or choose a file.
2. Confirm the output folder.
3. Click `Analyze Sequence` once.
4. Monitor progress and `Log`.
5. Inspect rank, hotspot residues, center, score, and explanation in `Candidate Table`.

Available actions include `Export Display XLSX`, `Export PyMOL PDB`, `Export Motif Hints`, `Open output folder`, and `Load Example`.

A high score is prioritization evidence, not a validated interface. Check structure, accessibility, disorder, PTMs, isoforms, and experimental data.

## 7. Peptide Design Engine

### 7.1 Tabs and apply contract

The tabs are `Design Settings`, `Chemistry / Constraints`, `Hot Spot / Docking`, `Data / ML`, `Expert Override`, and `Log / Results`.

The bottom actions are intentionally ordered:

1. `1. Apply Settings`
2. `2. Generate Candidates`

After a setting changes, the status reads `Settings changed — click Apply Settings`. Apply changes to preset, length mode, length bounds, and chemistry before generation. This avoids hidden state changes.

### 7.2 Design Settings

| Control | Meaning |
| --- | --- |
| `Target sequences` | Target sequence input |
| `Preset` | Starting bundle of settings |
| `Target Mode` | Single/multi-target intent |
| `Design Mode` | Candidate strategy |
| `Binder Mode` | Candidate balance |
| `Population`, `Generations` | Search size and iterations |
| `Final Top K` | Number of retained candidates |
| `Random Seed` | Seed used when `Lock seed for exact repeat` is enabled |

By default the seed is unlocked: every `Generate Candidates` action receives a new cryptographically sourced integer, and the actual seed is written to the log and config snapshot. Enable `Lock seed for exact repeat` to reproduce the entered seed. `Repeat Last Run` reuses the complete previous configuration and seed exactly. The public UI starts with no active target and no locked RGD/KLVFF examples; examples are applied only by an explicit user action.

The visible final Top K is selected with a normalized sequence-distance filter before the threshold is relaxed. Consequently, a new exploratory seed should change the candidate set, although strongly constrained targets or motifs can still produce scientifically reasonable overlap.
| `Peptide Length Mode` | Fixed or ranged length behavior |
| `Fixed/Min/Max Length` | Length bounds |
| `Length Measurement` | Residue-based or token-based counting |
| `Trim to length` | Handling of excess length |

Start with a small population and generation count. Confirm the contract before a larger search.

### 7.3 Chemistry and constraints

Review terminal chemistry, D-residues, selected non-natural residues, linkers, tags, locked motifs, cyclization, disulfides, and branches. Confirm whether length is counted by residues or tokens; a linker/tag should not accidentally alter the intended peptide residue length.

Hot Spot/Docking inputs may use exported motif hints, a PDB-derived region, or a manually locked motif. Verify chains and residue numbering. A sequence-only complex input is a starting package, not a proven pose.

### 7.4 Data/ML and Expert Override

- No bundled untrained reranker is presented as useful science.
- Trained reranking requires user-provided labeled data.
- A CSV prior is used only when explicitly selected and reviewed.
- Model output is not Kd, ΔG, IC50, or success probability.
- Small or mismatched datasets should not override chemistry and external validation.

Expert JSON is applied last. First run without it, add a minimal override, click Apply, inspect the log, and retain the config snapshot.

Review sequence, modifications, charge, solubility, aggregation, chemical stability, SPPS feasibility, and motif retention together. Do not choose a candidate by one score alone.

## 8. Peptide Structure Builder

### 8.1 Purpose and inputs

PSB interprets a peptide sequence and supported chemistry, samples multiple backbone families, and exports exactly five representative conformers for a successful public Top-5 build. If five real coordinate candidates cannot be generated, ranked, and written, the worker reports failure instead of presenting a partial set as complete. It is not a protein native-structure predictor and does not calculate an in-vivo equilibrium population.

The main inputs are `Peptide sequence`, `Output name`, `Output folder`, pH, temperature, ionic strength, environment, a condition preset, and a build preset. The current UI uses `Peptide sequence`, not the older `Peptide notation` label.

### 8.2 Condition presets

| Preset | Defaults | Interpretation |
| --- | --- | --- |
| `Physiological aqueous` | pH 7.4, 37 °C, 150 mM | Physiological aqueous metadata |
| `Neutral room temp` | pH 7.0, 25 °C, 100 mM | Neutral room-temperature metadata |
| `Membrane-mimetic metadata` | pH 7.4, 37 °C, 150 mM | Membrane-oriented interpretation label |
| `Custom` | User values | User-recorded metadata |

These values are metadata, not explicit-solvent, membrane, or constant-pH simulation.

### 8.3 Build presets

| Preset | Search settings | Use |
| --- | --- | --- |
| `Fast Top 5 (recommended)` | 5 initial conformers, 80 iterations, 2 adaptive retries, evidence-fast family profile | First run and routine checks |
| `Balanced` | 12 initial conformers, 200 iterations, 3 adaptive retries, evidence-balanced profile | Wider family/RMSD exploration |
| `Thorough` | 30 initial conformers, 500 iterations, 4 adaptive retries, evidence-thorough profile | Larger final exploration |

All presets enforce the same exact-five output contract. The presets differ in actual sampling budget, retry budget, RMSD threshold, and evidence-guided family priority. Thorough means more search, not a guarantee of a truer structure.

### 8.4 Analyze and build

1. Enter the sequence and click `Analyze`.
2. Read position, raw token, normalized token, class, note, and warning in `Chemistry interpretation`.
3. Use `Open Token Map` to check registry support.
4. Resolve unknown, ambiguous, or planning-only tokens.
5. Choose a writable output folder and build preset.
6. Click `Build Top 5 Structures` once.
7. The calculation runs in an isolated worker; inspect the result with `Open Output`.

If it is slow, test `Fast Top 5`, a short canonical sequence, and a local output folder. Check RDKit and whether antivirus blocked the worker.

### 8.5 Backbone families and special cases

The search may include α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, and coil/mixed families. Helix propensity coverage, i/i+3 and i/i+4 charge spacing, amphipathic moment, turn-compatible windows, β alternation, Pro/PPII context, and α/β/γ backbone detection now determine an auditable family-priority plan. The selected build preset controls how broadly that plan is sampled. Torsion seeds make a family available to the search; they are not measured populations.

α/β/γ-peptidomimetics, including BH3-like helical designs, require backbone-pattern-specific interpretation because substitution pattern can change helicity. PSB reports guidance/limitations for supported patterns and does not silently reuse an α-peptide propensity or geometry for an unsupported unit. Compare important results with CD, NMR, crystallography, and an appropriate parameterized simulation.

Typical output types:

```text
*_top5_conformers.sdf
*_top5_conformers.csv
*_top5_rank1.pdb ... *_top5_rank5.pdb
*_top5_compare.pml
*_conformer_families.csv
*_backbone_torsions.csv
```

Rank and relative energy are run-local values. They do not compare different chemistries or experimental affinity. Generated fraction is not equilibrium population. Inspect atoms, bonds, chirality, and terminal groups.

## 9. SPPS Planner V4

### 9.1 Active scope

The embedded component provides the single-plan, materials, checklist, cleavage, and evidence workflows. LOT Number and Batch Manager are intentionally excluded from the active Pepforge interface.

Before generation, review sequence, scale, resin/linker, resin loading, coupling/deprotection chemistry, loading/cleavage time, and modified building blocks. A generic reagent with ambiguous form or attachment is correctly marked manual-required.

### 9.2 Generate and Apply Change

`Generate` creates Plan, Materials, Total Materials, Checklist, cleavage, and risk/evidence views. After editing a table cell, click `Apply Change` to synchronize dependent tables and totals. Selecting or typing in a cell alone is not application.

Review in this order:

1. Plan: step, position, reagent, equivalents, repeats, time.
2. Materials: amount and unit per step.
3. Total Materials: aggregation and cleavage inclusion.
4. Checklist: physical execution order.
5. Cleavage: cocktail, ratio, time, sequence risk.
6. Evidence: source and status.
7. Apply Change after edits.
8. Compare export with the visible tables.

### 9.3 Evidence and cleavage rules

| Status | Meaning | Exact-condition Apply |
| --- | --- | --- |
| `verified` | Source and key conditions reviewed | Allowed when compatible |
| `parsed` | Structured but not fully verified | Explicit user confirmation required |
| `incomplete` | Required fields missing | Blocked |
| `excluded` | Exclusion rule applies | Blocked |

One recommendation must transfer one coherent historical condition. Components, time, and temperature are not mixed across records. A fitted model does not create an invented optimum for Apply.

Cleavage matching is sequence-first; product name is descriptive metadata. Unknown or incomplete cocktail components block exact Apply. Loading and cleavage time are independent process values and do not change stoichiometry.

`Ac-EEMQRR-NH2` has a regression contract for 30 equivalents and `TFA 95% / water 5% / no TIS`. That software test does not make it a validated SOP for every laboratory.

For Pal, FITC, Biotin, chelators, lipids, PEG/AEEA, or protected building blocks, verify exact form, MW, attachment, protection state, and position. Review difficult-sequence aggregation, aspartimide, diketopiperazine, oxidation, disulfide/cyclization, and cleavage risks.

Before export, confirm sequence, terminal chemistry, scale/loading units, every manual-required reagent, equivalents/repeats, cleavage total/time, inclusion in Total Materials, and that Apply Change was run.

## 10. Docking Workbench

Structure inputs include `Protein/complex PDB or mmCIF`, `Peptide PDB or peptide chain file`, and `Result file`. Sequence mode uses `Protein sequence`, `Peptide sequence`, and `Output folder`.

RCSB actions are `Search RCSB`, `Fetch selected to Target`, and `Open RCSB page`. Verify chains, missing residues, mutations, ligands, and the biological assembly in the source entry.

Target Prep lets you select chains and whether to keep waters, ions, and ligands before `Prepare Target`. Metal/cofactor and protonation decisions require mechanism-specific review. `Build Initial Complex` creates a starting hypothesis, not an optimized pose.

Screening workflow:

1. Provide inputs.
2. Click `Analyze`.
3. Click `Run Screening` once.
4. Monitor progress and the log.
5. Compare contacts, clashes, geometry, and ranking.
6. Use `Export` or `Open Folder`.

`Input data full`, `Results data full`, and `Advanced` expose detailed tables and advanced workflows, including external-result import, sessions, dashboards, experimental import, run comparison, and calibration/evidence tools.

Internal screening is a local geometry/contact hypothesis. It is not Vina energy, PRODIGY affinity, ΔG, Kd, Ki, or IC50. Quantitative claims require an appropriate docking engine, parameter review, convergence/control analysis, possible MD, and experiments.

## 11. External Validation

`Check again` checks PATH availability for AutoDock Vina, Open Babel, GROMACS, and WSL. Missing status means that the application is not installed or not discoverable; Pepforge does not bundle it.

For Vina:

1. Choose output, receptor, and ligand/peptide files.
2. Click `Export Vina Package`.
3. Review the generated guide and inputs.
4. Decide charge, PDBQT conversion, box center/size, and exhaustiveness externally.

For GROMACS:

1. Choose the peptide PDB.
2. Click `Export GROMACS Prep Folder`.
3. Read `README_GROMACS.txt`.
4. Confirm that the force field supports every modification, D-residue, linker, lipid, and tag.
5. Run topology, solvation, ionization, equilibration, production, and analysis in GROMACS.

A hand-off folder is not a completed docking or MD run.

## 12. Project and output management

Source runs use the repository or the selected output folder. Installed builds may use a user-writable application-data location. Use `Open project folder` and `Open runtime logs` to find the active paths.

Recommended layout:

```text
project_name/
  01_input/
  02_hotspot/
  03_design/
  04_structure/
  05_spps/
  06_screening/
  07_external_validation/
  08_experimental/
  config_and_notes/
```

Record sequence, target accession, config snapshot, seed, software version, and date for every run. Before public release, remove laboratory history, unpublished sequences/structures, credentials, local models/training data, personal information, restricted supplier documents, and personal paths from logs.

## 13. Scientific interpretation

Safe wording:

- “Candidates were computationally prioritized with Pepforge.”
- “Five representative starting conformers were generated.”
- “A contact-oriented internal screen was performed.”
- “An external docking/MD hand-off package was prepared.”

Unsupported wording:

- “Pepforge predicted the native structure.”
- “Rank 1 is the only in-vivo conformation.”
- “The internal score proves nanomolar Kd.”
- “Pepforge ran or replaced Vina/GROMACS.”
- “The SPPS recommendation is an optimized validated SOP.”

Recommended validation ladder: parser/chemistry review → Top 5 comparison → external docking → parameterized MD if appropriate → CD/NMR/crystallography → binding/functional assays → synthesis identity and purity.

## 14. Troubleshooting

| Symptom | First check | Action |
| --- | --- | --- |
| Launcher does not open | Python/Tk and active environment | Run in a terminal and inspect traceback |
| Module closes immediately | Runtime log | Launch that `--tool` directly |
| `ModuleNotFoundError` | Active Python | Reinstall `requirements.txt` |
| RDKit import failure | Interpreter mismatch | Print `sys.executable` and test import |
| Hot Spot direct input ignored | Empty/invalid sequence | Click Analyze Sequence and inspect Log |
| PDE Generate disabled | Settings not applied | Click Apply Settings |
| PDE length unexpected | Length Measurement | Check residue/token mode and re-apply |
| PSB token confusion | Delimiters/case | Use `A-C-`, `P-A-L-`, `-AEEA-` |
| PSB slow or worker exits | Preset, memory, path | Fast preset, short sequence, local folder |
| SPPS edits not reflected | Cell commit/Apply | Finish editing and click Apply Change |
| SPPS exact Apply blocked | Incomplete/unknown record | Complete and verify the source record |
| No docking result | Mode, file, chain | Analyze input and inspect Log |
| External tool not found | Install/PATH | Install, restart terminal, Check again |
| PyMOL does not open | Separate PyMOL install | Open PDB/PML manually |

A useful bug report includes suite/component version, OS, Python, source/installer, module, minimal shareable sequence, exact button sequence, expected/actual behavior, log, and screenshot. Remove confidential data.

## 15. CLI and release verification

```bash
python pepforge_cli.py --help
```

| Command | Purpose |
| --- | --- |
| `version` | Show suite version |
| `init-workflow`, `run-workflow` | Initialize/run a workflow |
| `experimental-template`, `import-experimental` | Create/import experimental-data records |
| `dashboard`, `evidence-autoscan`, `compare-runs` | Review and compare evidence |
| `validate-runtime` | Runtime diagnostics |
| `audit-package`, `regression-audit` | Package/regression audit |
| `release-integrity`, `verify-matrix`, `release-gate` | Public-release checks |

Use `python pepforge_cli.py <command> --help` for command-specific options.

```bash
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Automated checks do not replace native Windows GUI smoke tests, real RDKit export, PyMOL opening, external-engine execution, or scientific validation.

## 16. Publication and citation

Before publishing, read `PUBLIC_DATA_POLICY.md`, scan for secrets/private data, run the release gate, and align `VERSION.txt`, `CITATION.cff`, README, and release filename to `3.0.0`. Keep the SPPS component at its separate `4.0.0` label. Exclude runtime output, caches, backups, local models, and private data from source archives.

Citation metadata is in `CITATION.cff`. The repository uses the custom **Pepforge Public Academic Citation License** and is not represented as OSI-approved. Read `LICENSE` before redistribution or commercial use.

Final checklist:

- [ ] Suite and SPPS component versions are distinguished.
- [ ] Every token warning was reviewed.
- [ ] PDE settings were explicitly applied.
- [ ] All five PSB representatives were compared.
- [ ] SPPS edits were applied with Apply Change.
- [ ] Docking scores were not called affinity.
- [ ] External execution was documented accurately.
- [ ] Experimental/structural validation was planned.
- [ ] Private data was removed before publication.

Related documents: [README](README.md), [Scientific scope](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md), [Sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md), [SPPS parser contract](docs/SPPS_PARSER_CONTRACT.md), [SPPS V4 evidence workflow](docs/SPPS_V4_EVIDENCE_WORKFLOW.md), and [Docking guide](docs/DOCKING_WORKBENCH_USER_GUIDE.md).
