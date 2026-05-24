# Sequence Hotspot Finder v1.0

**Sequence Hotspot Finder** is a GitHub + Google Colab ready toolkit for prioritizing candidate hotspot residues from amino acid sequences. It supports canonical proteins, modified peptides, D-form residues, non-natural residues, linkers, terminal modifications, labels, side-chain modifications, and long proteins using domain-aware sliding windows.

This project is designed for **candidate hotspot prioritization**, not definitive biological validation. It should be used to narrow down residues for follow-up experiments such as alanine scanning, conservative mutation, binding assays, structure inspection, or DMS.

---

## 1. What is new in v1.0

Compared with the earlier MVP, this version adds:

```text
1. Cleaner GitHub package structure
2. Improved Colab UI workflow
3. validation.py for token DB, config, domain CSV, structure CSV, conservation CSV
4. Domain-aware + sliding-window combined segmentation for long sequences
5. Safer ESM window-size handling
6. Explicit display_position / original_position / residue_position / model_position mapping
7. Selectable merge_position_mode
8. Extended token_db.csv
9. New sidechain_mod_db.csv
10. More reproducible output ZIP
11. token_db_used.csv, sidechain_mod_db_used.csv, input_used.fasta, run_summary.txt
12. Utility scripts for conservation template, MSA conservation, and simple PDB-derived structure proxy
13. Basic pytest tests
14. Clearer documentation separating implemented, optional, and future-extension features
```

---

## 2. Repository structure

```text
sequence-hotspot-finder/
├─ sequence_hotspot_finder/
│  ├─ __init__.py
│  ├─ engine.py
│  ├─ parser.py
│  ├─ scoring.py
│  ├─ esm_features.py
│  ├─ io_utils.py
│  └─ validation.py
│
├─ colab/
│  └─ sequence_hotspot_finder_colab.ipynb
│
├─ data/
│  ├─ token_db.csv
│  ├─ sidechain_mod_db.csv
│  └─ default_config.json
│
├─ examples/
│  ├─ example_input.fasta
│  ├─ example_domains.csv
│  ├─ example_structure_features.csv
│  └─ example_conservation_features.csv
│
├─ scripts/
│  ├─ make_conservation_template.py
│  ├─ compute_conservation_from_msa.py
│  └─ extract_structure_features_from_pdb.py
│
├─ tests/
│  ├─ test_parser.py
│  ├─ test_no_esm_run.py
│  └─ test_validation.py
│
├─ outputs/
├─ run_hotspot_cli.py
├─ requirements.txt
├─ README.md
├─ MANUAL.md
├─ CHANGELOG.md
└─ LICENSE
```

---

## 3. Supported input examples

Plain sequence:

```text
ACDEFGHIKLMNPQRSTVWY
```

FASTA:

```text
>protein_1
MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGE
```

Modified peptide:

```text
Ac-K-dA-Ahx-W-FITC
```

Side-chain modification:

```text
CHS-PEG4-K[Biotin]-dR-W-NH2
```

Multi-record FASTA:

```text
>pep1
KLVFFAE
>pep2
Ac-K-dA-Ahx-W-FITC
>protein_domain
MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGE
```

---

## 4. Token parsing model

The parser is token-based. If a sequence contains hyphens, tokens are split by `-`. If no hyphen is present, the sequence is parsed as one-letter amino acids.

Example:

```text
Ac-K-dA-Ahx-W-FITC
```

Parsed as:

```text
Ac    → N_terminal_modification
K     → natural_L_amino_acid
dA    → D_amino_acid mapped to A
Ahx   → linker mapped to X
W     → natural_L_amino_acid
FITC  → label
```

The ESM-compatible model sequence becomes:

```text
KAXW
```

The original tokens remain preserved in the result table.

---

## 5. Position mapping

This version explicitly tracks multiple position systems.

| Column | Meaning |
|---|---|
| `display_position` | Token order in original input |
| `original_position` | Alias of display position for user-facing input |
| `residue_position` | Residue-like token count excluding terminal/label annotations |
| `model_position` | Position in ESM-compatible model sequence |

This matters for modified peptides because input-token positions and ESM model positions can differ.

Example:

```text
Ac-K-dA-Ahx-W-FITC
```

| token | display_position | model_position |
|---|---:|---:|
| Ac | 1 | NA |
| K | 2 | 1 |
| dA | 3 | 2 |
| Ahx | 4 | 3 |
| W | 5 | 4 |
| FITC | 6 | NA |

Optional CSV files can be merged using:

```json
"merge_position_mode": "model_position"
```

Other supported values:

```text
display_position
original_position
residue_position
model_position
```

---

## 6. Main features

Implemented in this package:

```text
FASTA/direct input parsing
Modified token parsing
D-form residue recognition
Non-natural residue mapping
Linker/terminal/label annotation
Side-chain modification database
Rule-based physicochemical scoring
Optional ESM-2 feature extraction
Masked marginal WT log probability
Masked-distribution mutation sensitivity
Domain-aware + sliding-window long-sequence analysis
External domain CSV support
External structure feature CSV support
External conservation feature CSV support
Configurable score weights
Validation of token DB/config/CSV inputs
Reproducible output package
Colab UI notebook
Local CLI
Basic tests
```

Not automatically performed:

```text
AlphaFold/ESMFold structure prediction
Automatic BLAST/MMseqs2 search
Automatic Pfam/InterPro domain detection
True docking
Experimental ΔΔG prediction
Guaranteed hotspot identification
```

---

## 7. Installation

```bash
pip install -r requirements.txt
```

Recommended Python:

```text
Python 3.9+
```

For ESM-2, GPU runtime is recommended.

---

## 8. CLI usage

Rule-based first-pass analysis:

```bash
python run_hotspot_cli.py --input examples/example_input.fasta --outdir outputs --no-esm
```

ESM-enabled analysis:

```bash
python run_hotspot_cli.py \
  --input examples/example_input.fasta \
  --outdir outputs \
  --use-esm \
  --model esm2_t6_8M_UR50D \
  --window 900 \
  --overlap 150 \
  --batch-size 4
```

With optional domain/structure/conservation files:

```bash
python run_hotspot_cli.py \
  --input examples/example_input.fasta \
  --outdir outputs \
  --domains examples/example_domains.csv \
  --structure-features examples/example_structure_features.csv \
  --conservation-features examples/example_conservation_features.csv
```

---

## 9. Colab usage

Recommended workflow:

```text
1. Upload this repository to GitHub.
2. Open colab/sequence_hotspot_finder_colab.ipynb.
3. Set REPO_URL to your GitHub repository.
4. Runtime → Change runtime type → GPU.
5. Run the notebook.
6. Edit sequence, token DB, side-chain DB, config, and optional CSVs directly in the UI.
7. Run analysis.
8. Download the result ZIP.
```

In the Colab notebook, update:

```python
REPO_URL = "https://github.com/YOUR_ID/sequence-hotspot-finder.git"
BRANCH = "main"
```

---

## 10. Output package

Each run produces:

```text
hotspot_full_YYYYMMDD_HHMMSS.csv
hotspot_top_YYYYMMDD_HHMMSS.csv
analysis_config_YYYYMMDD_HHMMSS.json
input_used_YYYYMMDD_HHMMSS.fasta
token_db_used_YYYYMMDD_HHMMSS.csv
sidechain_mod_db_used_YYYYMMDD_HHMMSS.csv
run_summary.txt
hotspot_result_package_YYYYMMDD_HHMMSS.zip
```

If optional CSVs were used, they are also included in the result ZIP.

---

## 11. Score interpretation

| Score | Meaning |
|---:|---|
| 0.75–1.00 | high candidate hotspot |
| 0.50–0.75 | medium candidate |
| 0.00–0.50 | low candidate |
| NaN | annotation-only token such as Ac, FITC, NH2 |

The score is not a binding free energy or experimental ΔΔG. It is a prioritization score.

---

## 12. Recommended scientific wording

Recommended:

```text
This tool prioritizes candidate hotspot residues from amino acid sequences using modification-aware parsing, ESM-2-derived contextual features, masked marginal scoring, mutation sensitivity estimation, domain-aware long-sequence analysis, and optional conservation or structure-derived features.
```

Avoid:

```text
This tool definitively predicts true hotspots.
This replaces alanine scanning.
This guarantees functional residue identification.
This accurately predicts experimental ΔΔG.
```

---

## 13. License

MIT License. See `LICENSE`.


---

# Full-Data Practical Edition Note

This release includes an expanded default token database and side-chain modification database.

Current default data size:

```text
C_terminal_modification     8
D_amino_acid               20
N_terminal_modification    23
label                      15
linker                     25
natural_L_amino_acid       20
non_natural_amino_acid     66
sidechain_modification      37
```

It also includes:

```text
examples/example_supervised_features.csv
examples/example_training_labels.csv
scripts/train_supervised_model.py
scripts/predict_supervised_score.py
data/aa_property_reference.csv
data/README_DATA.md
README_COMPLETE_DATA.md
```

External large biological databases are not embedded directly. Instead, the repository provides CSV templates and merge workflows for structure features, conservation scores, domain annotations, and supervised scores.
