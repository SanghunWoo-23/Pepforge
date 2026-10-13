from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_shared_vertical_scroller_exists_and_is_used():
    helper=(ROOT/'peptiforg_core'/'ui_scroll.py').read_text(encoding='utf-8')
    psb=(ROOT/'suite_gui'/'pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    workflow=(ROOT/'peptiforg_core'/'workflow_gui.py').read_text(encoding='utf-8')
    assert 'class VerticalPageScroller' in helper
    assert 'VerticalPageScroller(self, shell' in psb
    assert 'VerticalPageScroller(self.root, shell' in workflow

def test_scroller_clamps_and_debounces_edge_events():
    helper=(ROOT/'peptiforg_core'/'ui_scroll.py').read_text(encoding='utf-8')
    assert '_at_edge' in helper
    assert 'after(12, self._flush_wheel)' in helper
    assert 'after(35, self._commit_region)' in helper
    assert 'bbox("all")' in helper
    assert 'itemconfigure(self.window, width=width)' in helper

def test_no_middle_button_required_for_page_scroll():
    psb=(ROOT/'suite_gui'/'pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    helper=(ROOT/'peptiforg_core'/'ui_scroll.py').read_text(encoding='utf-8')
    assert '<Button-2>' not in helper
    assert '<MouseWheel>' in helper
    assert '<Button-4>' in helper and '<Button-5>' in helper
