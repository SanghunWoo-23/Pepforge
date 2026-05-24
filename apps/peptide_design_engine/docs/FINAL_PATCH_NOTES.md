# Final Patch Notes

## Added

- Hotspot Only Mode preset in Colab UI.
- Python CLI `--preset hotspot_only`.
- Updated README.md.
- Updated MANUAL_KR.md.

## Preserved

- Existing Colab UI structure.
- Python CLI.
- Hotspot/PDB extraction.
- Motif position control.
- D-form, noncanonical, linker, tag, label, chemistry options.
- Docking-ready classification.
- Optional ML.
- Optional pseudo-docking.
- CSV/FASTA/manifest outputs.

## Meaning of Hotspot Only Mode

Hotspot-derived fragments are used as TARGETS, but not locked as motifs.

Recommended safe settings:

- AUTO_HOTSPOT = ON
- HOTSPOT_REPLACE_TARGETS = ON
- HOTSPOT_LOCK_AS_MOTIF = OFF
- MOTIF_LOCK = OFF
