from suite_gui import experimental_data

def test_repeated_initialize_does_not_repeat_full_migration(tmp_path):
    db=tmp_path/"perf.sqlite"
    experimental_data._INITIALIZED_DB_PATHS.clear()
    experimental_data.performance_counters(reset=True)
    experimental_data.initialize(db)
    first=experimental_data.performance_counters()
    experimental_data.initialize(db)
    second=experimental_data.performance_counters()
    assert first["full_initialize_runs"] == 1
    assert second["full_initialize_runs"] == 1
    assert second["cache_hits"] == 1
    assert second["lookup_backfills"] == first["lookup_backfills"]
