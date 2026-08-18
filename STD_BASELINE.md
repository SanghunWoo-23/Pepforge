# Pepforge Current STD Baseline

## Canonical baseline

- Pepforge version: `3.0.0`
- Integrated SPPS module: `SPPS Planner V4.0.0`
- STD established: `2026-08-13`
- Integration input archive: `Pepforge_V3.0.0_SPPS_V4_Complete_Upgrade_2026-08-13.zip`
- Integration input SHA-256: `373ce153978e76f008421eec4fbdc1d3b9a5aeb32e9e98468fae0dae4978e068`
- Public source artifact: `Pepforge_V3.0.0_GitHub_Public_STD_2026-08-13.zip`

Future work must preserve the confirmed workflow and behavior of this baseline unless a change is explicitly approved and tested.

## Required preservation rules

- Preserve Hot Spot Finder, PDE, Top-5 Structure Builder, SPPS, Docking Workbench, and external-validation workflows.
- Preserve supported chemical, tag, linker, non-natural amino-acid, D-residue, and terminal-modification parsing.
- Preserve explicit Generate/Update and Apply Change behavior in SPPS.
- Preserve the `Ac-EEMQRR-NH2` 30 eq, TFA 95% / water 5%, no-TIS contract.
- Keep LOT Number and Batch Manager outside the Pepforge operator surface.
- Do not introduce runtime monkey patches, placeholder/stub/dummy/fake behavior, fabricated scientific parameters, hidden fallbacks, or silent feature loss.

## GitHub-public derivation

This repository is the maintained public derivative of the integration input. It adds complete user documentation, CI configuration, data-exclusion rules, and security guidance; excludes runtime/private data and inactive synthetic model artifacts; and includes the tested maintenance fixes listed in `RELEASE_NOTES_V3.0.0.md` and `CHANGELOG.md`. The suite version remains Pepforge V3.0.0 and the embedded synthesis component remains SPPS Planner V4.0.0.
