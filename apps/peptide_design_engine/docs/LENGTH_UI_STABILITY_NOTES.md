# Length / UI Stability Patch Notes

## Fixed

- FIX length mode now forces `MIN_LENGTH = MAX_LENGTH = FIX_LENGTH`.
- RANGE mode now automatically corrects `MIN_LENGTH > MAX_LENGTH`.
- Colab length sliders and number boxes are linked with `widgets.jslink`.
- FIX mode disables range controls to prevent conflicting UI values.
- RANGE mode disables the fix-length control to avoid ambiguity.
- Engine-side safety normalization is applied in `update_config()` and `length_bounds()`.

## Preserved

- Hotspot extraction
- Hotspot-output columns
- SINGLE / MULTI / BRIDGE TargetMode
- Motif and motif-position logic
- Chemistry options
- Docking-readiness export
- Optional ML and pseudo-docking
