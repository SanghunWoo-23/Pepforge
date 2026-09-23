# Pepforge V5.0.0 Future Docking Plan

**Status: roadmap only. Not an active V4 docking execution backend.**

The planned V5 docking workflow should preserve the V4 lineage contract:

```text
candidate ID -> PSB conformer rank -> docking pose rank
```

Target outputs should be directly reviewable in PyMOL:

- receptor PDB/mmCIF copy;
- peptide starting conformer PDB;
- docking pose PDB files;
- complex PDB files where appropriate;
- `docking_lineage.json/csv`;
- interaction-evidence CSV per pose;
- PyMOL `.pml` review script and, where technically reliable, optional `.pse`;
- pose clustering and repeated-hotspot-interaction reports.

V5 should keep engine score, geometry evidence, clash status and interaction
recovery as separate fields. Docking score must not be described as measured
Kd/affinity, and a single top-scoring pose must not be treated as native
structure without independent validation.
