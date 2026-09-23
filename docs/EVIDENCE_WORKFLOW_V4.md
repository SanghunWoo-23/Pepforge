# Pepforge V4.0.0 Evidence Workflow

## Hot Spot -> PDE

Workflow Mode now exports both:

- `selected_hotspots_for_design.csv`
- `hotspot_chemistry_profile_for_PDE.json/csv`

The chemistry profile is a weighted sequence-composition hand-off. When Design
is launched from the active project, the PDE can read this profile and use it
under `OFF / REPORT_ONLY / EVIDENCE_AND_SELECTION`.

It does **not** represent a 3D contact map or affinity. Actual atom-level
interaction evidence requires coordinates and is handled separately.

## PDE -> PSB -> future docking lineage

Stable candidate IDs are retained. PSB outputs can be assigned lineage IDs:

```text
PF-CAND-.../PSB-R01
PF-CAND-.../PSB-R01/DOCK-P01
```

V4 only prepares the lineage and PyMOL review script. A `DOCK-Pxx` pose is a
real docking result only if an actual docking backend output is executed or
imported and recorded. Actual V5 docking is intentionally not fabricated in V4.

## Candidate comparison

`candidate_evidence_matrix.csv/json` compares candidates on separate evidence
axes. It intentionally does not collapse PDE, PSB, SPPS, docking, trajectory,
and experimental evidence into one affinity-like score.

## Structure consensus v2

In addition to exact-sequence-safe CA/backbone RMSD and DSSP, the comparison can
now report:

- per-residue CA/local-backbone displacement;
- nonlocal CA contact-map Jaccard agreement;
- lost/gained contacts;
- hotspot-residue CA RMSD for user-specified 1-based residue indices.

Model agreement is an independent consensus diagnostic, not proof of native
structure.

## Simulation / MD preparation

V4 plans start-state sensitivity, independent replicates, force-field
sensitivity and parameterization requirements. It checks backend availability
but does not claim that MD ran merely because OpenMM or MDTraj is installed.
Only actual imported trajectories may yield MD-derived measurements.
