"""Generate a PyMOL Qt plugin for full-length modified-residue tokens.

Requires the PyMOL Qt UI; uses no chemical reinterpretation. The native
sequence row remains supported by the existing three-character alias export.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path


def export_full_token_panel(mapping_tsv, output_py, *, object_name='Pepforge_Modified'):
    source = Path(mapping_tsv)
    dest = Path(output_py)
    if not source.is_file():
        raise FileNotFoundError(source)
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        if not {'resi', 'full_chemical_token'}.issubset(reader.fieldnames or []):
            raise ValueError('Expected resi and full_chemical_token in mapping TSV')
        rows = list(reader)
    if not rows or len(rows) > 10000:
        raise ValueError('Expected 1..10000 token records')
    seen = set()
    for row in rows:
        resi, token = row['resi'].strip(), row['full_chemical_token'].strip()
        if not resi or not token or resi in seen or any(c in resi for c in '\\"\'\n\r;'):
            raise ValueError('Invalid or duplicate residue selection')
        if len(token) > 200:
            raise ValueError('Token text is too long')
        seen.add(resi)
    if not object_name or not all(c.isalnum() or c == '_' for c in object_name):
        raise ValueError('Object name must be alphanumeric/underscore')
    data = [{'resi':r['resi'].strip(), 'token':r['full_chemical_token'].strip()} for r in rows]
    code = '''"""Generated Pepforge PyMOL full chemical token panel.
Load using: run /path/to/this_file.py; pepforge_tokens
Requires PyMOL with Qt GUI.
"""
import json
from pymol import cmd
from pymol import Qt

_ROWS = json.loads(DATA_LITERAL)
_OBJECT = OBJECT_LITERAL
_WINDOW = None

def pepforge_tokens():
    global _WINDOW
    from pymol.Qt import QtWidgets
    if _WINDOW is not None:
        _WINDOW.show()
        _WINDOW.raise_()
        return _WINDOW
    widget = QtWidgets.QDialog()
    widget.setWindowTitle('Pepforge — Full Chemical Tokens')
    widget.resize(760, 220)
    layout = QtWidgets.QVBoxLayout(widget)
    label = QtWidgets.QLabel('Select a full-length D-AA / non-natural AA / linker / chemical token to highlight its structure')
    layout.addWidget(label)
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    body = QtWidgets.QWidget()
    line = QtWidgets.QHBoxLayout(body)
    for record in _ROWS:
        resi = record['resi']
        token = record['token']
        button = QtWidgets.QPushButton(f'{resi}: {token}')
        button.setToolTip(f'PyMOL residue {resi}: {token}')
        def select_residue(_checked=False, residue=resi):
            # Command arguments remain separate; only vetted resi values enter expression.
            selection = 'model ' + _OBJECT + ' and resi ' + residue
            cmd.select('pepforge_selected_token', selection)
            cmd.zoom('pepforge_selected_token', animate=0.3)
        button.clicked.connect(select_residue)
        line.addWidget(button)
    line.addStretch()
    scroll.setWidget(body)
    layout.addWidget(scroll)
    _WINDOW = widget
    widget.show()
    return widget

cmd.extend('pepforge_tokens', pepforge_tokens)
'''
    # Make the output self-contained; escaped values are never interpolated into selection expressions.
    code = code.replace('DATA_LITERAL', repr(json.dumps(data, ensure_ascii=False)))
    code = code.replace('OBJECT_LITERAL', repr(object_name))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(code, encoding='utf-8')
    return {'plugin_python':str(dest), 'token_count':len(data), 'object_name':object_name,
            'display':'Qt full-length chemical token panel; native PyMOL sequence bar still uses aliases'}
