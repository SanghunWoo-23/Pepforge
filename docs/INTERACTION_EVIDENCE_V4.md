# Pepforge V4.0.0 Interaction Evidence

## Scope

Pepforge V4 separates **coarse docking-oriented contact screening** from a new
**geometry-aware specific interaction evidence** layer. The new layer is a
coordinate review tool; it does not calculate binding free energy, affinity,
probability, or experimental confidence.

The legacy Docking Workbench contact tables remain available for backward
compatibility. Their historical cutoffs are not silently reinterpreted as the
new evidence profile.

## Profiles

### `CONSERVATIVE_MANUAL`

Designed for conservative PyMOL-style manual screening:

| Interaction | Main distance rule | Geometry / interpretation |
|---|---:|---|
| H-bond | donor-heavy-atom to acceptor-heavy-atom <= 3.5 Å | D-H...A >= 120° when explicit H is present; without H it remains a distance candidate |
| Hydrophobic | nonpolar atom to nonpolar atom 3.3-5.0 Å | atom-level contact, not residue-center distance |
| Salt bridge | opposite charged-group centers <= 4.0 Å | His is not automatically treated as protonated |
| pi-pi | ring centroid <= 5.0 Å | plane angle 0-30° or 60-90° and offset <= 2 Å |
| cation-pi | cation center to ring centroid <= 5.0 Å | ring-face placement; offset <= 2 Å |
| van der Waals | near sum of atomic vdW radii | general packing descriptor |
| clash | vdW surface overlap >= 0.4 Å | structure warning, not favorable interaction |

### `TOOL_COMPATIBLE`

A separate wider screening profile is retained for comparison with automated
tool conventions. Examples include H-bond D-A <= 4.1 Å, salt-bridge charge
centers <= 5.5 Å, pi-pi centroid <= 5.5 Å and cation-pi <= 6.0 Å. This profile
is **not** interchangeable with the conservative Methods profile.

## Representative interaction policy

For the same residue pair, Pepforge can minimize double counting:

1. clash is preserved independently as a structure warning;
2. salt bridge represents a same-pair H-bond candidate when both apply;
3. pi-pi/cation-pi represent a more specific aromatic interaction rather than
   also counting the same pair as a generic hydrophobic contact;
4. general vdW packing is lower priority than a specific interaction.

This is a reporting policy, not an energy decomposition.

## Evidence levels

- `geometry_supported`: required coordinate geometry is available and passes.
- `candidate`: distance screening passes but essential geometry is unavailable,
  e.g. an H-bond candidate in a hydrogen-free PDB.
- `not_confirmed`: distance is close but directional geometry fails.
- `packing_contact`: vdW packing descriptor.
- `structure_warning`: serious nonbonded overlap/clash.

## Docking Workbench export

V4 exports:

- `docking_atom_contact_report.csv` — existing coarse atom-proximity layer;
- `docking_specific_interaction_evidence.csv` — new geometry-aware evidence;
- `interaction_evidence_profiles.csv` — exact profile settings;
- `specific_interaction_evidence_summary.json` — counts/status with claim guard.

Actual docking execution remains outside the V4 scope. Coordinate-derived
interaction evidence is only meaningful when target/peptide coordinates are
actually present.

## References / policy basis

The conservative profile follows the Pepforge R&D protein/peptide interaction
screening guide and distinguishes its Methods cutoffs from wider automated-tool
settings. Tool-compatible references include PLIP configuration/documentation,
PIC/PICCOLO-style protein-interface criteria, and MolProbity/Probe clash
conventions. Report the profile and exact cutoff used in any Methods section.
