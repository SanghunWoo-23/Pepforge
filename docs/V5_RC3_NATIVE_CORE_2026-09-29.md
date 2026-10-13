# Pepforge V5 RC3 Native Core Development — 2026-09-29

## Direction
Pepforge core scientific workflows are being migrated from mandatory external scientific engines to Pepforge-owned implementations. External engines remain optional reference/validation adapters.

## Added in RC3
### Pepforge Native Docking v1
- No HADDOCK3/LightDock/network dependency.
- PDB receptor + PDB peptide input.
- Blind/manual/hotspot anchor generation.
- Deterministic rigid-body rotational sampling.
- Surface-shell peptide placement.
- Severe-overlap filtering and local translation refinement.
- Pepforge interaction-evidence scoring using conservative H-bond, hydrophobic, salt-bridge, aromatic/cation-pi and clash rules.
- Centroid-diverse representative pose selection.
- Ranked complex PDB, interaction CSV and JSON exports.
- Internal score explicitly labelled dimensionless and run/configuration-relative.

### Native Geometry Dynamics v1 foundation
- No OpenMM dependency.
- Bond-like geometry inferred from starting structure.
- Harmonic geometry preservation term.
- Steric-overlap force term and bounded weak-contact term.
- Iterative coordinate update, saved frames, trace CSV and restart JSON.
- Explicit evidence grade EXPERIMENTAL_GEOMETRY_DYNAMICS.
- Explicitly NOT production MD until validated units/force field/integrator benchmarks exist.

### Integration
- `pepforge_cli.py v5-native-dock`
- `pepforge_cli.py v5-native-relax`
- `v5-psb-simulate --docking-backend native|haddock3`
- PSB GUI docking backend selector; Native is the GUI default.
- `backend_status()` reports the native docking engine as local/network-independent.

## Clean implementation
See `docs/PEPFORGE_NATIVE_CLEAN_IMPLEMENTATION_POLICY.md`.
Third-party implementations may be studied at the algorithm/workflow level, but Pepforge Native code must not be copy/pasted or line-by-line translated from those projects.

## Validation in this build environment
- V5 regression selection: 43 passed / 0 failed.
- Release Gate: 25 passed / 0 failed.
- Python compile: 352 files / 0 errors.

## Scientific claim boundary
Native Docking v1 is an experimental rigid-body coordinate search. Its score is not affinity, free energy, Kd or native-pose proof. Native Geometry Dynamics v1 is a geometry relaxation/exploration foundation and is not production molecular dynamics.

## Next native milestones
1. Native topology representation independent of OpenMM/RDKit scientific engines.
2. Native bonded terms: bond, angle, dihedral, improper.
3. Native nonbonded terms with explicit units and parameter provenance.
4. Validated integrator and thermostat implementations.
5. Native peptide coordinate builder replacing RDKit-based conformer generation.
6. Benchmark suite against public experimental/benchmark structures without copying external engine implementation code.
