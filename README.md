# Pepforge V5.0.0 FINAL

**UI Polish R4 · 2026-10-12**

Pepforge is a local peptide R&D desktop toolkit connecting peptide design, structure preparation, native docking, interaction review, mechanics/trajectory follow-up, and SPPS planning in one workflow.

## V5 FINAL R4 highlights

### Structure & Docking Studio

PSB and Native Docking are presented as one continuous Studio workflow.

`Peptide input → conformer preparation → receptor preparation → Native Docking → interaction/mechanics/trajectory review`

- Large multi-line peptide sequence editor
- Conventional **mouse-wheel page scrolling**
- `PageUp / PageDown / Home / End` navigation
- Edge clamping so redundant wheel events do not accumulate at page limits
- Coalesced high-resolution wheel events
- Debounced scrollregion updates
- Viewport-locked outer page width to prevent geometry stretching while dragging the scrollbar thumb
- Independent horizontal scrolling for long sequences and result tables

### Workflow Mode

Workflow Mode now uses the same stable vertical scrolling contract, preserving project/candidate lineage and existing workflow hand-offs.

### SPPS Planner integration

Pepforge references the supplied **SPPS Planner V7.0.0 FINAL R2** UI/launch patterns and retains only the integration needed by Pepforge. Pepforge and SPPS Planner remain distinct projects.

## Run

```bash
python main_launcher.py
```

## Main workflow

1. Hotspot Finder
2. Peptide Design Engine
3. Structure & Docking Studio
4. SPPS Planner
5. External Validation

## Scientific claim boundary

Pepforge Native Docking scores are internal pose-search scores.

- docking score ≠ measured affinity
- docking score ≠ ΔG / Kd
- contact geometry ≠ biological activity
- RMSD stability ≠ functional validation
- Native Mechanics ≠ production MD

## Documentation

- `MANUAL_EN.md`
- `MANUAL_KO.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`

Detailed handover material and the V6/V7 roadmap are distributed separately from the public repository.
