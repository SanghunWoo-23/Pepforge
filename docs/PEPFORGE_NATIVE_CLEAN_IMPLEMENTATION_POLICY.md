# Pepforge Native Clean Implementation Policy

## Purpose
Pepforge Native scientific engines are developed as independent implementations.
External projects may be studied for published algorithms, workflow concepts,
benchmark design and scientific context, but their source-code expression is not
the implementation basis for Pepforge Native modules.

## Allowed references
- Peer-reviewed papers and publicly described algorithms/mathematical methods.
- General workflow concepts such as sampling -> scoring -> refinement -> clustering.
- Public benchmark definitions and validation strategies, subject to their data licences.
- Scientific constants and generally used geometry definitions, with provenance notes.

## Prohibited implementation shortcuts
- Copy/paste of third-party scientific-engine source into Pepforge Native modules.
- Line-by-line translation or superficial renaming of third-party implementation code.
- Presenting third-party model weights, force-field parameters or databases as Pepforge-owned assets.
- Re-labelling a toy/random coordinate perturbation as molecular dynamics.
- Re-labelling a local pose search score as affinity, free energy or experimental Kd.

## Native dependency boundary
Pepforge Native may use general-purpose language/runtime and numerical/data libraries.
The scientific decision logic, search/scoring definitions, state/provenance and result
claims of Native modules must live in Pepforge source. External scientific engines
(HADDOCK3, OpenMM, structure predictors, PyMOL) are optional validation/reference or
visualization adapters, not required for the Pepforge Native docking path.

## Current native docking evidence specification
The native docking interaction classifier uses Pepforge's conservative interaction
evidence implementation: donor/acceptor H-bond screening, atom-level hydrophobic
contact, opposite-charge salt bridges, aromatic ring geometry, cation-pi geometry and
steric-overlap warnings. The score is an internal dimensionless search score and is
only comparable within a matching engine version/configuration.

## Validation rule
A Native module can be called implemented when its input -> validation -> algorithm ->
output -> failure path is real and tested. It cannot be described as scientifically
validated until documented benchmark comparisons appropriate to that engine have been
completed.
