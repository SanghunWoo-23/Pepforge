# Final Colab Hotspot Region Output Patch

## What changed

Top results now directly include the target hotspot region used as design reference:

- binding_target_hotspot_sequence
- binding_target_hotspot_start
- binding_target_hotspot_end
- binding_target_hotspot_range
- binding_target_hotspot_chain
- binding_target_hotspot_source
- binding_target_hotspot_score
- all_target_hotspot_ranges

This makes the Colab top table show not only the peptide, but also the target-derived hotspot sequence and residue range such as `A:125-132`.

## Important interpretation

This is the design-referenced hotspot region, not experimentally validated binding position.
