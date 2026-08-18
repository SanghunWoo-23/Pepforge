from __future__ import annotations

"""One-time source migration: make every top-level definition unique.

This preserves the exact historical call chain while eliminating Python's
implicit last-definition-wins behavior. It is a release-maintenance utility,
not imported by Pepforge at runtime.
"""

import ast
import io
import sys
import tokenize
from pathlib import Path


def consolidate(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    occurrences: dict[str, list[int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            occurrences.setdefault(node.name, []).append(node.lineno)
    duplicates = {name: lines for name, lines in occurrences.items() if len(lines) > 1}
    if not duplicates:
        return 0

    intervals: list[tuple[str, str, int, int]] = []
    for name, lines in duplicates.items():
        for index, start in enumerate(lines[:-1], 1):
            intervals.append((name, f"_{name}_historical_stage_{index}", start, lines[index]))

    output = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        token_type, text, start, end, line = token
        if token_type == tokenize.NAME:
            row = start[0]
            for old, new, first, stop in intervals:
                if text == old and first <= row < stop:
                    text = new
                    break
        output.append((token_type, text))
    migrated = tokenize.untokenize(output)
    migrated = migrated.replace("  # type: ignore[override]", "")
    path.write_text(migrated, encoding="utf-8")
    return sum(len(lines) - 1 for lines in duplicates.values())


if __name__ == "__main__":
    target = Path(sys.argv[1])
    print(f"consolidated={consolidate(target)} path={target}")
