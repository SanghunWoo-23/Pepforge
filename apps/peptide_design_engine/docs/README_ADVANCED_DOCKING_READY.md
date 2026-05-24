# Advanced Docking-Ready Upgrade

This version keeps the original engine behavior: D-form residues, non-natural residues,
linkers, tags, labels, terminal chemistry, bridge mode, motif locks, and length control
are still available.

## What changed

The engine now adds a docking-readiness layer instead of forcing candidates into L-form only.

New ranking/export fields include:

- `fit_docking_ready`
- `docking_ready_level`
- `docking_ready_score`
- `docking_param_token_count`
- `docking_param_tokens`
- `docking_surrogate_sequence`
- `docking_warning`

New output files:

- `docking_ready_candidates.csv`
- `docking_modeling_manifest.json`
- `docking_surrogate_sequences.fasta`
- `DOCKING_README.md`

## Docking-ready levels

- `DIRECT_LFORM_DOCKING_READY`: standard peptide docking can be used directly.
- `PARAMETERIZED_DOCKING_READY`: candidate preserves real modifications; use Rosetta/HADDOCK/MD with explicit parameters.
- `PARAMETERIZATION_HEAVY`: candidate is chemically rich; prioritize only if biologically important.
- `BLOCKED_UNSUPPORTED_TOKEN`: register/remove unknown token first.

## Important interpretation

`docking_surrogate_sequences.fasta` is only for fast pre-screening. For D-form,
non-natural residues, chemical linkers, labels, or caps, final validation should use
a parameterized model, not the surrogate sequence alone.

## Example

```bash
cd Python
python peptide_cli.py --pop 200 --gen 20 --top-n 20 --docking-ready-mode ADVANCED --max-param-tokens 8
```
