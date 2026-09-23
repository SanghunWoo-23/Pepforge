# Pepforge V4.0.0 R12 Validation — 2026-09-21

## Fixed defect

Repeated SPPS Project Manager failure: the visible Sequence editor could contain a valid peptide such as `GHK` while the legacy internal `seq` mirror remained blank, allowing a classic calculation route to raise `Parse error: Core sequence is empty`.

## Source-of-truth contract

- If the Project Manager Sequence editor (`pm_sequence`) exists, its current visible value is authoritative for Generate/Apply.
- A non-empty visible value is mirrored into legacy `seq` before calculation so compatibility paths cannot see a stale blank value.
- An intentionally blank visible Sequence remains blank; stale saved/legacy sequence values are not resurrected.
- Legacy `seq` remains a fallback only for callers that do not expose a Project Manager Sequence editor.

## Exact reproduction check

Real Tk/Xvfb was run with:

- Sequence: `GHK`
- Scale: `1000`
- Resin: `2-CTC`
- Resin loading: `0.8 mmol/g`
- Chemistry: `DIC/HOBt`
- Legacy `seq`: deliberately forced to blank immediately before Generate

Results:

- Canonical Project Manager Generate button: PASS; 3 plan rows generated; no messagebox error.
- Historical `ClassicControllerBase.generate_update_plan` route: PASS; no `Core sequence is empty`; legacy `seq` repaired to `GHK`.

## Automated regression

- New source-of-truth unit regression: 4 passed.
- SPPS + R8/R9/R10 + project-session focused regression: 82 passed / 1 intentional skip / 0 failed.
- Release integrity + verify matrix + release gate + source-integrity: 9 passed / 0 failed.
- Python compile for embedded SPPS/package source: PASS.

## Existing chemistry/privacy guardrails retained

- Pepforge suite version remains V4.0.0.
- Embedded SPPS component remains V5.0.0 Public/Data-Sanitized.
- AUTO cleavage remains 95% TFA + 5% Water.
- TIS is not inserted automatically.
- No Private experimental seed/history/database is intentionally bundled.

## Native Windows follow-up

The exact operator-reported case should still be smoke-tested on the target Windows machine after replacing the old package, because native Tk/DPI and local launch-path behavior are machine-specific. The R12 archive is intentionally named separately so an older R10/R11 folder cannot be mistaken for the hotfix.
