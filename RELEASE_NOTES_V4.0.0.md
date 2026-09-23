# Pepforge V4.0.0 — Release Notes

**Release date:** 2026-09-22  
**Public package revision:** R14  
**Embedded SPPS component:** SPPS Planner V5.0.0 Public/Data-Sanitized

## Release summary

Pepforge V4.0.0 is the public source release of the integrated peptide research workflow spanning Hot Spot Finder, Peptide Design Engine, Peptide Structure Builder, SPPS planning, Docking Workbench interaction review, and external validation preparation.

The V4 line emphasizes traceability and conservative scientific interpretation: supported chemistry is preserved explicitly, missing evidence stays missing, unsupported structures are not fabricated, and internal screening output is not promoted into experimental claims.

## R14 interoperability update

R14 improves PSB-generated PDB files so they can carry peptide identity forward into Docking Workbench.

- `SEQRES` describes peptide residue positions.
- `REMARK 901 PEPFORGE_EXACT_SEQUENCE` preserves exact Pepforge modified notation.
- Modifier/linker metadata is retained separately from peptide residue numbering.
- Existing residue-aware `ATOM` / `HETATM` coordinate export is preserved.
- Long exact-sequence metadata supports continuation lines.
- Docking Workbench restores peptide identity from Pepforge metadata first, then `SEQRES`, then coordinate residue records.
- Chemistry without a unique curated coordinate graph remains explicitly unsupported for fabricated all-atom coordinate generation.

## Preserved V4 improvements

### Peptide Design Engine

- Real Pareto NSGA-II selection using non-dominated sorting, crowding distance, and Pareto environmental selection.
- Five scientific-design objective modes: Interaction Only, Interaction First, Balanced, Structure Guided, and Structure Exploration.
- Chemistry-aware final diversity and stable candidate IDs.
- Explicit conformational-strategy and environment/context handling.
- Position-resolved synthesis/chemical-risk evidence kept separate from interaction objectives.

### Peptide Structure Builder

- Sequence-aware exploration of supported conformational families.
- Up to five ranked, severe-clash-free coordinate candidates where sufficient valid structures are generated.
- Explicit separation between requested structure intent, measured relaxed geometry, and audit metadata.
- Modified chemistry is not silently canonicalized.
- Static PDB/SDF structure analysis and compatible structure comparison remain available; production trajectory analysis is not a V4 user function.

### SPPS Planner integration

- Embedded Public/Data-Sanitized SPPS Planner V5 evidence workflow.
- Editable Plan, Materials, Total Materials, Checklist, cleavage review, and project/session workflow.
- Reviewed historical evidence remains provenance-aware and does not silently merge unrelated conditions.
- R12 visible-sequence source-of-truth fix is preserved.
- R13 blank-startup/idle-refresh guard is preserved.
- LOT Number and Batch Manager remain outside the Pepforge operator-facing surface.

### Docking / interaction review

- Readable residue-centered contact output.
- Separate conservative specific-interaction evidence rather than collapsing all contacts into one score.
- Geometry-aware interaction review remains screening evidence, not experimental affinity.
- Candidate/structure lineage and PyMOL review preparation are preserved.

## Public release boundary

The public source package excludes private experimental history, local databases, runtime logs/workspaces, credentials, generated outputs, caches, build products, and private seed payloads.

## Validation snapshot

- Release Gate: **25 / 25 passed**
- Release Verify Matrix: **16 / 16 passed**
- Focused GitHub-readiness regression: **32 / 32 passed**
- Source-integrity audit: **0 findings**
- Release Gate Python compile: **325 files / 0 errors**
- R14 representative PDB round-trip: **20 / 20 passed**
- Explicit/buildable chemistry round-trip: **47 / 47 passed**

Detailed records are in `docs/validation/`.

## Scientific boundary

Pepforge is a research-support and screening workbench. Its output does not by itself establish experimental binding affinity, native structure, biological efficacy, synthesis yield/purity, or laboratory safety. Production MD/trajectory analysis is reserved for future V5 scope.
