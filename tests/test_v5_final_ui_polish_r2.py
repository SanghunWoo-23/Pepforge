from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_psb_outer_page_is_vertical_viewport_without_width_feedback():
    src = (ROOT / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    section = src[src.index("def _build(self):"):src.index("def _browse(self):")]
    assert "VerticalPageScroller(self, shell" in section
    helper = (ROOT / "peptiforg_core" / "ui_scroll.py").read_text(encoding="utf-8")
    assert 'bbox("all")' in helper
    assert "itemconfigure(self.window, width=width)" in helper
    assert "root.winfo_reqwidth()" not in section
    assert "ttk.PanedWindow(root" not in section
    assert "results_stack = ttk.Frame(root)" in section


def test_regular_mouse_wheel_scrolls_page_from_child_widgets():
    section = (ROOT / "peptiforg_core" / "ui_scroll.py").read_text(encoding="utf-8")
    assert 'bind_class(self._wheel_tag, "<MouseWheel>"' in section
    assert 'tags.insert(1, self._wheel_tag)' in section
    assert 'self.canvas.yview_scroll' in section
    assert '<Button-2>' not in section


def test_sequence_editor_remains_large_and_owns_horizontal_scroll():
    src = (ROOT / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert 'self.sequence_text = tk.Text(seq_frame, height=3, wrap="none"' in src
    assert 'seq_x = ttk.Scrollbar(seq_frame, orient="horizontal"' in src


def test_results_table_owns_horizontal_scroll_instead_of_outer_page():
    src = (ROOT / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert 'tree_x = ttk.Scrollbar(token_frame, orient="horizontal"' in src
    assert 'xscrollcommand=tree_x.set' in src
    assert 'stretch=False' in src
