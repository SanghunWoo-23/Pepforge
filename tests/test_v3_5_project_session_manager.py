from pathlib import Path

from peptiforg_core.project_session_manager import (
    new_project_session,
    save_project_session,
    load_project_session,
    mark_stage,
    attach_file,
    export_session_summary,
    create_project_session_package,
)


def test_new_save_load_session(tmp_path):
    s = new_project_session("Test", tmp_path)
    s = mark_stage(s, "design_engine", "completed", files=["results_top.csv"], notes="done")
    path = save_project_session(s)
    loaded = load_project_session(path)
    assert loaded["project_name"] == "Test"
    assert loaded["stages"]["design_engine"]["status"] == "completed"


def test_attach_file_and_export_summary(tmp_path):
    s = new_project_session("Test", tmp_path)
    s = attach_file(s, "outputs", "docking_contacts", "contacts.csv")
    paths = export_session_summary(s, tmp_path)
    assert Path(paths["session_json"]).exists()
    assert Path(paths["project_stage_progress"]).exists()
    assert Path(paths["project_session_summary"]).exists()


def test_create_project_session_package(tmp_path):
    paths = create_project_session_package("Demo", tmp_path)
    assert Path(paths["session_json"]).exists()
    assert Path(paths["project_next_actions"]).exists()
