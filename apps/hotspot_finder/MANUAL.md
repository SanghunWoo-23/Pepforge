# Sequence Hotspot Finder v1.0 Manual

This manual explains how to use the GitHub + Colab version of Sequence Hotspot Finder.

---

## 1. Purpose

Sequence Hotspot Finder ranks candidate hotspot residues using only amino acid sequence input plus optional external annotations. It is intended for early-stage peptide/protein engineering and experimental planning.

Correct interpretation:

```text
candidate hotspot prioritization
sequence-only residue ranking
mutation candidate screening
hypothesis generation
```

Incorrect interpretation:

```text
definitive hotspot prediction
experimental validation replacement
accurate binding ΔΔG prediction
complete interface prediction
```

---

## 2. GitHub + Colab design

The intended workflow is:

```text
GitHub repository:
  source code, token DB, config, examples, tests

Google Colab:
  clone GitHub repo
  install dependencies
  launch editable UI
  run analysis
  download output ZIP

Local Python:
  run the same engine using run_hotspot_cli.py
```

This avoids copying the full engine code into Colab and keeps the project maintainable.

---

## 3. Data you can edit in Colab

The Colab UI allows direct editing of:

```text
FASTA/direct sequence input
token_db.csv
sidechain_mod_db.csv
default_config.json
domain CSV
structure feature CSV
conservation CSV
```

The runtime copies are used for analysis, so the GitHub files are not overwritten from Colab unless you manually commit changes later.

---

## 4. Input rules

Plain sequence:

```text
ACDEFGHIKLMNPQRSTVWY
```

Modified peptide sequence:

```text
Ac-K-dA-Ahx-W-FITC
```

Side-chain modification:

```text
K[Biotin]-Ahx-dR-W-NH2
```

FASTA:

```text
>protein_1
MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGE
```

---

## 5. Token DB

Token recognition is controlled by:

```text
data/token_db.csv
```

Required columns:

```text
token,class,model_token,charge,hydrophobicity,notes
```

Extended columns included in v1.0:

```text
aromaticity
polarity
bulkiness
flexibility
is_terminal_only
is_sidechain_allowed
esm_policy
hotspot_penalty
hotspot_bonus
```

Examples:

```csv
token,class,model_token,charge,hydrophobicity,notes
A,natural_L_amino_acid,A,0,1.8,Alanine
dA,D_amino_acid,A,0,1.8,D-alanine
Hyp,non_natural_amino_acid,P,0,-1.6,Hydroxyproline mapped to P
Ahx,linker,X,0,0,Aminohexanoic acid linker
GGGGS,linker,GGGGS,0,-0.5,Peptide linker expanded as GGGGS
Ac,N_terminal_modification,,0,0,N-terminal acetylation
FITC,label,,0,0,Fluorescent label
```

---

## 6. Side-chain modification DB

Side-chain modifications are controlled by:

```text
data/sidechain_mod_db.csv
```

Required columns:

```text
mod,class,charge_delta,hydrophobicity_delta,bulkiness_delta,hotspot_bonus,notes
```

Examples:

```csv
Biotin,affinity_tag,0,1.2,2.0,0.04,Biotin side-chain modification
PO3H2,phosphorylation,-2,-1.5,1.0,0.06,Phosphorylation-like group
Pal,lipidation,0,4.0,3.0,0.03,Palmitoylation-like group
```

For input `K[Biotin]`, the base residue `K` is scored and the Biotin side-chain feature is added.

---

## 7. Config file

Config path:

```text
data/default_config.json
```

Important options:

```json
{
  "use_esm": false,
  "esm_model": "esm2_t6_8M_UR50D",
  "window_size": 900,
  "overlap": 150,
  "batch_size": 4,
  "use_masked_marginal": true,
  "use_mutation_sensitivity": true,
  "max_mutation_scan_length": 2500,
  "merge_position_mode": "model_position"
}
```

Recommended Colab model:

```text
esm2_t6_8M_UR50D
```

---

## 8. Long-sequence analysis

Long sequences are processed by domain-aware sliding windows.

If domain CSV exists:

```text
split by user-defined domains
if a domain is longer than window_size, split that domain into overlapping windows
stitch scores back to original model positions
```

If no domain CSV exists:

```text
analyze the full sequence by overlapping windows
```

Recommended settings for ~2000 aa:

```text
window_size = 900
overlap = 150
batch_size = 2–4
model = esm2_t6_8M_UR50D
```

For >5000 aa:

```text
1. run rule-based first
2. identify high-score regions
3. re-run ESM on selected domains/regions
```

---

## 9. Optional CSV files

### Domain CSV

```csv
record_name,domain_name,start,end
protein_1,N_terminal_domain,1,280
protein_1,catalytic_domain,281,760
```

### Structure feature CSV

```csv
record_name,position,solvent_accessibility,disorder_score,contact_number,pLDDT
protein_1,25,0.72,0.18,8,91.2
```

### Conservation CSV

```csv
record_name,position,conservation_score
protein_1,25,0.91
```

Use `merge_position_mode` to control whether these positions refer to `model_position`, `display_position`, `original_position`, or `residue_position`.

---

## 10. CLI examples

Rule-based:

```bash
python run_hotspot_cli.py --input examples/example_input.fasta --outdir outputs --no-esm
```

ESM-enabled:

```bash
python run_hotspot_cli.py --input examples/example_input.fasta --outdir outputs --use-esm --model esm2_t6_8M_UR50D
```

With optional files:

```bash
python run_hotspot_cli.py \
  --input examples/example_input.fasta \
  --outdir outputs \
  --domains examples/example_domains.csv \
  --structure-features examples/example_structure_features.csv \
  --conservation-features examples/example_conservation_features.csv
```

---

## 11. Output interpretation

Important columns:

```text
record_name
raw_sequence
model_sequence
display_position
original_position
residue_position
model_position
input_token
class
model_token
is_d_form
is_non_natural
is_linker
is_label
rule_score
esm_embedding_score
esm_unpredictability_score
esm_mutation_sensitivity
conservation_score
structure_score
hotspot_score
hotspot_rank
confidence
reason
warning
```

Score interpretation:

```text
0.75–1.00: high candidate
0.50–0.75: medium candidate
0.00–0.50: low candidate
NaN: annotation-only token
```

---

## 12. Validation

Before analysis, v1.0 validates:

```text
token DB required columns
duplicate tokens
numeric charge/hydrophobicity
config window/overlap/batch/weights
domain CSV columns
structure CSV columns
conservation CSV columns
```

This is important because the Colab UI allows users to edit the input databases directly.

---

## 13. Utility scripts

Create conservation template:

```bash
python scripts/make_conservation_template.py --input examples/example_input.fasta --output conservation_template.csv
```

Compute simple conservation from aligned FASTA:

```bash
python scripts/compute_conservation_from_msa.py --msa aligned.fasta --record-name protein_1 --output conservation_features.csv
```

Extract simple PDB-derived structure proxies:

```bash
python scripts/extract_structure_features_from_pdb.py --pdb model.pdb --record-name protein_1 --output structure_features.csv
```

The PDB script is a lightweight proxy extractor, not a full SASA calculator.

---

## 14. Tests

Run:

```bash
pytest tests
```

The tests cover parser behavior, no-ESM analysis, output creation, and validation.

---

## 15. Troubleshooting

CUDA out of memory:

```text
batch_size 8 → 4 → 2
window_size 900 → 700
turn off mutation sensitivity
run rule-based first
```

Unknown token:

```text
Add the token to data/token_db.csv
```

Modified peptide gives odd ESM result:

```text
Check model_sequence and X count. ESM-2 does not directly understand synthetic modifications.
```

---

## 16. Recommended scientific language

Use:

```text
candidate hotspot prioritization
sequence-only residue ranking
ESM-2-derived contextual scoring
mutation sensitivity estimation
modification-aware annotation
```

Avoid:

```text
definitive hotspot prediction
guaranteed functional residue identification
replacement for alanine scanning
accurate ΔΔG prediction
```


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
