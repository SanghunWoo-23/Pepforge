# Final Length and Chemistry Semantics

## Length

Default mode: TOKEN

- TOKEN counts amino-acid residues and selected construct tokens such as linker, tag, label, and chemical tokens.
- RESIDUE counts amino-acid residues only.
- EXPANDED expands AA-linkers and known peptide tags where possible.
- NH2 is always treated as a C-terminal modification and contributes 0 to length.

## Chemistry / linker / tag / label

These features are only introduced when the corresponding UI option is enabled.

This is not HARD CHEM mode. The engine does not force every candidate to contain every selected chemistry token unless the generation operators and settings naturally include them.

## Scoring

A mild chemistry presence bonus is available to avoid unnecessarily penalizing selected chemistry/linker/tag/label features.
