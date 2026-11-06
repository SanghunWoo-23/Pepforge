# SPPS Parser Contract

The parser accepts plain one-letter peptide sequences, terminal groups, and explicit modifiers without silently changing the peptide core.

## Plain and terminal forms

These examples use a synthetic sequence only:

- `GHTYKL`
- `GHTYKL-NH2`
- `-GHTYKL-NH2`
- `Ac-GHTYKL-NH2`
- `AcGHTYKL-NH2`
- `FITC-GHTYKL-NH2`
- `Biotin-GHTYKL-NH2`

Expected parsing for `GHTYKL-NH2`:

```text
nterm = ""
core = "GHTYKL"
cterm = "NH2"
core_tokens = ["G", "H", "T", "Y", "K", "L"]
```

Expected parsing for `Ac-GHTYKL-NH2`:

```text
nterm = "Ac"
core = "GHTYKL"
cterm = "NH2"
core_tokens = ["G", "H", "T", "Y", "K", "L"]
```

## Safety rules

- Plain delimiter-free FASTA chunks are split into amino-acid residues.
- Bracketed chemicals, linkers, labels, and tags remain single parser tokens.
- `Ac` compact notation is recognized only when it is unambiguous; a natural sequence beginning with `AC...` must not be converted into an acetylated peptide.
- Other N-terminal modifiers should be written explicitly with a dash.
- Protecting-group text is normalized by the planner/catalog layer; the parser must not invent a protecting group that was not selected.
