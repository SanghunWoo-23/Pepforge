# Residue Length Fix Notes

## Fixed

- `FIX_LENGTH` now means amino-acid residue length in default `RESIDUE` mode.
- `NH2` no longer reduces the requested amino-acid mer length.
- Example: `FIX_LENGTH = 12` produces 12 amino-acid residues plus optional terminal `NH2`.
- Output now includes:
  - `length`
  - `residue_length`
  - `expanded_length`
  - `token_length_sum`

## Chemistry/linker enhancement

- Added `FORCE_CHEMISTRY_TOKENS` option placeholder in config/UI.
- Added mild `CHEMISTRY_BONUS_WEIGHT` scoring term so requested chemistry/linker/tag/label is not unnecessarily disadvantaged.
- Existing chemistry, tag, label, linker, hotspot, motif, docking-ready, and analysis functions are preserved.

## Recommended setting

For paper-safe peptide mer length:

```text
LENGTH_COUNT_MODE = RESIDUE
FIX_LENGTH = desired amino-acid mer length
USE_CTERM_NH2 = True/False as desired
```
