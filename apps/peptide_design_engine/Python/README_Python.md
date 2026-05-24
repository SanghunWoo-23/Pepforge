# Python CLI

Run the integrated peptide design engine from a terminal.

## Basic run

```bash
python Python/peptide_cli.py --target EGFR --top-n 10 --outdir outputs/demo
```

## Docking-ready advanced run

```bash
python Python/peptide_cli.py \
  --target EGFR \
  --design-mode BRIDGE_LINKER \
  --docking-ready-mode ADVANCED \
  --top-n 25 \
  --outdir outputs/bridge_demo
```

## Optional ML reranking

```bash
python Python/peptide_cli.py \
  --target EGFR \
  --top-n 25 \
  --use-optional-ml \
  --ml-rerank-weight 0.25
```

## Optional pseudo-docking input preparation

```bash
python Python/peptide_cli.py \
  --target EGFR \
  --top-n 10 \
  --prepare-pseudodocking-colab \
  --receptor-sequence "YOUR_PROTEIN_SEQUENCE"
```
