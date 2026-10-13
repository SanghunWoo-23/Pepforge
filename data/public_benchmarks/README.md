# Pepforge V5 public protein-peptide benchmark registry

This folder ships **metadata only**, not redistributed experimental coordinate files.

- Registry: `public_57_registry.csv`
- Published source: Tao et al., *J. Chem. Inf. Model.* (2020), DOI `10.1021/acs.jcim.0c00372`; 57 bound/unbound protein-peptide benchmark cases.
- Experimental coordinates: synchronized at runtime from the RCSB PDB file download service.
- Protein annotation and sequence provenance: synchronized at runtime from UniProtKB when a PDB DBREF accession is available.
- Normalization: receptor is written as chain `A`; peptide is written as chain `P` for Pepforge benchmark contracts.
- Coordinate files are intentionally not bundled in this source archive. This avoids silently freezing third-party records and preserves per-file provenance/hash at sync time.
- The `train`/`holdout` column is a deterministic **development split**, not a claim of sequence-family independence.
- `v5-public-benchmark-split-audit` detects exact accession/sequence leakage after structures have been synchronized. It does not claim thresholded sequence independence.
- Native docking tuning is computational calibration. Its score is not ΔG, Kd, affinity, or experimental activity.

Typical workflow:

```bash
python pepforge_cli.py v5-public-benchmark-sync --output-dir benchmark_data
python pepforge_cli.py v5-public-benchmark-split-audit --registry data/public_benchmarks/public_57_registry.csv --prepared-root benchmark_data --output-dir benchmark_audit
python pepforge_cli.py v5-native-docking-tune --registry data/public_benchmarks/public_57_registry.csv --prepared-root benchmark_data --output-dir tuning
python pepforge_cli.py v5-native-dock --receptor receptor.pdb --peptide peptide.pdb --output-dir result --score-profile tuning/native_docking_best_config.json
```
