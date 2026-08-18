# Pepforge V3.0.0 — Public GitHub Release

Pepforge V3.0.0 is the current STD public source release. It integrates the SPPS Planner V4 evidence workflow while retaining the peptide-focused analysis, design, structure, synthesis-planning, screening, and validation-export pipeline.

The public package uses one explicit version contract: the integrated suite is **Pepforge V3.0.0**, while the embedded synthesis component is **SPPS Planner V4.0.0**. The complete English and Korean manuals are the canonical user instructions; obsolete backup, duplicated manual, legacy installer-note, and intermediate patch-note files are excluded from the release archive.

The launcher uses the V3 Modern/Classic hybrid workspace: a workflow sidebar, selected-tool explanation, output/workspace context, display-density controls, and one explicit launch action. All six active modules remain connected to the current repaired backends; Docking Workbench appears once.

## Highlights

- Restored direct pasted-sequence analysis in Hot Spot Finder.
- Retained explicit PDE settings Apply followed by candidate generation.
- Generates a sequence-aware, family-diverse Top-5 peptide conformer ensemble.
- Requires exactly five exported ranked structures for a successful PSB Top-5 build; adaptive retries and preset-specific evidence profiles replace the former partial-set behavior.
- Starts PDE without hidden target/motif examples, uses a new recorded exploratory seed by default, provides exact-repeat control, and applies an explicit final sequence-diversity filter.
- Parses supported terminal chemistry, tags, linkers, non-natural amino acids, and explicit D-residue notation.
- Integrates editable SPPS Plan, Materials, Total Materials, Checklist, cleavage output, literature guidance, and project/session export.
- Adds loading and cleavage time fields without changing stoichiometry.
- Uses sequence-first cleavage advice and one coherent reviewed historical condition; no cross-record cocktail mixing or model-invented optimum is applied.
- Preserves the confirmed `Ac-EEMQRR-NH2` 30 eq, TFA 95% / water 5%, no-TIS condition.
- Excludes LOT Number and Batch Manager from the Pepforge operator surface.
- Keeps one Docking Workbench launcher and explicit external-tool claim boundaries.
- Removes the unused synthetic pretrained-lite PDE artifact and its inactive loader; optional PDE priors require an explicitly selected user-reviewed CSV.

## Verification snapshot

- SPPS integration contracts: 6/6
- SPPS packaged self-test: 9/9
- Source-integrity findings: 0
- Runtime validation: 8/8
- Package audit: 20/20
- Regression audit: 9/9
- Release integrity: 16/16
- Verification matrix: 14/14
- Release gate: 23/23

Native Windows GUI behavior, actual RDKit 3D generation, PyMOL opening, installer execution, and third-party docking/MD programs still require target-machine validation.

## Public-data boundary

The GitHub package contains no real experimental history. Public schemas and seed directories are empty. Review `PUBLIC_DATA_POLICY.md` before publishing a fork or release asset.
