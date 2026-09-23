# Pepforge V4.0.0 — Public Source Release (R14) — 2026-09-22

- Finalized the GitHub-ready public/data-sanitized source package.
- Added PSB PDB `SEQRES` and exact modified-construct metadata with Docking recovery fallback.
- Preserved R12/R13 SPPS sequence source-of-truth and blank-startup protections.
- Cleaned public packaging, release metadata, citation metadata, `.gitignore`, and root documentation layout.
- Release Gate 25/25, Verify Matrix 16/16, focused GitHub-readiness regression 32/32, source-integrity findings 0.

---

## 2026-09-21 — Pepforge V4.0.0 R14

- Added peptide `SEQRES` records to PSB residue-aware PDB exports.
- Added exact Pepforge construct metadata with continuation support for long modified sequences.
- Preserved modifier/linker metadata without consuming peptide residue numbering.
- Docking Workbench now recovers peptide identity from Pepforge exact-sequence metadata, then `SEQRES`, then ATOM/HETATM residue extraction.
- Preserved coordinate-bearing supported chemistry and retained the no-fabricated-coordinate rule for ambiguous/unsupported derivatives.
- Added round-trip regression for canonical, terminal-modified, linker, D-AA, non-natural, lipid/acyl, label, and side-chain-label constructs.
- Removed runtime workspace/log artifacts from the GitHub-ready source package and synchronized release metadata/documents to R14.

## 2026-09-21 — Pepforge V4.0.0 R13

- Fixed the remaining SPPS blank-startup/idle-refresh route that could call the legacy parser with no visible sequence and show `Parse error: Core sequence is empty`.
- Background/tab/startup output refresh now treats an empty Project Manager Sequence as a valid idle state and never auto-rebuilds the plan until a visible sequence exists.
- Preserved R12 behavior: `pm_sequence` remains authoritative, stale legacy `seq` is not resurrected, and explicit Generate/Apply still validate missing input.
- Added regression coverage for blank visible sequence + stale legacy state and fresh real-Tk startup/refresh.

## 2026-09-21 — Pepforge V4.0.0 R12

- SPPS Project Manager visible Sequence is now the authoritative Generate/Apply input.
- Fixed repeated `Core sequence is empty` failures caused by stale blank legacy sequence state.
- Added source-of-truth and real-Tk GHK/1000/2-CTC regression coverage.

# Pepforge V4.0.0 R10 — 2026-09-14

- Fixed a Windows SPPS Planner launch failure where startup/session diagnostics could call `_log()` after the streamlined Pepforge surface had omitted `log_text`. Logging now safely buffers diagnostics when the legacy Log widget is absent or already destroyed.
- Added a shared dependency-free MSDS/SDS lookup helper. Pepforge opens a Google SDS/MSDS search in the user's default browser; it does not scrape, cache, or certify third-party SDS content.
- SPPS Planner now exposes **MSDS / SDS** from the Project Manager global actions and prioritizes selected Materials, Plan, and Cleavage components before falling back to visible synthesis setup reagents/solvents.
- PDE now exposes **MSDS / SDS (Google)** in Chemistry / Constraints and Log / Results. Selected candidate chemistry is prioritized, with enabled design-chemistry tokens available as lookup choices.
- PDE intentionally does not convert natural one-letter residues into guessed protected SPPS reagent identities. Supplier/product/CAS and protection state must be verified against the material actually used.
- Suite version remains **V4.0.0**.

# Pepforge V4.0.0 — Current Final Improved / R9 SPPS Evidence Persistence Hardening (2026-09-10)

- Fixed embedded SPPS active Run/Work Item lineage lookup: `experimental_workflow.active_run_context()` now imports the real `spps_v4_gui` data/project modules instead of a nonexistent `suite_gui` path that could silently collapse linked IDs to empty strings.
- Routed integrity-critical Loading/Cleavage/Outcome/Issue evidence reads and writes through the initialized persistent experimental-database path so locally recorded Public-build evidence is not bypassed by an uninitialized workflow entry point.
- Hardened bundled-seed initialization without changing the Public data boundary: an incomplete seed import is no longer cached as successfully initialized, while provenance-based retries remain idempotent. The Pepforge Public package still bundles no Private experimental seed/history.
- Preserved zero-valued cleavage components such as `TIS = 0` and added fallback to the active peptide's persisted cleavage rows when the visible cleavage table is not populated, preventing an otherwise valid TFA/Water/TIS condition snapshot from being partially lost.
- Made Loading/Cleavage/Outcome/Issue persistence failures visible to the operator instead of allowing a failed save to look like a successful record. Experimental-DB initialization failure is retained, retried when Recommendations/Lab History opens, and surfaced explicitly if it remains unavailable.
- Hardened Loading target-recommendation argument routing so shared/controller context cannot trigger a legacy-compatible API `TypeError`; bounded same-context evidence behavior remains unchanged.
- Added real two-process regression coverage: process A records Verified Loading/Cleavage evidence, exits, process B reopens the same SQLite database, verifies the linked records, and confirms the advisors reuse the persisted evidence.
- Full split working-tree regression: **437 passed / 1 intentional Public-only skip / 0 failed** across 438 collected tests. Direct Release Gate remains **25 passed / 0 failed** with compile/source-integrity/stale/package findings at zero.
- Suite version remains fixed at **V4.0.0**; integrated SPPS component identity remains **V5.0.0 Public/Data-Sanitized**.

# Pepforge V4.0.0 — Current Final Improved / R8 Feedback Integration (2026-09-09)

- Restored SPPS Project Manager sequence persistence: saved peptide sequences are restored on reopening, while genuinely new projects still start with a blank Sequence field. Window-close and File → Exit now save the active session before destruction.
- Reconnected resin selection to the original SPPS `settings_db.csv` loading defaults. Known original values are reused exactly; unsupported/expanded resin entries do not receive invented loading values.
- Set the direct-loading checkbox default to ON for new and legacy peptide items. The chemistry engine still gates the actual loading reaction to direct-loading resin profiles only, so a checked box does not fabricate a loading step for preloaded/non-direct resins. Workflow → SPPS launches also carry the default-ON loading flag.
- Added Workflow PDE peptide-length controls using the native PDE keys: RANDOM (Min/Max) or FIX (Fixed), token-count length semantics, and trim-to-length behavior. Length changes invalidate stale downstream PDE/PSB/SPPS lineage like the other PDE settings.
- Updated Docking Workbench conservative interaction evidence to the owner-supplied PyMOL manual criteria: H-bond 3.5 A with directional review, hydrophobic 3.3–5.0 A, salt bridge 4.0 A, pi-pi/cation-pi 5.0 A with geometry, serious clash by >=0.4 A vdW overlap, disulfide ~2.0–2.1 A, water bridge 2.5–3.5 A each, metal <=3.0 A, halogen <=3.5 A with direction, aromatic-S <=5.0 A, weak C-H...O/N <=3.5 A, and NH-pi <=3.9 A secondary screening.
- Added a visible `Specific interactions — conservative PyMOL criteria` table to the Docking Contacts page. Specific interactions use atom/group/ring-centroid geometry; the older coarse centroid screening remains a separate backward-compatible triage layer.
- Added R8 regression coverage for persistence, original resin-loading defaults, direct-loading gating, Workflow length mapping, Workflow SPPS loading hand-off, interaction cutoffs, disulfide/clash separation, water/metal/halogen screening, and visible specific-interaction output.
- Suite version remains fixed at V4.0.0.

# Pepforge V4.0.0 — Current Final Improved / R7 Workflow Handoff UI (2026-09-08)

- Made the Hot Spot → PDE target hand-off explicit in Workflow Mode and added a visible PSB input-candidate dropdown that mirrors the current PDE candidate list. Selecting a candidate from either PDE or PSB keeps the same active candidate lineage.
- Labeled the PSB result selector as `Ranked structure`; the existing dropdown remains the selector for generated rank outputs before opening the structure output.
- Changed Workflow SPPS behavior from an invisible background quick-plan action to `Open SPPS Planner`, launching the full standalone SPPS Planner in a separate process with the active candidate prefilled.
- Expanded Workflow resin choices to the same public SPPS resin catalog and added the requested `Resin → Loading mmol/g → Scale mmol` input order. Sequence, resin, loading, scale, and Workflow project are passed to the SPPS Planner through an explicit launch hand-off; ordinary standalone SPPS startup remains blank.
- Removed the redundant bottom `Evidence / Runtime Status` text panel. Workflow progress, per-stage status labels, message dialogs, and normal application logging remain; evidence-matrix export buttons remain because they create real candidate-comparison artifacts.
- Added R7 regression coverage for Hot Spot→PDE, PDE→PSB selector mirroring, ranked-structure dropdown, SPPS subprocess launch/prefill, resin catalog reuse, requested SPPS field order, and removal of the redundant runtime panel.
- Preserved all R6 Docking residue-identity/numbering hardening, Workflow PDE revision invalidation, PDE option catalog single-source behavior, and lazy PDE ML startup changes. Suite version remains fixed at V4.0.0.

# Pepforge V4.0.0 — Current Final Improved / R6 Lineage Hardening (2026-09-08)

- Hardened Docking Workbench residue identity mapping so D-amino acids and non-natural residues are never silently canonicalized to L-amino-acid residue names during PSB metadata remapping.
- Corrected peptide residue numbering so N-terminal modifiers and linkers such as Ac/Ahx do not consume peptide residue positions; C-terminal atoms remain attached to the preceding peptide residue.
- Preserved residue-aware PSB PDB chain-P numbering when a companion JSON sidecar is unavailable, and prevented modified tokens from being fabricated as GLY in combined-complex review PDB exports.
- Added Workflow PDE dirty-state invalidation and monotonic PDE revision lineage so a chemistry/target/profile change cannot reuse stale PDE candidates, PSB structures, or SPPS completion state.
- Derived Workflow progress from the active candidate/revision lineage instead of stale global outputs. Progress values remain UI stage indicators, not scientific probabilities.
- Centralized PDE chemistry option catalogs in a lightweight import-safe module; Workflow exposes only options verified as explicitly buildable by the V4 PSB graph route.
- Deferred optional `ml_trainer` import until training or trained-model reranking is actually requested, reducing unnecessary standalone PDE startup work.
- Added R6 lineage-hardening regression coverage for D-AA/non-natural residue identity, terminal/linker numbering, sidecar-free PDB numbering, modified-complex export, Workflow stale-state prevention, PDE option catalog consistency, and startup lazy loading.
- Suite version remains fixed at V4.0.0. Native Windows GUI/DPI/PyMOL and the owner's exact local CIF remain the final acceptance boundary.

# Pepforge V4.0.0 — Current Final Improved / RC8 (2026-09-07)

- Integrated the owner-supplied peptide sequence/structure-design literature summary as the V4 Phase-1/Phase-2 evidence basis while keeping production MD/trajectory work in V5.
- Added explicit PeptideBuilder-method provenance for canonical-L linear backbone search seeds. Pepforge uses its own chemistry graph and does not require the external PeptideBuilder package at runtime.
- Added post-relaxation phi/psi seed-fidelity auditing so an alpha/beta/PPII search seed is not assumed to remain in its intended basin after geometry cleanup.
- Added explicit structure-generation route metadata: plain canonical-L linear peptides may use deterministic phi/psi search seeds; D/non-natural/linker/side-chain-modified constructs remain on the explicit chemistry-graph/RDKit route unless an existing motif-specific rule applies.
- Added covalent graph validation across every adjacent token atom range. Missing encoded linkages or disconnected components are build failures rather than display-only structures.
- Refined sequence evidence to separate internal Pro/Gly helix-breaker context from terminal/cap-adjacent context, report Gly runs, local charge patches, and odd/even beta-face hydrophobic context.
- Added PeptideBuilder/helix-cap/beta-context entries to the scientific-evidence registry and a dedicated `docs/STRUCTURE_DESIGN_EVIDENCE_V4.md` contract.
- Removed remaining user-facing/documentation claims that V4 performs trajectory analysis. V4 keeps static PDB/SDF review and external-MD hand-off/summary metadata; production MD, automatic trajectory generation, MDTraj/MDAnalysis analysis and clustering remain V5 scope.
- Preserved the RC7 clean SPPS engine/controller architecture, RC6 Workflow/PSB scope cleanup, RC5 Docking Workbench readability/contact-residue redesign, Windows icon/path fixes, and the V4.0.0 suite version.

# Pepforge V4.0.0 — Final Polish RC7 (2026-09-04)

- Reviewed the owner-supplied SPPS Planner V5.0.0 Public FINAL CLEAN ENGINE as the accepted V5 chemistry baseline and V6.0.0 Public R7 only as a development-architecture reference. Private experimental history/seed data was not imported.
- Replaced the embedded SPPS engine's remaining historical implementation stack with the clean single material-generation pipeline while preserving Pepforge's qualitative literature-validation layer and the operator-requested blank material Warning fields.
- Removed the `_v23/_v25/_v26` Classic batch-controller wrapper/alias tail. Batch/Project behavior now lives in `spps_v4_gui/modules/classic_batch_controller.py` and is composed by ordinary inheritance.
- Project Manager action routing now uses explicit widget references (`pm_generate_button`, `pm_apply_button`, advisor/data buttons, duplicate/delete/export) instead of scanning button labels and rebinding by displayed text.
- Added a stable `spps_v4_gui.recommendation` namespace so workflow code no longer imports version-suffixed advisor/model implementations directly; heavy recommendation backends remain lazy-loaded.
- Added an explicit recoverable-error policy for controller boundaries and regression tests that reject reintroduction of the historical engine/controller wrapper stacks or text-based Project action routing.
- Verified V5 CLEAN chemistry parity for the accepted Plan/operation/reagent/step-material/cleavage/summary outputs. Total-material chemistry matches after excluding only the intentionally suppressed user-facing Warning text; Pepforge literature evidence remains a separate validation layer.
- Preserved V4 scope: no MD/trajectory feature was reintroduced and no V6 Run/Preflight/Repeat/Run-Package lifecycle feature was copied into V4.

# Pepforge V4.0.0 — Final Polish RC6 (2026-09-04)

- Removed MD trajectory analysis from the V4 user scope. PSB now exposes only static `Analyze Structures` and `Compare Structures`; the `Analyze Trajectory` UI action, CLI command, public API exposure, and packaged trajectory analyzer implementation are reserved for the V5 production-MD workflow.
- Moved Workflow Mode `Save sequence to project` out of the Shared Input Sequence text panel and placed it beside the section title so the rectangular sequence panel contains only sequence input.
- Tightened PSB Output folder/Browse layout so the path field and Browse button form one contiguous row instead of leaving a large visual gap.
- Flattened the embedded SPPS material presentation path: the historical V2.1.9 → V2.2.1 → V2.2.2 wrapper chain was removed. Step/total material builders now execute the core calculation once and pass through one canonical display pipeline for resin naming, protected-AA bottle names, liquid-unit presentation and protocol ordering.
- Verified the flattened SPPS material pipeline against RC5 snapshots for `Ac-EEMQRR-NH2`, `EEMQRR / 2-CTC`, `ACDC`, and `K(FITC)-AEEA-dK-NH2`; step and total material records remain identical.
- Preserved the RC5 Docking Workbench readability redesign and V4.0.0 version boundary.

# Pepforge V4.0.0 — Final Polish RC4 (2026-09-04)

- Applied Windows feedback from the RC2/RC3 source run while keeping the suite version fixed at V4.0.0.
- Hardened the shared window icon helper to use the Pepforge `.ico` on Windows and PNG fallback elsewhere, preventing PDE/tool title bars from falling back to a generic Tk icon.
- Simplified PSB ranked PDB filenames to `*_rank1.pdb` ... `*_rank5.pdb`; backbone-family classification remains in CSV/JSON/report metadata instead of filenames. Removed redundant per-rank `*_canonical_view.pdb` duplicates while retaining the bundle-level canonical-L review view where applicable.
- Added `Analyze Structures` for direct PDB/SDF geometry review without requiring an MD trajectory; production MD/trajectory analysis is reserved for V5.
- Added explicit Docking Workbench sequence helper buttons and hardened the sequence-to-coordinate bridge with an ASCII-safe RDKit staging root for Windows Unicode user/output paths.
- Synchronized the embedded SPPS engine/compound identity rules to the user-supplied SPPS Planner V5.0.0 Public Final baseline. N-terminal purpose prose such as `for N-terminal ...` is no longer part of the material identity, legacy aliases remain readable, and terminal material Note/Warning fields stay blank under the V5 Final contract.
- Reviewed the user-supplied V6.0.0 R4 development checkpoint as reference only. V6 is incomplete and was not used as a wholesale replacement; only the general legacy N-terminal purpose-suffix cleanup rule was adopted where it strengthens backward compatibility without changing the embedded component version.
- Workflow Mode sections **2. Shared Input Sequence** and **4. Evidence / Runtime Status** now use explicit 1 px rectangular panels; sections 1 and 3 retain their existing layout.

# Pepforge V4.0.0 — 2026-09-02 PSB / Workflow Refinement

## V4.0.0 evidence/workflow + SPPS FAST_OPEN refinement (2026-09-02)
- Hardened release integrity: source audit now checks module-level runtime attribute reassignment, pass-only and NotImplemented-only functions; release verification removes only transient Python/test caches before artifact scanning.

- Integrated the Public/Data-Sanitized SPPS Planner V5 `FAST_OPEN` changes while retaining Pepforge LOT/Batch non-exposure and no Private/local history.
- Added experimental-database initialization fast-path, shared run/work-item identity across loading/cleavage/outcome/issue records, quick measured-loading capture, five-new-verified loading-model rebuild readiness, and content-fit UI helpers.
- Added a central scientific-evidence registry and stage-by-stage modified-peptide support matrix.
- Added geometry-aware protein/peptide interaction evidence with separate conservative-manual and tool-compatible profiles; legacy coarse Docking Workbench contact tables remain backward compatible.
- Added Workflow Hot Spot chemistry-profile hand-off that PDE can consume without converting sequence chemistry into 3D contact or affinity claims.
- Added V4 docking-lineage/PyMOL review preparation only; actual docking execution remains a future V5 scope.
- Added candidate evidence-matrix comparison without an aggregate binding/affinity score.
- Upgraded Structure Consensus to v2 with local-backbone displacement, nonlocal CA contact-map Jaccard agreement, lost/gained contacts and optional hotspot-region RMSD.
- Updated external MD preparation to V4 protocol/support-matrix planning; V4 may import external summary metadata but trajectory-derived analysis is reserved for V5.


## V4.0.0 design/structure theory refinement checkpoint (2026-09-02)

- Added Conformational Strategy optimizer policies while preserving the five existing Design Objective modes and Interaction Only objective contract.
- Refined alpha, beta/hairpin, PPII, 3_10/Aib and coiled-coil evidence with explicit claim boundaries.
- Added literature-guided dP-G/Aib-G turn search seeds, explicit Aib 3_10 seeds, bidirectional nonlocal hairpin contact audit, C-alpha beta-turn geometry and beta-extended hairpin flank search seeds.
- Preserved new theory fields through candidate manifests and Candidate Summary Reports.
- Added optional coarse Hot Spot chemistry complementarity evidence without converting it to contact/docking/affinity claims.

- Normalized PDE `pde_objective_mode` to downstream PSB design intent and preserved unique PDE candidate IDs across PSB/SPPS workflow stages.
- Added candidate-centered evidence-only Summary Reports; absent Docking, trajectory, and experimental stages remain explicitly unavailable.
- Hardened Pro-rich PPII seed generation against individual RDKit ring-constrained torsions, followed by measured relaxed-geometry classification.
- Added explicit Preferred Structure audit metadata and limitations for beta-hairpin/turn-rich, amphipathic-alpha, and coiled-coil requests.
- Verified an eight-family PSB sanity probe without forcing unsupported families: alpha, amphipathic alpha, 3_10, beta strand, PPII, and coiled-coil returned requested-family candidates; turn-rich used measured match plus explicit fallbacks; beta-hairpin reported clean fallbacks when the quick probe did not sample a hairpin.
- Preserved SPPS Planner V5 WORKFLOW_REFINED behavior, Cys hard rule, Public/Private boundary, LOT/Batch non-exposure, and Pepforge V4.0.0 suite version.

# Pepforge V4.0.0 — 2026-09-01 SPPS V5 Workflow Refined

- Integrated the user-supplied SPPS Planner V5.0.0 WORKFLOW_REFINED Public/Data-Sanitized changes into the embedded Pepforge SPPS component while keeping the Pepforge suite at V4.0.0.
- Added bounded target-loading inversion from reviewed same-resin/same-C-terminal-AA loading history; recommendations interpolate only within observed evidence and never extrapolate beyond it.
- Added a separate post-cleavage rescue workflow for operator-selected NH4I reduction; rescue calculation/state is never inserted into the cleavage cocktail.
- Routed coupling problems/deviations through synthesis issue/evidence logging instead of silently treating them as successful coupling records.
- Preserved the Cys cleavage-equivalent hard rule, LOT/Batch non-exposure, Public/Private data boundary, Pepforge result-bundle exports, and the backward-compatible internal `spps_v4_gui` namespace.

# Pepforge V4.0.0 — 2026-08-28

- Fixed PSB Fast-mode coil-first ranking for strongly helix-supported canonical peptides.
- Added constrained canonical backbone-seed relaxation and per-conformer steric-clash screening.
- Made Balanced Top 5 the recommended/default PSB preset while retaining Fast as an option.
- Added canonical-L residue-aware PDB view exports without canonicalizing modified/D/linker chemistry.
- Fixed guided seed family recognition (`*_guided_variantN`).

# Changelog

## V3.0.0 scientific-quality and latest SPPS V4 maintenance refresh (2026-08-19)
- PSB Top-5 selection now follows PDE preferred-structure intent without artificial family diversity; severe-clash structures are not used to fill the set, and default PDB/PyMOL views hide hydrogens while calculations retain them.

- Replaced the PDE's former weighted-elite implementation behind the `NSGA2` label with real non-dominated sorting, crowding distance, tournament selection, and Pareto environmental selection while retaining the existing weighted score for reporting/tie-break context.
- Made final PDE diversity chemistry-aware across core sequence, construct tokens, chemical features, and physicochemical properties; added stable `PF-CAND-*` identifiers and candidate-manifest export for cross-module traceability.
- Removed RNG consumption from diversity fitness evaluation so locked-seed runs are reproducible from the same configuration.
- Connected PSB evidence profiles to actual sampling workload and canonical-L torsion-basin seed generation, added hairpin/turn-oriented guided variants where eligible, and kept D/non-natural/modified constructs outside canonical-L torsion forcing.
- Added explicit Top-5 diversity audit metadata and separated requested canonical-L seed families from seed conformers actually applied.
- Replaced symmetry-permutation RMSD work for same-molecule conformers with identity-mapped heavy-atom aligned RMSD to avoid pathological runtimes while preserving conformational diversity screening.
- Added stable candidate-manifest hand-off across Design, Structure, SPPS, and Docking workflow stages without removing the existing CSV/PDB/SDF/XLSX/JSON artifacts.
- Synchronized the embedded SPPS Planner with the latest user-supplied Public/Data-Sanitized V4 evidence/parser/engine layer; Private/Local experimental data remain outside Pepforge.
- Updated SPPS cleavage behavior to the latest evidence-first contract: exact conditions come from one complete reviewed compatible historical record; generic chemistry guidance cannot fabricate or auto-apply a named-peptide cocktail.
- Fixed the temporary structure/docking bridge so canonical one-letter sequences such as `ACDE-NH2` are not misread as an `Ac-` terminal modifier.

> Earlier changelog entries are preserved as historical records of prior implementations. Where they describe a hard-coded `Ac-EEMQRR-NH2` cleavage contract, that behavior is superseded by the 2026-08-19 latest-SPPS evidence-first integration above.

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