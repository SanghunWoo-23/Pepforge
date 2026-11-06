import json
import pytest
from suite_gui import state_persistence, persistence_workflow


def test_invalid_json_root_rejected(tmp_path):
    file = tmp_path / "s.json"
    file.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        state_persistence.read_json_object(file)


def test_invalid_project_structure_rejected_before_gui_changes():
    class GUI:
        _restoring_state = False
        pm_items = [{"project": "existing"}]
    gui = GUI()
    with pytest.raises(ValueError, match="pm_items"):
        persistence_workflow._restore_state(gui, {"pm_items": {"bad": True}})
    assert gui.pm_items == [{"project": "existing"}]
    assert not gui._restoring_state


def test_bad_primary_preserves_good_backup(tmp_path):
    file = tmp_path / "p.json"
    state_persistence.atomic_write_json_with_backup(file, {"project": "first"})
    state_persistence.atomic_write_json_with_backup(file, {"project": "second"})
    file.write_text("{bad", encoding="utf-8")
    state_persistence.atomic_write_json_with_backup(file, {"project": "third"})
    assert json.loads(file.read_text())["project"] == "third"
    assert state_persistence.read_json_object(file.with_suffix(".json.bak"))["project"] == "first"


def test_atomic_write_no_orphan_temp(tmp_path):
    file = tmp_path / "p.json"
    state_persistence.atomic_write_json(file, {"hello": "한글"})
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))
