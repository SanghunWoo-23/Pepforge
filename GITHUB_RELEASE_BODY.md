# Pepforge V4.0.0 — Public Research Release

Pepforge V4.0.0 is a Windows-first peptide research workbench that connects **sequence prioritization → peptide design → structure generation → SPPS planning → protein–peptide interaction review → external validation hand-off** in one traceable workflow.

This release is the **public/data-sanitized source release**. It contains no private experimental history or local operator database.

## Highlights

### One connected peptide workflow

- Hot Spot Finder for sequence-level prioritization
- Peptide Design Engine with Pareto NSGA-II selection and five explicit scientific-design modes
- Peptide Structure Builder with sequence-aware, sterically screened ranked conformers
- Embedded SPPS Planner V5.0.0 Public/Data-Sanitized workflow
- Docking Workbench with readable residue-centered contact and conservative interaction review
- Candidate/project lineage and external PyMOL/docking/MD hand-off artifacts

### R14 — PSB PDBs now round-trip into Docking Workbench

R14 preserves peptide identity directly inside PSB-generated PDB files.

- peptide `SEQRES` records are written,
- exact Pepforge construct notation is stored in `REMARK 901 PEPFORGE_EXACT_SEQUENCE`,
- modifier/linker metadata is retained,
- residue-aware `ATOM` / `HETATM` coordinates are preserved,
- modifiers/linkers do not consume peptide residue numbering,
- Docking Workbench restores identity using **Pepforge metadata → SEQRES → ATOM/HETATM** fallback.

Examples such as `Ac-EEMQRR-NH2` and `Pal-AEEA-dK-NH2` can therefore be passed from PSB into Docking Workbench without losing the exact construct notation.

Chemistry with an explicit curated coordinate graph remains coordinate-bearing. Recognized chemistry without a unique derivative/attachment graph is **not** given fabricated all-atom coordinates.

### Modified-peptide aware by design

Pepforge preserves supported terminal groups, D-residues, non-natural residues, linkers, labels, and modified-peptide notation across the stages that can represent them. Support is reported stage-by-stage rather than as a blanket claim.

### SPPS workflow hardened

The embedded SPPS workflow retains the R12/R13 fixes:

- visible Project Manager Sequence is authoritative for Generate/Apply,
- stale legacy sequence state cannot override an intentionally blank visible field,
- automatic startup/idle refresh does not invoke the parser when no sequence has been entered,
- public release data remains sanitized and local evidence stays local.

### Conservative scientific boundaries

Pepforge does not present internal screening scores as experimental affinity, generated conformers as native-structure proof, or synthesis guidance as an automatically validated SOP. Production MD and trajectory analysis are not exposed as V4 user functionality.

## Validation

The final GitHub-ready source tree passed:

- **Release Gate: 25 / 25**
- **Release Verify Matrix: 16 / 16**
- **Focused GitHub-readiness regression: 32 / 32**
- **Source-integrity audit: 0 findings**
- **Python files compiled by Release Gate: 325 / 0 compile errors**
- **Representative modified-construct PDB round-trip: 20 / 20**
- **Explicit/buildable chemistry PDB round-trip: 47 / 47**

The R14 functional validation also covers affected PSB/notation, UI/output lineage, Docking, release-integrity, and compile checks.

## Public-data boundary

The public package excludes:

- private experimental history,
- private seed databases,
- user-local SQLite databases,
- runtime workspaces/logs,
- sessions and generated outputs,
- credentials/secrets,
- Python/pytest caches,
- build/dist binaries.

`apps/spps_planner_app/data/actual_runs.csv` is header-only, and the public experimental-seed directory contains documentation only.

## Quick start

```bat
git clone https://github.com/poowsh1407/Pepforge.git
cd Pepforge
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

See `README.md`, `MANUAL_EN.md`, or `MANUAL_KO.md` for the complete workflow and scientific limitations.

## Release assets

For the source release, publish the source archive together with its SHA-256 checksum. Native Windows installer/EXE assets should only be attached after a machine-local Windows build and smoke test.

## Citation

If Pepforge materially contributes to academic work, cite the exact release using `CITATION.cff`. If a DOI-backed release becomes available, prefer the DOI-linked citation.

---

**Pepforge V4.0.0** — peptide design, structure generation, synthesis planning, interaction review, and validation hand-off without hiding the boundary between computational evidence and experimental proof.
