# Changelog

## V3.0.0 PSB/PDE behavior correction (2026-08-14)

- Changed PSB from an `up to five` behavior to an exact-five successful-build contract with adaptive embedding retries, independent ranked-PDB export, preset-specific evidence profiles, and visible family-priority/retry provenance.
- Connected Fast/Balanced/Thorough PSB presets to different real sampling counts, retry budgets, RMSD thresholds, and literature-evidence family priorities; the Input panel now uses one continuous light-blue surface instead of white gaps behind blue labels.
- Removed hidden PDE target and RGD/KLVFF defaults from desktop, config, and Colab paths. Exploratory runs now receive a new recorded seed, exact-repeat mode remains available, and final Top K selection enforces normalized sequence-distance diversity before transparent relaxation.

## V3.0.0 SPPS V4 evidence-workflow upgrade (2026-08-13)

- Restored the V3 Modern/Classic hybrid launcher as the public home screen while preserving the current six-module callbacks, isolated PSB worker, runtime workspaces, and SPPS V4 integration. Docking Workbench appears once as workflow step 5.
- Replaced the short user guides with complete English and Korean manuals covering installation, exact UI button order, sequence grammar, module workflows, output interpretation, scientific claim boundaries, and troubleshooting.
- Standardized public release wording to `Pepforge V3.0.0 with SPPS Planner V4.0.0`; historical component labels no longer appear as active SPPS version metadata.
- Reduced the GitHub source package by removing an obsolete Docking Workbench backup, duplicate plain-text manuals, a superseded V2 structure note, standalone PDE installer notes, accumulated patch notes, and synthetic example-result files.
- Synchronized the PSB runtime token registry, static manifests, and 13 missing explicit-graph SDF templates; buildable entries now have inspectable template files and ambiguous derivatives remain blocked by design.
- Added a safe temporary-directory fallback when the default SPPS application-data location is read-only; an explicitly configured user-data path still fails visibly if it cannot be created.
- Restored the explicit methionine cleavage route to `REAGENT_H`; Trp remains on the separate reducing EDT-containing route, and both remain operator-reviewed recommendations rather than automatic SOP claims.
- Changed Docking Workbench's temporary peptide coordinate bridge to one lightly optimized, explicit-chemistry conformer; the visible family-diverse Top 5 remains the separate PSB workflow and is no longer regenerated for every geometry preview.
- Integrated the sanitized SPPS Planner V4 calculation and experimental-evidence workflow while keeping Pepforge itself at V3.0.0.
- Added loading and cleavage time as first-class planning fields; time annotations do not silently alter stoichiometric amounts.
- Added conservative loading, coupling, and sequence-first cleavage advice from reviewed experimental records. Apply reproduces one coherent historical condition only; it never applies a model-invented optimum or mixes cocktail components across records.
- Added explicit `parsed`, `verified`, `incomplete`, and `excluded` record states plus direct loading/coupling/cleavage record entry. Public seed data remain empty and sanitized.
- Preserved editable Plan, Materials, Total Materials, Checklist, project/session, custom-material, export, literature-guidance, resin-dependent planning, and the confirmed `Ac-EEMQRR-NH2` 30 eq / 95% TFA / 5% water / no-TIS contract.
- Excluded operator-facing LOT Number and Batch Manager workflows from Pepforge and replaced the packaged runtime proof with a single-plan chemistry and cleavage self-test.
- Retained static controller composition with no runtime class reassignment or nested build-wrapper patch stack.

## V3.0.0 PSB reliability and SPPS V3 integration (2026-08-13)

- Made terminal chemical shorthand case-tolerant: `Ac-/AC-` resolve to acetyl and `Pal-/PAL-` resolve to palmitoyl; explicitly separated residues remain available as `A-C-` and `P-A-L-`.
- Expanded PSB parsing for curated non-natural amino acids, PEG/linker shorthand, tags, labels, and chemical modifiers. Recognized chemistry without a curated bound graph is rejected explicitly instead of receiving a surrogate structure.
- Added physiological, room-temperature, membrane-mimetic, and custom condition presets, with an explicit boundary that conditions are interpretation/export metadata rather than constant-pH or solvent simulation.
- Moved PSB geometry generation to an isolated worker process and added fast, balanced, and thorough Top-5 presets with bounded CPU use. Worker failure can no longer close the PSB window.
- Integrated the supplied SPPS Planner V3 controller through a normal static subclass, removed LOT and Batch Manager from the active and alternate UIs, and preserved the confirmed `Ac-EEMQRR-NH2` cleavage contract.
- Removed the duplicate Docking Workbench launcher entry and aligned active release, installer, audit, citation, and manual metadata to V3.0.0.
- Static SPPS monkey-patch audit reports zero runtime class bindings and zero build wrappers.

## V2.0.0 UI and workflow preservation repair (2026-08-13)

- Replaced the launcher card wall with a compact 3×2 workflow layout and applied one shared light visual system across the first-party GUIs.
- Restored direct Hot Spot Finder analysis for visually wrapped, multi-line pasted sequences and clarified the sequence-first workflow.
- Removed the overlapping PDE preset/length controls; preset selection now updates the visible fields immediately, while `Apply Settings` explicitly validates and freezes the configuration before `Generate Candidates` is enabled.
- Standardized operator-facing structure input terminology on `Peptide sequence` and clarified major PDE field labels.
- Restored SPPS Selected Plan, Selected Materials, Total Materials, and Synthesis Checklist as one Generate/Update workflow while keeping literature guidance and clean static release routes.
- Corrected the active Ac-EEMQRR-NH2 AUTO cleavage path to the confirmed 30 eq, 95% TFA / 5% DW, no-TIS contract.

## V2.0.0 GitHub documentation refresh (2026-08-12)

- Rebuilt the English and Korean README files around the actual public workflow, entry points, dependency profiles, scientific claim boundaries, and target-machine validation requirements.
- Added GitHub-rendered English and Korean user manuals with end-to-end module guidance, Top 5 structure interpretation, α/β/γ and BH3 special-case boundaries, troubleshooting, and developer verification commands.
- Corrected direct-launch examples to match the active launcher contract and separated automated Linux/package QA from pending native Windows, RDKit, PyMOL, and third-party-tool checks.
- Verified all local Markdown links, launcher help, CLI version, Python compilation, and the 23/23 release gate.

## V2.0.0 Stage 7 full source consolidation (2026-08-12)

- Replaced the 43k-line SPPS legacy controller and ordered runtime installer stack with one concrete `modern_tk_gui.SPPSGui` release class.
- Implemented Duplicate, Delete, Generate/Update, Apply, Export, autosave and project-save routes as real class methods and connected previously unbound buttons.
- Removed versioned compatibility routers and class/function reassignment modules from the shipped package; PyInstaller now includes the concrete modern GUI.
- Consolidated 18 duplicate top-level definitions across SPPS/PDE sources into unique static definitions without last-definition-wins behavior.
- Added a permanent source-integrity audit to the release gate for duplicate definitions, runtime class rewriting, override suppression and incomplete implementation markers.
- Source-integrity audit: 0 findings; targeted Structure/SPPS/PDE contracts: 30/30; package/runtime/regression/verification gates all passed.

## V2.0.0 Stage 6 complete literature-guidance integration (2026-08-12)

- Added a first-party, evidence-linked SPPS guidance engine covering coupling-system review, protecting groups, resin/linker choice, mild versus global cleavage, sensitive-residue cleavage, difficult sequences, aspartimide, pseudoproline, disulfide/cyclization, workup/counterion, analytical structure validation and sustainability.
- Guidance is generated from the same parsed peptide and resin used by the active material/operation plan; it is included in validation, GUI exports, CSV and an Excel `11_LITERATURE_GUIDANCE` sheet.
- Explicit protecting groups such as Acm/Pbf are preserved for orthogonality review; noncanonical and alpha/beta/gamma units cannot inherit canonical-alpha parameters.
- Met-only AUTO cleavage now selects literature-linked Reagent H; the confirmed `Ac-EEMQRR-NH2` 30 eq, 95% TFA/5% DW, no-TIS rule remains higher priority.
- Added Cys(S-tBu) `+56.0626 Da` impurity guidance, acetate/TFA counterion verification, and beta-edge/Trp-zipper sequence descriptors.
- Added seven Stage 6 executable contract tests and retained all nine Stage 5/Top-5 contracts.

## V2.0.0 Stage 5 literature sequence/foldamer integration (2026-08-12)

- Added transparent hydrophobic-moment, coiled-coil heptad, beta-alternation, turn/hairpin, aggregation, difficult-SPPS, chemical-liability, cysteine-topology and helix-dipole sequence screens.
- Added explicit alpha/beta/gamma backbone-pattern recognition, including the `αγααβα` 4:1:1 hexad discussed by Shin and Gellman (2018) and the BH3 design context studied by Shin and Yang (2022).
- Canonical alpha-peptide propensity values and alpha-backbone seed torsions are not transferred to beta/gamma residues; BH3 mimicry and binding are never inferred from the backbone pattern alone.
- Every Top 5 structure now carries an ordinal candidate role plus a guard against interpreting it as a physiological population, kinetic state, or target-bound assignment.
- Added nine executable sequence/Top-5 contract tests; all pass under the dependency-light manual runner.

## V2.0.0 Stage 4 scientific/Windows/UI hardening (2026-08-12)

- Top-five conformer selection now applies a 1.0 Å symmetry-aware heavy-atom RMSD diversity screen before filling ranked outputs.
- Structure Builder accepts optional pH, temperature, ionic-strength and environment records with strict numeric validation and an explicit statement that RDKit is not constant-pH or explicit-solvent MD.
- Added explicit derivative-information contracts for generic TAMRA, Cy5, NBD, DOTA, Chol, Mal and Dde tokens; no surrogate structure was introduced.
- Added a Windows release preflight that checks RDKit, PyMOL, installer resources, reference structure generation, Top 5 ranks and condition metadata.
- Introduced a shared first-party Tk theme across launcher, Hot Spot, Docking, Structure Builder and the Pepforge SPPS integration surface.
- Preserved the active SPPS behavior baseline; Ac-EEMQRR-NH2 remains 30 eq, 95% TFA / 5% DW, no TIS.

## V2.0.0 sequence-aware structure top-five checkpoint (2026-08-12)

- Structure Builder now samples a broader 32-conformer search and exports a ranked, family-diverse top five.
- Final selection now uses transparent sequence evidence for helix, beta/hairpin, turn, PPII and coil retention before within-molecule energy tie-breaking.
- Rank 1 is the primary PDB/SDF; ranked PDBs, top-five SDF/CSV and a PyMOL comparison session are exported.
- Modified, D-form and linker-containing peptides remain geometry-only where literature parameters are unavailable; no canonical surrogate or physiological-structure claim is introduced.

All notable public changes to Pepforge are documented here.

The project uses semantic-style release labels where practical, but scientific behavior should be judged from the actual release notes and code rather than a version number alone.

## [2.0.0] - 2026-08-11

### Integrated hardening checkpoint - 2026-08-12

- Closed the curated Structure Builder chemistry/template audit.
- Completed PDE preset, motif, terminal, ML-evidence, and export hardening.
- Disabled bundled/untrained ML-like reranking; user-data models now require at
  least 10 labeled rows and preserve higher/lower-is-better direction.
- Blocked modified-peptide canonical surrogate export.
- Fixed the confirmed `Ac-EEMQRR-NH2` AUTO cleavage contract to 30 eq,
  95% TFA / 5% DW, with no TIS.
- Added Hot Spot Finder progress state and thread-safe setting snapshots.
- Aligned package/release audits with V2.0.0 and made a failing release gate
  return a non-zero CLI exit code.
- Preserved the established Docking, Structure, SPPS, launcher, and export
  workflows while keeping scientific claims within preparation/screening scope.

### Fixed baseline
This release is the current development standard for Pepforge V2.0.0.

### Added / Improved
- Reorganized Windows-first launcher and lightweight per-tool workspace architecture.
- Hot Spot Finder alignment, blank-start input behavior, validation/progress fixes.
- Peptide Design Engine C-terminal NH2 GUI option wired to `USE_CTERM_NH2`.
- Direct integration of the proven SPPS Planner V2 workflow into Pepforge.
- Pepforge SPPS integration excludes LOT Number and Batch Manager by design.
- Docking Workbench `Run Screening` flow repaired with visible validation, stage-aware progress, diagnostics, and result population.
- Peptide Structure Builder expanded from a single representative conformer workflow to an interpreted conformer ensemble.
- Structural-family handling for α, 3₁₀, β-extended, β-hairpin-like, PPII, turn-rich, and coil/mixed candidates.
- Canonical-L α / 3₁₀ / β-extended / PPII search seeds to reduce missed conformational basins in short ETKDG sampling.
- Ensemble SDF, conformer-family CSV, and backbone φ/ψ CSV outputs.
- Explicit unsupported-evidence handling for D/non-natural/modified residues instead of fabricated numerical propensities.
- External-tool guidance / hand-off architecture retained without pretending to replace Vina or GROMACS.

### QA highlights
- `python -m compileall -q .` passed on the fixed source baseline.
- Targeted Structure Builder / Docking Workbench tests passed.
- Docking Workbench GUI sequence/sequence screening smoke reached 100% and populated representative pose/contact results.
- Structure ensemble export validated on canonical and modified-peptide examples.

### Documentation
- Rebuilt README EN/KO around the actual v2.0.0 baseline.
- Removed stale 4.x/8.8 public-release wording from top-level release metadata.
- Added scientific-scope, development-policy, roadmap, contributing, and release-note documents.
