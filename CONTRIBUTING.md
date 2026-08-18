# Contributing to Pepforge

Thanks for helping improve Pepforge.

Pepforge is scientific workflow software, so a change is not considered complete merely because the GUI opens or the code compiles. Changes should preserve existing behavior, expose failures clearly, and avoid unsupported scientific claims.

## Development rules

1. **No monkey patching as the implementation strategy.**
2. **No placeholder/stub feature presented as complete.**
3. **No fake/dummy scientific output.**
4. **No silent feature loss.**
5. **Avoid destructive refactors when a bounded fix is sufficient.**
6. **Do not invent scientific parameters.** Unsupported values must remain unsupported or explicitly estimated.
7. **Keep Windows-first operation in mind.**
8. **Preserve the lightweight workspace architecture.**

## Before changing code

- Start from the current fixed v3.0.0 baseline.
- Create a separate working copy/branch.
- Identify the real callback/dataflow behind the affected UI.
- Check nearby tests and output contracts.
- Confirm whether the change affects scientific interpretation.

## Minimum verification

For a code change, perform the relevant subset of:

```bash
python -m compileall -q .
pytest -q
```

For GUI functions, also perform an actual smoke test where feasible:

```text
button
→ callback
→ validation
→ processing
→ output/result
→ error recovery
```

Do not consider a button fixed only because its `command=` exists.

## Scientific changes

A change that introduces a new propensity, score, structural rule, or quantitative interpretation should document:

- source / paper / dataset
- exact meaning of the value
- supported residue/system scope
- units if applicable
- whether it is experimental, statistical, fitted, or estimated
- limitations / claim boundary

If no defensible parameter exists, report `unsupported` rather than fabricating one.

## Pull request notes

A useful PR description should include:

```text
Problem
Root cause
Implementation
Scientific impact
Files changed
Tests performed
Known limitations
```

## Versioning and release docs

When public behavior changes, update as appropriate:

- `README.md`
- `README_KO.md`
- `CHANGELOG.md`
- `CITATION.cff`
- release notes in `docs/`
- user manuals if workflow changes

## License

Contributions are made under the repository's existing license unless explicitly agreed otherwise.
