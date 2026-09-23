# Pepforge V4.0.0 — Current Final R6 Validation

## Scope
R6 closes the residual Docking residue-identity/numbering and Workflow lineage/state issues found after R5. Suite version remains V4.0.0. Production MD/trajectory analysis remains V5 scope.

## R6 regression contract
- D-AA residue identity is not canonicalized to L-AA during Docking PSB-metadata remapping.
- Non-natural residues such as Aib retain explicit non-standard identity.
- N-terminal modifiers/linkers such as Ac/Ahx do not consume peptide residue numbers.
- Sidecar-free residue-aware PSB PDBs preserve chain-P residue numbering in Docking.
- Combined-complex review PDB output does not fabricate GLY for modified/non-natural tokens.
- Workflow PDE input changes mark the active downstream lineage dirty.
- A monotonically increasing Workflow PDE revision prevents stale PSB/SPPS reuse even when a later PDE run resolves to the same sequence/candidate ID.
- Workflow progress is derived from active candidate/revision state and is not a scientific confidence/probability.
- Workflow PDE chemistry selectors use a centralized PDE catalog filtered to explicit PSB graph buildability.
- Optional ML trainer code is loaded lazily only when requested.

## Development-tree regression
The R6 development tree completed the full test collection with **410 passed, 1 skipped, 0 failed**.

## Release gate
Direct Release Gate result before final packaging: **25 passed / 0 failed**, **305 Python files compiled**, **0 compile errors**, **0 source-integrity findings**, **0 stale-name hits**, **0 packaging-artifact hits**.

## Exact fresh-unzip requirement
The final R6 ZIP must be unpacked into a new directory and rechecked for: clean package state before test execution, R6 focused regression, complete pytest collection, direct Release Gate, source-integrity audit, compile success, header-only public `actual_runs.csv`, and absence of packaged runtime caches. The companion external R6 validation report records the exact packaged-artifact result.

## Remaining native Windows acceptance boundary
Automated validation does not replace the final owner-side native Windows E2E pass for GUI/DPI/PyMOL rendering and the exact local `(3BW6) Synaptobrevin homolog YKT6.cif` path/input.
