# Pepforge V4.0.0 — Current Final R8 Validation

## Scope
R8 integrates the final user feedback collected after R7. The suite version remains V4.0.0 and the existing Public/Private and V4/V5 scope boundaries are unchanged.

## SPPS corrections
- Saved peptide Sequence is persisted/restored on reopen; a truly new planner remains blank.
- Window close and File → Exit save the active autosave/session before destruction.
- Resin selection reuses original loading defaults from `apps/spps_planner_app/data/settings_db.csv` where an original value exists.
- Loading checkbox defaults ON for new/legacy items and Workflow hand-off. The engine applies an actual direct-loading reaction only when the selected resin profile is direct-loading and the checkbox remains enabled.

Original loading values currently available from the accepted settings database:
- Rink Amide AM resin: 0.4 mmol/g
- Rink Amide MBHA resin: 0.35 mmol/g
- Sieber Amide resin: 0.5 mmol/g
- 2-CTC: 0.8 mmol/g
- Trityl chloride resin: 0.8 mmol/g
- Wang resin: 0.7 mmol/g

Expanded resin choices without an original database value keep the current/user-entered loading instead of receiving an invented default.

## Workflow PDE length
Workflow exposes the native PDE length contract:
- `RANDOM`: Min / Max
- `FIX`: Fixed Length
- token-count semantics
- trim-to-length enabled

Length settings are persisted in Workflow PDE settings and changing them invalidates stale downstream candidates/structures just like chemistry/structure/quality changes.

## Docking interaction evidence
The conservative specific-interaction layer follows the owner-supplied manual criteria: H-bond <=3.5 A, hydrophobic 3.3–5.0 A, salt bridge <=4.0 A, pi-pi/cation-pi <=5.0 A with geometry, vdW-overlap clash >=0.4 A, disulfide ~2.0–2.1 A, water bridge 2.5–3.5 A each, metal <=3.0 A, halogen <=3.5 A plus direction, aromatic-S <=5.0 A, weak C-H...O/N <=3.5 A, and NH-pi <=3.9 A secondary screening.

A visible `Specific interactions — conservative PyMOL criteria` table is provided in Docking → Contacts. Distance-only cases that require missing hydrogens, metal-specific geometry, covalent connectivity, or manual ring-direction review are not silently promoted to fully confirmed interactions.

## Automated validation
- R8 focused + related Workflow/SPPS/Docking regression: 56 passed in the focused integration group, plus 23 passed in the first focused contract run.
- Core/SPPS/source-integrity batch: 106 passed / 1 skipped.
- Direct Release Gate: 25 passed / 0 failed; 307 Python files compiled; 0 compile errors; 0 stale hits; 0 packaging-artifact hits.

The final artifact is additionally checked after clean staging/fresh unzip before SHA-256 is frozen.

## Native Windows acceptance boundary
Automated tests cannot substitute for the final owner-side visual E2E check of native Windows Tk/DPI/PyMOL rendering and local external file paths.
