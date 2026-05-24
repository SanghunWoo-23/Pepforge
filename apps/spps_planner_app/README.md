# SPPS Python Planner

Python-based SPPS planner that keeps Excel-like usability while moving calculation logic into maintainable Python code.

## What this does

- Parses peptide sequences such as `Ac-EEMQRR-NH2`
- Removes protecting group notation for core sequence parsing
- Applies resin-dependent loading logic
  - Amide: DMF swell → deprotection → DMF wash → synthesis → DMF wash
  - CTC/Trityl: DCM swell → 90% DCM + 10% DMF synthesis
- Calculates wash-by-wash synthesis operations
- Calculates raw material usage in g and mL
- Exports CSV and XLSX files
- Lets you keep adding compounds and actual run data
- Includes ML-ready data log and simple ML/anomaly-detection functions

## Quick start

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Or on Windows, double-click:

```text
run_app.bat
```

## CLI example

```bash
python cli.py --seq Ac-EEMQRR-NH2 --resin Amide --mmol 400 --outdir outputs/std_400mmol
```

Expected STD check:

```text
DMF = 304,800 mL
Piperidine = 11,200 mL
DCM = 12,000 mL
```

## Editable data files

- `data/compounds.csv` — compound/AA/label/linker database
- `data/resins.csv` — resin rules
- `data/process_rules.csv` — process counts and solvent fractions
- `data/actual_runs.csv` — actual run/yield/purity/usage log for future ML

## Recommended workflow

1. Use Streamlit app for input and review.
2. Export CSV/XLSX synthesis forms and raw material tables.
3. Add actual run data to `data/actual_runs.csv`.
4. Once actual target values exist, use ML Lab for first models.
