# Pepforge V4.0.0 R14 — Final GitHub Public Source Validation

**Date:** 2026-09-22  
**Suite version:** V4.0.0  
**Public package revision:** R14  
**Embedded SPPS component:** V5.0.0 Public/Data-Sanitized

## Final public-release cleanup

The GitHub-ready source tree was cleaned and synchronized before final packaging.

- Rewrote `README.md` and `README_KO.md` as product-first public documentation instead of development-log-first pages.
- Rewrote `GITHUB_RELEASE_BODY.md` and `RELEASE_NOTES_V4.0.0.md` for the final public source release.
- Consolidated `.gitignore` and explicitly preserved `installer/Pepforge.spec` as a tracked release/build file.
- Synchronized repository URLs to `https://github.com/poowsh1407/Pepforge`.
- Updated `CITATION.cff` release date to `2026-09-22` and synchronized the citation policy to V4.0.0.
- Finalized `PACKAGE_INDEX.json` as the R14 public source release metadata.
- Moved R11–R14 validation records under `docs/validation/`.
- Moved the V3 historical release note under `docs/release_history/`.
- Moved GitHub upload and development-only notes under structured `docs/` subfolders.
- Added `docs/README.md` as a documentation index.
- Verified internal Markdown links after the reorganization.
- Simulated `git add` in a temporary repository and confirmed `installer/Pepforge.spec` is tracked while runtime/private artifacts remain excluded.

## Functional and release validation

Documentation/packaging changes were followed by source regression and release checks.

### Focused regression after cleanup

- Documentation/package-index/release-contract group: **22 passed / 0 failed**
- R14 / Docking / explicit-chemistry focused group: **27 passed / 0 failed**
- Python `compileall`: **PASS**

### Official release tooling

- Release Gate: **25 passed / 0 failed**
  - Python files compiled: **325**
  - Compile errors: **0**
  - Source-integrity findings: **0**
  - Stale legacy-name findings: **0**
  - Packaging-artifact findings: **0**
- Release Verify Matrix: **16 passed / 0 failed**
- Release Integrity: **18 passed / 0 failed**
- Full Package Audit: **20 passed / 0 failed**
- Final packaged ZIP fresh-unzip Release Gate: **25 passed / 0 failed**

### R14 coordinate/identity validation retained

- Representative modified-construct PDB round-trip: **20 / 20 passed**
- Explicit/buildable chemistry PDB round-trip: **47 / 47 passed**
- PSB PDB preserves peptide `SEQRES`, exact Pepforge modified-construct metadata, and residue-aware coordinates where supported.
- Docking Workbench recovery order remains Pepforge exact-sequence metadata → `SEQRES` → ATOM/HETATM residue extraction.

## Public-data boundary

The final public source tree excludes runtime workspaces/logs, private experimental history, user-local databases, credentials, generated outputs, build/dist products, and Python/pytest caches.

`apps/spps_planner_app/data/actual_runs.csv` remains header-only and `apps/spps_planner_app/data/experimental_seed/` contains documentation only.

## Binary boundary

This validation approves the **public source release**. Native Windows installer/EXE artifacts must still be built and smoke-tested on the target Windows machine before being attached as binary assets to a GitHub Release.

## Scientific boundary

These checks validate software and package readiness. They do not validate biological activity, experimental binding affinity, native structure, synthesis yield/purity, or laboratory safety.
