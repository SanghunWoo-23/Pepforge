"""Regression contract for drag-selectable PDE output presentation."""
import ast
from pathlib import Path

GUI = Path(__file__).resolve().parents[1] / 'apps' / 'peptide_design_engine' / 'Python' / 'desktop_gui.py'


def test_result_clipboard_format_is_tab_delimited_and_sanitized():
    src = GUI.read_text(encoding='utf-8')
    module = ast.parse(src)
    method = next(n for cls in module.body if isinstance(cls, ast.ClassDef)
                  for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_copyable_result_lines')
    assert method is not None
    assert '"\\t".join' in src
    assert '"\\n".join' in src


def test_result_surface_is_native_text_and_read_only():
    src = GUI.read_text(encoding='utf-8')
    assert 'self.result_text = tk.Text(' in src
    assert 'self.result_text.configure(state="disabled")' in src
    assert 'self.result_text.insert("1.0", display)' in src
    assert 'self.tree.item(item, "values")' in src
    assert 'self.result_text.bind("<ButtonRelease-1>"' in src
