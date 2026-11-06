from types import SimpleNamespace
from suite_gui import v3_menu

class FakeNotebook:
    def __init__(self, labels):
        self._labels = list(labels)
        self.selected = None
    def tabs(self):
        return list(range(len(self._labels)))
    def tab(self, tab, key):
        assert key == 'text'
        return self._labels[tab]
    def select(self, tab=None):
        if tab is not None:
            self.selected = tab
        return self.selected

def test_view_menu_aliases_select_clean_v3_labels():
    nb = FakeNotebook(['Plan','Materials','Total Materials','Checklist','Cleavage Cocktail'])
    gui = SimpleNamespace(pm_results_notebook=nb)
    for old, expected in [
        ('Selected Plan',0),('Selected Materials',1),('Selected Total Materials',2),('Selected Checklist',3),('Cleavage Cocktail',4)
    ]:
        v3_menu._select_result_tab(gui, old)
        assert nb.selected == expected
