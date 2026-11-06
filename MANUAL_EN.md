# Pepforge V6.0.0 User Manual

**Pepforge V6.0.0 · Public Research Source Release**

## 1. Start

```bash
python main_launcher.py
```

On Windows source distributions, `RUN_PEPFORGE_SOURCE.bat` is also available.

## 2. Main tools

### Hot Spot Finder
Prepares interface/hotspot evidence for peptide design.

### Peptide Design Engine (PDE)
Creates canonical/modified peptide candidates while preserving design intent and candidate lineage.

### Structure & Docking Studio
The primary V6 structure/docking workspace.

```text
Peptide sequence
→ conformer preparation
→ receptor preparation
→ Native Docking
→ interaction review
→ optional Native Mechanics / trajectory
→ Shared Native Result Viewer
```

#### Studio navigation (V6.0.0 tab layout)
- **1. Structure Builder:** peptide input, conditions, conformer generation and file review.
- **2. Docking & Simulation:** receptor/peptide inputs, docking configuration, mechanics and optional MD.
- **3. Results & Analysis:** token/chemistry table, ensemble evidence and shared native docking results.
- Click the notebook tabs (or press Ctrl+1 / Ctrl+2 / Ctrl+3) to switch **within the same Studio window**, without opening three separate windows. Token analysis and successful structure/docking results take you to the Results tab.
- Each tab has its **own** vertical scrollbar and retains its inputs when switching.
- Long sequence text and tables use their own horizontal scrollbars.
- Explanatory scientific/usage text lives in the README and this manual rather than occupying GUI space.

### SPPS Planner V8.0.0 — separate window

From the main launcher select **4 SPPS Planner**, then click **Open**. The original V8 Project/Batch/Materials/Checklist/Cleavage GUI opens in its **own normal window**, just like PDE or PSB. The main Pepforge window stays available. No Win32 window reparenting is performed. Save and close work using V8's normal project controls.

Source startup: `python -m pip install -r vendor/spps_planner_v8/requirements.txt`, then `python main_launcher.py --tool spps` or use the main launcher. Installed Windows builds must contain the `SPPS_Planner/SPPS_Planner.exe` companion in the Pepforge installation directory. Review `spps_v8_launch.log` if it closes immediately.

The Docking & Simulation tab groups Receptor file and sequence together and Peptide file and sequence together; the peptide sequence is synchronized with the Structure Builder tab. Pepforge retains V6.0.0; SPPS Planner retains V8.0.0.

**V8 UI update:** Recommendations/Lab History uses its own `SPPS.History.Treeview` style. Opening that window must not unbold the Project Manager Plan/Materials headers or change the Plan table row height. For reproduction, open Project Manager → Plan, record the heading appearance, open Recommendations & Lab History, then return to Plan. The fix changes styling only, not chemistry calculations.

## 3. Structure & Docking Studio inputs

### Peptide sequence
Use the large multi-line editor for canonical or supported modified notation.

### Receptor
Use PDB/mmCIF input or the supported sequence-derived preparation path.

### Binding mode
- blind
- hotspot
- manual residue guidance

### Native Docking
Pepforge-owned local pose search. The native score is not measured affinity.

## 4. Native follow-up

Usable poses can be followed by Native Mechanics and trajectory analysis.

Typical analyses include:
- aligned RMSD
- Rg
- RMSF
- drift
- clustering
- medoid frames

Native Mechanics is not production MD.

## 5. Public benchmark and external data

Pepforge includes registry, RCSB PDB synchronization, UniProt provenance, validation, and tuning infrastructure for public protein–peptide benchmarks.

Missing external benchmark execution is never presented as scientific validation PASS.

## 6. Interpretation boundaries

- docking score ≠ affinity
- docking score ≠ ΔG / Kd
- contact geometry ≠ biological activity
- RMSD stability ≠ functional validation
- predicted structure ≠ experimental structure
- Native Mechanics ≠ production MD

## 7. Project and result lineage

Pepforge preserves candidate → structure → docking → follow-up → review lineage. Share provenance, quality gates, and input context together with numerical outputs.

## 8. Troubleshooting

### Lower Studio controls are not visible
Use the ordinary mouse wheel or the right-hand scrollbar.

### Studio layout stretches horizontally
The current UI includes outer-page horizontal scroll sizing protections. Confirm you are using Pepforge V6.0.0.

### SPPS appears to be an older planner
Run Pepforge V6.0.0 from a fully extracted source folder. The V8.0.0 Public planner is launched as a separate process; use `python main_launcher.py --tool spps` to test the hand-off.

### Optional dependency is unavailable
The native core remains available where possible; optional backends are reported separately.

## 9. Documentation

- `README.md` / `README_KO.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `CONTRIBUTING.md`

Internal development handover documents are distributed separately from the public GitHub source package.


### Direct native docking: PDB/mmCIF and results (V6.0.0)

1. Open **Structure & Docking Studio → Docking & Simulation**.
2. In **Receptor**, choose `file` and Browse for `.pdb`, `.cif` or `.mmcif`; enter a sequence only for a separately configured prediction backend.
3. In **Peptide**, choose `file` and Browse for a valid 3D PDB/mmCIF/SDF/MOL. Peptide sequence can be entered for record-keeping and shares the Structure Builder value.
4. Choose **native**, a binding mode, and a preset; turn off optional OpenMM MD to verify native docking independently first.
5. Click **BUILD + DOCK + ANALYZE**. Docking tab progress counts the actual pose-search trials. After completion, open **Results & Analysis**. Pose rows, 3D review and report/export actions appear only for verified result files.
6. If no poses are verified, inspect the displayed error and the `Direct_Docking/<run-id>/results/v6_compute_pipeline.json` file. Source mmCIF may contain alternate conformations, nonstandard residues, multiple models or ligands that require structural review before search.

The native score is dimensionless and must not be interpreted as ΔG, Kd or measured affinity. Tests with a small synthetic input do not validate arbitrary biological structures or production MD.
