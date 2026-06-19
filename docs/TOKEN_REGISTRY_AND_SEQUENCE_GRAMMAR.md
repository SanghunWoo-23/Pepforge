# Token Registry and Sequence Grammar

Pepforge V4 introduces a unified peptide token registry used by Structure Assist and intended as the reference layer for Design Engine and SPPS Planner integration.

Core goals:
- prevent terminal modifiers such as Ac from being confused with natural sequences such as ACDE;
- prevent C-terminal NH2/CONH2 from being counted as residues;
- prevent linker-only tokens such as PEG4 and Ahx from being decomposed into false residues;
- keep amino-acid-like tokens such as bAla, gAla, and Sar available as residue-like units;
- provide one conservative parser for N-terminal modifiers, C-terminal markers, linker-only tokens, and amino-acid-like units.

Supported examples:
- Ac-EEMQRR-NH2
- AcEEMQRR-NH2
- ACDE-NH2
- PALE-NH2
- EEMQRR-CONH2
- PEG4-EEMQRR-NH2
- Ahx-EEMQRR-NH2
- bAla-EEMQRR-NH2
- gAla-EEMQRR-NH2
- Sar-EEMQRR-NH2
