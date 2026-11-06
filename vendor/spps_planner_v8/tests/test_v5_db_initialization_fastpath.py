from pathlib import Path
import sqlite3

from suite_gui import experimental_data


def test_experimental_db_persists_lookup_backfill_version(tmp_path):
    db = tmp_path / "experimental.db"
    experimental_data._INITIALIZED_DB_PATHS.discard(str(db.resolve()))
    out = experimental_data.initialize(db)
    assert Path(out) == db
    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT meta_value FROM experimental_meta WHERE meta_key='lookup_backfill_version'"
        ).fetchone()
    assert row is not None
    assert int(row[0]) == experimental_data._LOOKUP_BACKFILL_VERSION
    assert str(db.resolve()) in experimental_data._INITIALIZED_DB_PATHS
    # Repeated reads use the already initialized DB path rather than re-running
    # schema/backfill work.
    assert experimental_data.initialize(db) == db
    assert experimental_data.list_records("loading", db) == []
