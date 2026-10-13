# Pepforge V5 — PSB + Docking Workbench + lightweight AI architecture

## Product goal

One user-facing PSB workflow should be able to:

1. generate many physically plausible peptide starting conformers;
2. retain up to five PSB models after explicit quality/ranking checks;
3. use a PDB/mmCIF receptor (or a separately predicted receptor structure);
4. run a real docking backend independently for each retained peptide model;
5. retain up to five real docking poses per peptide model;
6. export up to 25 receptor-peptide complexes for PyMOL review;
7. optionally continue selected complexes into parameter-gated MD and trajectory analysis.

The default user experience should be one orchestrated action, while Advanced mode exposes PSB and Docking Workbench details separately.

## Existing V4 assets to preserve

- RDKit ETKDG conformer generation and explicit modified-peptide graph handling.
- Sequence/PDE-aware Top-5 selection and ranked `rank1.pdb ... rank5.pdb` exports.
- Exact construct metadata/SEQRES PDB contract.
- Docking Workbench contact/interaction analysis and PyMOL exports.
- Candidate -> PSB -> docking lineage helpers.
- Public/private data separation and claim guards.

## V5 architecture

```text
Peptide construct
    -> PSB N-conformer sampling
    -> geometry / chemistry audit
    -> optional MD relaxation features
    -> Top 5 peptide models
    -> real docking backend x each model
    -> up to 5 verified poses/model
    -> Docking Workbench interaction analysis
    -> PyMOL complex PDB/PML/PSE(optional)
    -> selected pose(s) -> production MD -> trajectory analysis
```

### One-click vs advanced

- **Run Full PSB Simulation**: orchestration layer runs the validated stages in sequence.
- **Advanced PSB**: sampling, environment and ranking details.
- **Advanced Docking Workbench**: receptor preparation, site selection, engine settings, pose/interaction review.

The Docking Workbench core should be reused as a service rather than duplicated inside the PSB GUI.

## Lightweight Pepforge AI

Do **not** start by training an AlphaFold-scale coordinate generator.

V5 first AI scope:

- optional small ESM-2 sequence embedding;
- PSB numeric features (energy is same-molecule-only evidence, clash, torsion/family descriptors);
- later MD features (RMSD/Rg/RMSF/contact persistence/cluster evidence);
- later docking features (engine score kept separate from contact/clash/interaction evidence);
- supervised Pepforge ranker trained only when an explicit validated target exists.

Important: sequence ESM embedding is identical for different conformers of the same peptide. It therefore cannot by itself rank conformers. It becomes useful when combined with conformer/MD/docking-specific features and especially when learning across many peptide sequences.

### ESM chemistry boundary

- Canonical L amino-acid sequence: direct ESM embedding supported.
- Terminal/non-residue modifiers: canonical backbone may be embedded only with an explicit note that the modifier is not represented.
- D residues, non-natural residues, linkers, and side-chain-modified residues: direct ESM embedding is blocked rather than silently canonicalized.

## Backend strategy

- Structure sampling: retain Pepforge/RDKit engine; learn from PEP-FOLD/CABS-style ensemble sampling.
- MD reference backend: OpenMM candidate, parameterization gate required.
- Docking: backend adapter architecture; HADDOCK3 is a strong protein-peptide reference candidate, with optional alternatives.
- Receptor prediction: PDB/mmCIF first; ESMFold/AF3 adapters are optional and must remain distinct from MD.
- Analysis: reuse Docking Workbench interaction evidence, then add MDTraj/MDAnalysis trajectory analysis.

## No-fake contract

Prepared jobs are not completed runs. Do not create a docking pose record, docking score, MD trajectory, affinity, Kd, folding probability, or convergence result until the corresponding real backend generated/validated that artifact.
