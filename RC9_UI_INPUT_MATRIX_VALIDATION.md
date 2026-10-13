# RC9 Docking Input Matrix / UI Accessibility Validation

## Input matrix smoke
Headless Tk/Xvfb smoke executed the Docking Workbench 3D screening path for all four combinations:

- PDB / PDB: COMPLETED
- PDB / Sequence: COMPLETED
- Sequence / PDB: COMPLETED
- Sequence / Sequence: COMPLETED

For the smoke, sequence-target structure preparation was forced to `Pepforge Native` so the test required no network and no external predictor.

## Sequence target policy
`Auto local` tries local/cached ESMFold with `local_files_only=True`. If that is unavailable, Pepforge Native sequence-derived coordinates are used with evidence grade `EXPERIMENTAL_SEQUENCE_DERIVED_GEOMETRY`. These coordinates enable the workflow but are not represented as an experimentally validated folded protein structure.

## UI accessibility smoke
- Input host viewport remained fixed at 235 px while Advanced Input expanded.
- Scroll region expanded independently (advanced controls remain reachable).
- Results notebook remained visible and usable.
- Each Notebook feature page has its own vertical scroll container.
- Main action controls and status/progress are separated into two rows to prevent horizontal clipping.

## Regression
- Docking/native selected tests: 19 passed / 0 failed
- Additional V5 native/core selected tests: 23 passed / 0 failed
- V4 release gate / verify / integrity selected tests: 6 passed / 0 failed
- Full package / regression audit selected tests: 4 passed / 0 failed

Claim boundary: UI/workflow completion does not establish docking accuracy or experimental structural validity.
