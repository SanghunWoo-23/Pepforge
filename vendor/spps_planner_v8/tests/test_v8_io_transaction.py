from types import SimpleNamespace
from unittest.mock import patch
import pytest
from suite_gui import persistence_workflow as pw

class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


def test_restore_widget_failure_rolls_back_model_and_defaults():
    gui = SimpleNamespace(pm_items=[{"project": "old"}], custom_materials={"old": 1},
                          _project_id="old-id", _project_revision=4,
                          _project_change_history=[], _restoring_state=False,
                          pm_sequence=Var("OLD"))
    data = {"pm_items": [{"project": "new"}], "defaults": {"pm_sequence": "NEW"}}
    with patch.object(pw.synthesis_execution, "ensure_execution"), \
         patch.object(pw.ml_dataset, "ensure_review"), \
         patch.object(pw.data_system, "ensure_hierarchy"), \
         patch.object(pw.data_system, "sync_active_run"), \
         patch.object(pw.project_manager_workflow, "_rebuild_listbox", side_effect=RuntimeError("widget")):
        with pytest.raises(RuntimeError, match="widget"):
            pw._restore_state(gui, data)
    assert gui.pm_items == [{"project": "old"}]
    assert gui.pm_sequence.get() == "OLD"
    assert gui._project_revision == 4
    assert gui._restoring_state is False


def test_save_as_existing_refusal_preserves_file(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text('{"project":"old"}', encoding="utf-8")
    gui = SimpleNamespace(_loaded_project_path=None, _loaded_project_fingerprint="")
    with patch.object(pw.messagebox, "askyesno", return_value=False) as ask:
        assert pw.save_project_as(gui, path, show=False) is None
    ask.assert_called_once()
    assert path.read_text(encoding="utf-8") == '{"project":"old"}'


def test_invalid_batch_rows_rejected_before_mutation():
    gui = SimpleNamespace(pm_items=[{"project": "old"}])
    with patch.object(pw.synthesis_execution, "ensure_execution"), \
         patch.object(pw.ml_dataset, "ensure_review"), \
         patch.object(pw.data_system, "ensure_hierarchy"), \
         patch.object(pw.data_system, "sync_active_run"):
        with pytest.raises(ValueError, match="batch_rows"):
            pw._restore_state(gui, {"pm_items":[{"project":"new"}], "batch_rows":{}})
    assert gui.pm_items == [{"project": "old"}]
