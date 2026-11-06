from pathlib import Path
import sqlite3

from suite_gui import experimental_data


def test_canonical_lookup_keys_backfill_existing_rows(tmp_path):
    db = tmp_path / "exp.sqlite"
    experimental_data.initialize(db)
    load = experimental_data.add_record("loading", {
        "resin_type": "rink amide RESIN", "amino_acid_raw": "fmoc-gln(trt)-oh", "loading_rate_mmol_g": 0.4,
    }, db)
    clv = experimental_data.add_record("cleavage", {
        "product": "Synthetic Product-X(260720)", "sequence": "ac-aaaa-nh2", "tfa_ml": 95, "water_ml": 5,
    }, db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE loading_records SET resin_key='',amino_acid_key='' WHERE record_id=?", (load["record_id"],))
        con.execute("UPDATE cleavage_records SET product_key='',sequence_key='' WHERE record_id=?", (clv["record_id"],))
    experimental_data.initialize(db)
    load2 = experimental_data.list_records("loading", db)[0]
    clv2 = experimental_data.list_records("cleavage", db)[0]
    assert load2["resin_key"] == experimental_data.canonical_resin_key("Rink Amide resin")
    assert load2["amino_acid_key"] == experimental_data.canonical_amino_acid_key("Fmoc-Gln(Trt)-OH")
    assert clv2["product_key"] == experimental_data.canonical_product_key("Synthetic Product-X")
    assert clv2["sequence_key"] == experimental_data.canonical_sequence_key("AC-AAAA-NH2")


def test_experimental_connection_context_releases_handle(tmp_path):
    db = tmp_path / "handle.sqlite"
    with experimental_data._connect(db) as con:
        con.execute("CREATE TABLE handle_probe(value INTEGER)")
        con.execute("INSERT INTO handle_probe(value) VALUES (1)")
    # sqlite3's stock context manager does not close on exit.  V6 deliberately
    # does, so Windows can remove temporary preview databases deterministically.
    try:
        con.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("experimental DB connection remained open after context exit")


def test_preview_does_not_modify_target_db(tmp_path):
    csv_path = tmp_path / "loading.csv"
    csv_path.write_text("resin_type,amino_acid,loading_rate_mmol_g\nRink Amide resin,Fmoc-Gln(Trt)-OH,0.4\n", encoding="utf-8")
    db = tmp_path / "real.sqlite"
    experimental_data.initialize(db)
    preview = experimental_data.preview_path(csv_path)
    assert preview["counts"]["loading"] == 1
    assert experimental_data.list_records("loading", db) == []


def test_data_health_reports_keys_not_success_claims(tmp_path):
    db = tmp_path / "health.sqlite"
    experimental_data.initialize(db)
    experimental_data.add_record("loading", {"resin_type":"Wang resin","amino_acid_raw":"Q","loading_rate_mmol_g":0.4}, db)
    health = experimental_data.data_health(db)
    assert health["missing_canonical_keys"] == {"loading":0,"cleavage":0,"sequence":0}
    assert "loading_leave_one_out_mae_mmol_g" in health
