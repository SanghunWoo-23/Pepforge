# Python CLI / EXE / Continual ML Guide

## Files

```text
peptide_engine.py   # core design engine, preserved
peptide_cli.py      # EXE-ready CLI wrapper
data_manager.py    # imports AF3/PRODIGY/docking/experimental CSVs
ml_trainer.py      # lightweight JSON surrogate model trainer
```

## Smoke test

```bash
python -m py_compile peptide_engine.py peptide_cli.py data_manager.py ml_trainer.py
python peptide_cli.py --preset fast --target DELIKFVRWA --pop 20 --gen 2 --top-n 5 --outdir smoke_outputs
```

## Continual learning workflow

1. Generate candidate peptides.
2. Evaluate selected candidates externally using AF3/PRODIGY/docking/wet-lab assays.
3. Save those values as CSV using the templates in `../data/templates/`.
4. Append them into the training database.
5. Train the lightweight surrogate.
6. Use the saved model for reranking the next generated candidates.

```bash
python peptide_cli.py --import-training-data ../data/templates/experimental_import_template.csv --training-db ../data/training_data.csv --no-run
python peptide_cli.py --train-ml --training-db ../data/training_data.csv --ml-label experimental_binding --models-dir ../models --no-run
python peptide_cli.py --preset exploration --target DELIKFVRWA --trained-model ../models/surrogate_model.json --outdir outputs_ml
```
