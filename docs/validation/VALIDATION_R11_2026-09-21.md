# Pepforge V4.0.0 R11 Validation — 2026-09-21

## Scope

R11 continues from the Pepforge V4.0.0 R11 WIP continuation snapshot and selectively backports the validated SPPS Planner V6 FINAL recommendation/experimental-data core. The standalone V6 tree is not used as Pepforge ancestry.

## Chemistry guardrails retained

- AUTO cleavage fallback: 95% TFA + 5% Water.
- TIS automatic insertion: disabled.
- TIS/scavenger conditions: explicit/manual or historical evidence only.
- Existing Cys-equivalent hard rule remains owned by the embedded SPPS workflow.

## Completed checks

- Python compile of embedded SPPS: PASS.
- Experimental/recommendation focused regression: 31 passed / 1 skipped.
- Expanded SPPS/R8-R10/workflow regression: 84 passed / 1 skipped.
- Post-UI SPPS focused regression: 66 passed / 1 skipped.
- Release integrity + verify matrix + release gate: 6 passed / 0 failed.
- Larger whole-suite batches: no failure observed before the environment's 120-second command timeout; therefore not claimed as a completed full-suite pass.

## Packaging/privacy requirements

- Remove test/runtime caches and temporary logs.
- Do not bundle Private experimental SQLite/history/seed payload.
- Keep Pepforge suite version V4.0.0.
- Run ZIP CRC, fresh-unzip compile, focused SPPS regression, and release gate on the staged archive.

## Native Windows follow-up

The release should still be smoke-tested on the target Windows machine for Tk layout/DPI, browser-linked SDS actions, and operator-facing Data Store/Backup DB dialogs.
