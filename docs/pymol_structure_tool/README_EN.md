# Pepforge PyMOL Structure Tool v1.3.0

This is **not a PyMOL plugin**. It is a standalone modified peptide builder that generates SDF/PDB/JSON/report/PML files for direct visualization in PyMOL.

## Scope

The tool builds connected 3D starting models containing:

- 20 standard L-amino acids
- D-form canonical amino acids such as dK/dF
- non-natural amino acids such as Aib, Nle, Orn, Dab, Cit, Hyp, Cha, Nal
- linkers such as Ahx, PEG4, PEG8, AEEA
- labels such as Biotin, FITC, FAM, TAMRA, Cy5, NBD, DOTA
- chemical/lipid modifications such as Pal, Myr, Ste, Lau, Chol
- side-chain modifications such as K(FITC), K(Ahx-Biotin), K(Pal), K(Chol), C(NBD)

## Usage

```bash
python build_for_pymol.py "Ac-dK-Aib-LVFF-Ahx-Biotin-NH2" --name test --outdir outputs --confs 8
```

In PyMOL:

```pymol
@outputs/test.pml
```

## Template checks

```bash
python build_for_pymol.py --audit-templates
python build_for_pymol.py --template-manifest
```

## Limit

v1.3.0 creates connected 3D starting structures for PyMOL inspection. It does not guarantee publication/docking/MD-grade conformations for large labels or chemical groups. Replace templates with curated SDF files and perform additional minimization for downstream computational use.
