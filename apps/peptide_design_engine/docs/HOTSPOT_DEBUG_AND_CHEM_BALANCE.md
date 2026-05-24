# Hotspot Debug and Long-target Chemistry Balance

## Hotspot debug mode

If `AUTO_HOTSPOT` is ON but no hotspots are extracted, debug fallback can create diagnostic sequence windows.

This is intended to verify that the hotspot-to-target-to-peptide pipeline is working.

Output:

- `hotspot_debug_visualization.csv`
- `hotspot_peptide_pairs.csv`
- `hotspot_status`
- `binding_target_hotspot`
- `peptide_to_target_hotspot`

## Residue position display

`hotspot_debug_visualization.csv` includes:

- hotspot sequence
- source
- start residue
- end residue
- chain
- score
- exposure
- extraction status

## Label / chemical disappearance with long protein targets

Long protein targets can make target/hotspot scoring dominate the ranking. The engine now includes `CHEMISTRY_LONG_TARGET_BALANCE`, which raises the effective chemistry bonus for long sequence sources when selected chemistry/tag/label/linker options are enabled.

This is still not hard forcing.
