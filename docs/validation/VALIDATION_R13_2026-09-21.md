# Pepforge V4.0.0 R13 Validation — 2026-09-21

## Fixed defect

SPPS Planner retained a legacy automatic refresh path: when the editable Plan tree was empty, `refresh_outputs_from_tree()` called `rebuild_table()` unconditionally. On a fresh/blank Project Manager editor that implicit rebuild reached the parser with an empty sequence and could show `Parse error: Core sequence is empty` merely from startup/idle/tab refresh timing.

## R13 behavior

- Automatic startup/idle/tab refresh treats a blank visible Project Manager Sequence as a valid idle state.
- No implicit `rebuild_table()` or parser call occurs while the visible sequence is blank.
- If `pm_sequence` exists, it is authoritative even when blank; stale legacy `seq` is not resurrected.
- Legacy-only callers without `pm_sequence` may still use `seq`.
- Explicit Generate/Apply retain their normal empty-input validation.

## Regression targets

- blank visible sequence + stale legacy `seq=OLD` -> no implicit rebuild
- fresh real-Tk startup -> no messagebox error
- explicit background refresh on fresh blank planner -> no messagebox error
- visible `GHK` + blank legacy `seq` -> Generate succeeds and legacy mirror repairs to `GHK`

## Version/privacy guardrails

- Pepforge suite version remains V4.0.0.
- Embedded SPPS component remains V5.0.0 Public/Data-Sanitized.
- No Private experimental seed/history/database is added.

## Validation results

- New + R12 + launch/blank-startup unit regressions: **17 passed / 0 failed**.
- Focused SPPS + R8/R9/R10 + project-session regression: **85 passed / 1 intentional skip / 0 failed**.
- Release integrity + verify matrix + release gate + source-integrity: **9 passed / 0 failed** after release-tree cleanup.
- Real Tk/Xvfb fresh startup: **PASS**, zero error dialogs.
- Real Tk/Xvfb explicit blank background refresh: **PASS**, zero error dialogs.
- Real Tk/Xvfb tab-change refresh exercise: **PASS**, zero error dialogs.
- Real Tk/Xvfb R12 source-of-truth case (`GHK`, legacy `seq=''`): **PASS**, 3 plan rows generated and legacy mirror repaired to `GHK`.

Native Windows fresh-unzip smoke testing remains recommended because the original popup was operator-visible on Windows and Tk scheduling can be machine-specific.
