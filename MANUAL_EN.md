# Pepforge V5.0.0 FINAL User Manual

**Pepforge V5.0.0 · Public Research Source Release**

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
The primary V5 structure/docking workspace.

```text
Peptide sequence
→ conformer preparation
→ receptor preparation
→ Native Docking
→ interaction review
→ optional Native Mechanics / trajectory
→ Shared Native Result Viewer
```

#### Scrolling
- Ordinary mouse wheel: move the complete Studio page vertically
- PageUp / PageDown: page navigation
- Home / End: top / bottom
- No middle-button panning is required
- Long peptide text uses its own horizontal scrollbar
- Wide tables use their own scrollbars

### SPPS Planner
Pepforge launches the supplied **SPPS Planner V7.0.0 FINAL** runtime as the primary synthesis planner.

Primary workspaces include:
- Project Manager
- Batch Manager
- Add/Edit peptide
- synthesis plan / material / checklist workflows

Source distributions launch it as a separate process.

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

V5 includes registry, RCSB PDB synchronization, UniProt provenance, validation, and tuning infrastructure for public protein–peptide benchmarks.

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
V5.0.0 prevents outer-page horizontal geometry feedback. Confirm you are using the latest V5.0.0 package.

### SPPS appears to be an older planner
Launch through the latest V5.0.0 Pepforge launcher. The expected source-runtime title is `SPPS Planner V7.0.0 Final`.

### Optional dependency is unavailable
The native core remains available where possible; optional backends are reported separately.

## 9. Documentation

- `README.md` / `README_KO.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `CONTRIBUTING.md`

Detailed engineering handover and V6/V7 roadmaps are kept in the separate Internal/Handover package.
