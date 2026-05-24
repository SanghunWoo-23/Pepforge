# Patch Notes v3

## Fixed

- Fixed Colab error:
  `TypeError: 'Checkbox' object is not callable`
- Cause:
  UI widget variable `trim_to_length` overwrote the engine function `trim_to_length()`.
- Fix:
  Renamed UI widget to `trim_to_length_checkbox`.

## Improved

- Length mode UI now displays:
  - `FIX`: uses `FixLen`
  - `RANGE`: samples between `MinLen` and `MaxLen`
- Colab run log now prints:
  - `RANGE: min-max`
  - `FIX: fixed length`

## Preserved

- Colab UI structure
- Python CLI
- D-form / noncanonical / linker / tag / label / chemistry support
- docking-ready classification
- optional ML reranking
- optional pseudo-docking FASTA preparation
