# Pepforge V4.0.0 — Current Final R7 Validation

## Scope
R7 is a Workflow hand-off/UI correction on top of the R6 lineage hardening. The suite version remains V4.0.0. No V5 production-MD/trajectory feature is moved into V4.

## R7 user contract
- Hot Spot ranked selection transfers its sequence directly to the Workflow PDE target field.
- PDE candidates are visible again under `Peptide Structure Builder` through a dedicated read-only `PSB input candidate` dropdown.
- Selecting a PSB input candidate mirrors the same active PDE candidate; no duplicate candidate lineage is created.
- Generated PSB outputs are selected from a separately labeled `Ranked structure` dropdown.
- Workflow SPPS exposes the public SPPS resin catalog and uses the requested field order: `Resin → Loading mmol/g → Scale mmol`.
- `Open SPPS Planner` launches the full standalone planner rather than silently generating a headless plan. The active candidate, resin, loading, scale, and Workflow project are passed to that child process and prefilled there.
- Normal standalone SPPS startup remains blank when no Workflow hand-off is present.
- The bottom `Evidence / Runtime Status` text area is removed as redundant. Progress/status labels, error dialogs, Python logging, and real evidence-export buttons remain.

## Preserved R6 contracts
- Docking D-AA/non-natural residue identity is not silently canonicalized to L-AA.
- Ac/Ahx and other non-residue tokens do not consume peptide residue positions.
- Sidecar-free residue-aware PSB PDB numbering is retained in Docking.
- Workflow PDE dirty/revision state prevents stale PSB/SPPS lineage reuse.
- Workflow PDE chemistry options remain centralized and PSB-buildability filtered.
- Optional PDE ML code remains lazy-loaded.

## Automated validation
Development-tree collection: **423 tests collected**. All collected tests were exercised in grouped runs; final expected result is **422 passed, 1 skipped, 0 failed**. The skip is the existing optional empirical-cleavage case; `test_spps_parser_contract.py` is an import-time contract script and therefore is not itself a collected pytest function.

The final external R7 validation report records the exact fresh-unzip results, release-gate counts, package cleanliness checks, and SHA-256 for the generated ZIP.

## Native Windows acceptance boundary
Automated validation cannot replace the owner-side native Windows E2E pass for GUI/DPI/PyMOL rendering and the exact local `(3BW6) Synaptobrevin homolog YKT6.cif` path/input.
