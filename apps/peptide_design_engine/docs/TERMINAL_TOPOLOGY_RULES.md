# Terminal Topology Rules

Final default rules:

- Chemical / tag / label tokens are N-terminal only.
- Linkers are internal/middle only.
- Linkers are not allowed at the first construct position.
- C-terminal NH2 is a terminal modification and stays at the C-terminus.
- NH2 does not contribute to length.
- Chemical/linker/tag/label are introduced only when the corresponding option is enabled.
- `Soft-enrich selected chem` is not hard forcing; it only improves retention/ranking of selected chemistry features.

Recommended:
- Keep `Strict terminal rules` ON for paper-facing runs.
- Use `TOKEN` length mode for construct-level design.
- Use `RESIDUE` length mode for pure amino-acid mer length.
