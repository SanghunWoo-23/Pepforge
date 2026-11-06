from __future__ import annotations

import json

from suite_gui import state_persistence


def test_project_state_preserves_legacy_keys_and_copies_rows():
    item = {"project": "Demo-Project", "sequence": "Ac-AAAAAA-NH2"}
    row = {"Project": "Demo-Project", "Scale mmol": "0.2"}
    state = state_persistence.project_state(
        app_version="V3.0.0",
        saved_at="2026-07-30T12:00:00",
        selected_pm_index=1,
        active_index=1,
        pm_items=[item, "ignored"],
        batch_rows=[row, None],
        defaults={"scale": "0.2"},
    )

    assert state == {
        "app_version": "V3.0.0",
        "saved_at": "2026-07-30T12:00:00",
        "selected_pm_index": 1,
        "pm_items": [item],
        "defaults": {"scale": "0.2"},
        "batch_rows": [row],
        "active_index": 1,
    }
    assert state["pm_items"][0] is not item
    assert state["batch_rows"][0] is not row


def test_atomic_write_and_read_support_unicode_and_replace(tmp_path):
    path = tmp_path / "project_manager_state.json"
    state_persistence.atomic_write_json(path, {"project": "펩타이드", "value": 1})
    state_persistence.atomic_write_json(path, {"project": "새 프로젝트", "value": 2})

    assert state_persistence.read_json_object(path) == {
        "project": "새 프로젝트",
        "value": 2,
    }
    assert not path.with_suffix(".json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["project"] == "새 프로젝트"


def test_read_non_object_root_is_empty_state(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="top-level object"):
        state_persistence.read_json_object(path)


def test_normalize_items_migrates_saved_one_letter_aa_display_rows():
    source = [{
        "selected_plan_rows": [{"Unit name": "A"}, {"Unit name": "Ahx"}],
        "selected_material_rows": [{"material": "C", "class": "AA"}],
        "selected_total_rows": [{"material": "D"}],
        "selected_checklist_rows": [{"unit": "E"}],
    }]

    item = state_persistence.normalize_items(source)[0]

    assert item["selected_plan_rows"] == [
        {"Unit name": "Fmoc-Ala-OH"}, {"Unit name": "Ahx"},
    ]
    assert item["selected_material_rows"][0]["material"] == "Fmoc-Cys(Trt)-OH"
    assert item["selected_total_rows"][0]["material"] == "Fmoc-Asp(OtBu)-OH"
    assert item["selected_checklist_rows"][0]["unit"] == "Fmoc-Glu(OtBu)-OH"
    assert source[0]["selected_plan_rows"][0]["Unit name"] == "A"
