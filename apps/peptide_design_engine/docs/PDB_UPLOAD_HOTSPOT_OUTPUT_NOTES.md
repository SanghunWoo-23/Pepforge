# PDB Upload and Hotspot Output Notes

## Added

- Colab `FileUpload` widget for `.pdb`, `.ent`, or `.txt` files.
- PDB text area remains available as a fallback.
- If PDB mode is selected without PDB content, sequence fallback is used when available.

## Output columns

Top result tables and CSV files now include:

- `binding_target_hotspot`
- `peptide_to_target_hotspot`
- `all_target_hotspots_used`
- `hotspot_status`
- `target_hotspot_sequences`
- `hotspot_peptide_map`
- `best_hotspot`

## Interpretation

`binding_target_hotspot` is the target-derived hotspot most related to the generated peptide candidate.
It is a design-bias reference, not proof of binding.
