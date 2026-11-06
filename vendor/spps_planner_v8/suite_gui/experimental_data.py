"""Persistent experimental knowledge base for SPPS Planner V6.0.0.

The experimental-data layer is additive: it does not replace planner calculations.  It stores
real loading/cleavage observations, preserves raw source text, and separates
parsed records from operator-verified records before supervised training.
"""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, Iterable, Mapping
from uuid import uuid4
import zipfile


SCHEMA_VERSION = 10
STATUSES = ("parsed", "verified", "incomplete", "excluded")

_LOOKUP_BACKFILL_VERSION = 2
_INITIALIZED_DB_PATHS: set[str] = set()
_PERF_COUNTERS = {"initialize_calls": 0, "cache_hits": 0, "full_initialize_runs": 0, "lookup_backfills": 0, "legacy_merge_runs": 0, "legacy_merge_backups": 0, "legacy_merge_failures": 0}

def performance_counters(*, reset: bool = False) -> dict[str, int]:
    snapshot = dict(_PERF_COUNTERS)
    if reset:
        for key in _PERF_COUNTERS: _PERF_COUNTERS[key] = 0
    return snapshot




def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid4().hex


def default_db_path() -> Path:
    try:
        from spps_planner.user_paths import user_file
        return Path(user_file("experimental_v5.sqlite"))
    except Exception:
        from spps_planner.build_profile import FALLBACK_DOT_DIR
        return Path.home() / FALLBACK_DOT_DIR / "data" / "experimental_v5.sqlite"


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except Exception:
        return str(left.expanduser()) == str(right.expanduser())


def legacy_db_candidates(destination: str | Path | None = None) -> list[Path]:
    """Return safe same-profile historical DB locations in priority order.

    R10 deliberately does not search arbitrary disks or the other build flavor.
    The candidates are limited to paths used by older SPPS Planner user-storage
    layouts for the current Public/Private profile.  This prevents a version/path
    change from making real Loading/Cleavage history appear to disappear.
    """
    dest = Path(destination) if destination is not None else default_db_path()
    from spps_planner.build_profile import APP_FOLDER, FALLBACK_DOT_DIR, SESSION_FOLDER
    candidates: list[Path] = []
    # Older code sometimes placed the DB under an explicit data/ child while the
    # current canonical path is directly below the profile folder.
    candidates.extend([
        dest.parent / "data" / dest.name,
        dest.parent / "Data" / dest.name,
        Path.home() / FALLBACK_DOT_DIR / "data" / dest.name,
        Path.home() / FALLBACK_DOT_DIR / dest.name,
    ])
    # Windows/local profile name variants used during older Private/Public builds.
    parent = dest.parent.parent
    candidates.extend([
        parent / SESSION_FOLDER / dest.name,
        parent / SESSION_FOLDER / "data" / dest.name,
        parent / APP_FOLDER / "data" / dest.name,
    ])
    # V4 was intentionally cloned rather than edited in place.  Keep that safety
    # property while allowing a user who never opened V5/V6 to recover history.
    for base in list(candidates) + [dest]:
        candidates.append(base.with_name("experimental_v4.sqlite"))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if _same_path(candidate, dest):
            continue
        try:
            key = str(candidate.expanduser().resolve())
        except Exception:
            key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _safe_table_count(path: Path, table: str) -> int:
    try:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()
    except Exception:
        return 0


def _legacy_score(path: Path) -> tuple[int, int, int]:
    tables = ("loading_records", "cleavage_records", "synthesis_sequence_records", "cleavage_usage_records", "experimental_outcomes", "synthesis_issue_records")
    total = sum(_safe_table_count(path, table) for table in tables)
    try:
        st = path.stat()
        return total, int(st.st_mtime_ns), int(st.st_size)
    except OSError:
        return total, 0, 0


def _maybe_clone_legacy_db(destination: Path) -> Path | None:
    """Copy the richest historical same-profile DB when canonical is absent."""
    if destination.exists() or destination.name != "experimental_v5.sqlite":
        return None
    found = [p for p in legacy_db_candidates(destination) if p.is_file()]
    if not found:
        return None
    source = max(found, key=_legacy_score)
    try:
        import shutil
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return source
    except OSError:
        return None


def _legacy_source_fingerprint(source: Path) -> tuple[str, str]:
    """Return the persisted merge marker and human-readable source fingerprint."""
    stat = source.stat()
    fingerprint = f"{source.expanduser()}|{stat.st_size}|{stat.st_mtime_ns}"
    import hashlib
    marker = "legacy_merge:" + hashlib.sha256(fingerprint.encode("utf-8", "replace")).hexdigest()
    return marker, fingerprint


def _sqlite_integrity_ok(path: Path) -> tuple[bool, str]:
    """Read-only quick-check used before importing a historical user database."""
    try:
        src = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            row = src.execute("PRAGMA quick_check").fetchone()
            result = str(row[0] if row else "").strip()
            return result.lower() == "ok", result or "no result"
        finally:
            src.close()
    except Exception as exc:
        return False, str(exc)


def _legacy_has_new_primary_rows(con: sqlite3.Connection, source: Path) -> bool:
    """Return True only when a historical DB can add rows by canonical primary ID."""
    if not source.is_file():
        return False
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        table_keys = {
            "import_sources": "source_id",
            "loading_records": "record_id",
            "cleavage_records": "record_id",
            "synthesis_sequence_records": "record_id",
            "cleavage_usage_records": "record_id",
            "experimental_outcomes": "record_id",
            "synthesis_issue_records": "record_id",
            "recommendation_traces": "trace_id",
        }
        for table, key in table_keys.items():
            src_cols = {str(r[1]) for r in src.execute(f"PRAGMA table_info({table})").fetchall()}
            dst_cols = {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
            if key not in src_cols or key not in dst_cols:
                continue
            for (value,) in src.execute(f"SELECT {key} FROM {table}"):
                if value in (None, ""):
                    continue
                if con.execute(f"SELECT 1 FROM {table} WHERE {key}=? LIMIT 1", (value,)).fetchone() is None:
                    return True
        return False
    finally:
        src.close()


def backup_database(path: str | Path | None = None, *, reason: str = "manual") -> Path:
    """Create an atomic SQLite backup and return the final backup path."""
    destination = Path(path) if path else default_db_path()
    if not destination.is_file():
        raise FileNotFoundError(f"Experimental database does not exist: {destination}")
    safe_reason = re.sub(r"[^A-Za-z0-9_-]+", "_", str(reason or "manual")).strip("_") or "manual"
    backup_dir = destination.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = backup_dir / f"{destination.stem}.{safe_reason}_{stamp}_{uuid4().hex[:8]}.sqlite"
    temp = final.with_suffix(final.suffix + ".tmp")
    try:
        src = sqlite3.connect(f"file:{destination.as_posix()}?mode=ro", uri=True)
        out = sqlite3.connect(temp)
        try:
            src.backup(out)
        finally:
            out.close()
            src.close()
        temp.replace(final)
        return final
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _premerge_backup(destination: Path) -> Path | None:
    """Create a recovery point before importing rows into an existing store."""
    if not destination.is_file():
        return None
    backup = backup_database(destination, reason="pre_legacy_merge")
    _PERF_COUNTERS["legacy_merge_backups"] += 1
    return backup


def legacy_recovery_status(path: str | Path | None = None) -> dict[str, Any]:
    """Expose the last recovery/backup state without scanning user data tables."""
    destination = Path(path) if path else default_db_path()
    if not destination.is_file():
        return {"last_recovery": "", "last_error": "", "last_backup": ""}
    try:
        con = sqlite3.connect(f"file:{destination.as_posix()}?mode=ro", uri=True)
        try:
            rows = dict(con.execute(
                "SELECT meta_key,meta_value FROM experimental_meta WHERE meta_key IN "
                "('legacy_recovery:last','legacy_recovery:last_error','legacy_recovery:last_backup')"
            ).fetchall())
        finally:
            con.close()
    except Exception:
        return {"last_recovery": "", "last_error": "", "last_backup": ""}
    return {
        "last_recovery": str(rows.get("legacy_recovery:last", "") or ""),
        "last_error": str(rows.get("legacy_recovery:last_error", "") or ""),
        "last_backup": str(rows.get("legacy_recovery:last_backup", "") or ""),
    }


def _merge_legacy_database(destination: Path, source: Path, con: sqlite3.Connection, *, backup_path: Path | None = None) -> int:
    """Atomically merge compatible rows from one same-profile historical DB.

    Existing canonical rows always win.  The historical source is read-only.  A
    changed/corrupt source is never marked complete after a partial import, so a
    later launch can retry after the source is repaired.
    """
    if not source.is_file() or _same_path(source, destination):
        return 0
    try:
        marker, fingerprint = _legacy_source_fingerprint(source)
    except OSError:
        return 0
    if con.execute("SELECT 1 FROM experimental_meta WHERE meta_key=?", (marker,)).fetchone():
        return 0
    ok, integrity = _sqlite_integrity_ok(source)
    if not ok:
        _PERF_COUNTERS["legacy_merge_failures"] += 1
        con.execute(
            "INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last_error',?)",
            (f"source={source}; integrity={integrity}; at={_now()}",),
        )
        return 0
    try:
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
    except Exception as exc:
        _PERF_COUNTERS["legacy_merge_failures"] += 1
        con.execute(
            "INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last_error',?)",
            (f"source={source}; open_error={exc}; at={_now()}",),
        )
        return 0
    copied = 0
    table_order = (
        "import_sources",
        "loading_records", "cleavage_records", "synthesis_sequence_records", "cleavage_usage_records",
        "experimental_outcomes", "synthesis_issue_records", "recommendation_traces",
    )
    savepoint = "legacy_merge_source"
    try:
        con.execute(f"SAVEPOINT {savepoint}")
        for table in table_order:
            src_cols = [str(r[1]) for r in src.execute(f"PRAGMA table_info({table})").fetchall()]
            if not src_cols:
                continue
            dst_cols = [str(r[1]) for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if not dst_cols:
                continue
            cols = [c for c in src_cols if c in set(dst_cols)]
            if not cols:
                continue
            rows = src.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall()
            placeholders = ",".join("?" for _ in cols)
            sql = f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
            for row in rows:
                cur = con.execute(sql, [row[c] for c in cols])
                copied += max(int(cur.rowcount or 0), 0)
        recovery = json.dumps({
            "source": str(source), "copied": copied, "backup": str(backup_path or ""),
            "fingerprint": fingerprint, "merged_at": _now(),
        }, ensure_ascii=False, sort_keys=True)
        con.execute("INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES(?,?)", (marker, recovery))
        con.execute("INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last',?)", (recovery,))
        if backup_path:
            con.execute("INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last_backup',?)", (str(backup_path),))
        con.execute("DELETE FROM experimental_meta WHERE meta_key='legacy_recovery:last_error'")
        con.execute(f"RELEASE SAVEPOINT {savepoint}")
        _PERF_COUNTERS["legacy_merge_runs"] += 1
        return copied
    except Exception as exc:
        _PERF_COUNTERS["legacy_merge_failures"] += 1
        try:
            con.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            con.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            pass
        con.execute(
            "INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last_error',?)",
            (f"source={source}; merge_error={exc}; at={_now()}",),
        )
        return 0
    finally:
        src.close()

def _is_canonical_default_path(destination: Path) -> bool:
    try:
        return _same_path(destination, default_db_path())
    except Exception:
        return False


class _ClosingConnection(sqlite3.Connection):
    """SQLite connection whose context manager also releases the file handle.

    ``sqlite3.Connection`` commits/rolls back on ``with`` exit but does not close
    the connection.  That is easy to miss on POSIX because an open SQLite file can
    still be unlinked, but it leaves ``preview.sqlite`` locked on Windows.  All
    experimental-data connections are scoped with ``with _connect(...)`` so closing
    here preserves transaction semantics and guarantees deterministic handle release.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _connect(path: str | Path | None = None) -> sqlite3.Connection:
    destination = Path(path) if path else default_db_path()
    if _is_canonical_default_path(destination):
        _maybe_clone_legacy_db(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(destination, factory=_ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con



def canonical_product_key(value: Any) -> str:
    """Stable product lookup key while preserving the raw label separately.

    Only workbook metadata suffixes and cosmetic separators are ignored. Product
    numbers/letters remain part of the key, so distinct products are never merged.
    """
    text = str(value or "").strip().lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*:\s*\d+(?:\.\d+)?\s*(?:g\s*/\s*mol)?\.?\s*$", "", text, flags=re.I)
    text = re.sub(r"\s*:\s*$", "", text)
    text = re.sub(r"\((?:\d{6,8}|\d{2}[.]\d{2}[.]\d{2}|\d{1,3})\)\s*$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def sequence_signature(sequence: Any) -> tuple[str, tuple[str, ...], str] | None:
    """Parse a sequence into a case-insensitive identity without losing D-form."""
    text = str(sequence or "").strip()
    if not text:
        return None
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(text)
        tokens: list[str] = []
        for token in list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or []):
            raw = str(token).strip()
            if raw.lower().startswith("d") and len(raw) > 1:
                tokens.append("d" + raw[1:].upper())
            else:
                tokens.append(raw.upper())
        if not tokens:
            return None
        nterm = str(getattr(parsed, "nterm", "") or "").strip().upper()
        cterm = str(getattr(parsed, "cterm_text", "") or "").strip().upper()
        return nterm, tuple(tokens), cterm
    except Exception:
        return None


def canonical_sequence_key(sequence: Any) -> str:
    signature = sequence_signature(sequence)
    if signature:
        nterm, tokens, cterm = signature
        return "|".join([nterm, *tokens, cterm])
    text = str(sequence or "").strip()
    return re.sub(r"\s+", "", text).upper() if text else ""


def canonical_resin_key(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_resin(value)).casefold()


def canonical_amino_acid_key(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_amino_acid(value)).casefold()


def _ensure_column(con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _lookup_keys_need_backfill(con: sqlite3.Connection) -> bool:
    """Cheap integrity probe used by repeated initialize calls.

    It preserves the old repair contract for externally edited/corrupted rows
    without re-parsing every historical sequence on every read.
    """
    checks = (
        ("loading_records", "resin_key='' OR amino_acid_key=''"),
        ("cleavage_records", "product_key='' OR (sequence<>'' AND sequence_key='')"),
        ("synthesis_sequence_records", "product_key='' OR (sequence<>'' AND sequence_key='')"),
        ("cleavage_usage_records", "product_key='' OR (sequence<>'' AND sequence_key='')"),
        ("experimental_outcomes", "(product<>'' AND product_key='') OR (sequence<>'' AND sequence_key='')"),
        ("synthesis_issue_records", "(product<>'' AND product_key='') OR (sequence<>'' AND sequence_key='')"),
    )
    for table, predicate in checks:
        try:
            if con.execute(f"SELECT 1 FROM {table} WHERE {predicate} LIMIT 1").fetchone() is not None:
                return True
        except sqlite3.OperationalError:
            continue
    return False


def _backfill_lookup_keys(con: sqlite3.Connection) -> None:
    """Migrate existing DBs without changing any raw historical value."""
    _PERF_COUNTERS["lookup_backfills"] += 1
    for row in con.execute("SELECT record_id,resin_type,amino_acid_normalized,resin_key,amino_acid_key FROM loading_records").fetchall():
        resin_key = canonical_resin_key(row["resin_type"])
        aa_key = canonical_amino_acid_key(row["amino_acid_normalized"])
        if row["resin_key"] != resin_key or row["amino_acid_key"] != aa_key:
            con.execute("UPDATE loading_records SET resin_key=?,amino_acid_key=? WHERE record_id=?", (resin_key, aa_key, row["record_id"]))
    for row in con.execute("SELECT record_id,product,sequence,product_key,sequence_key FROM cleavage_records").fetchall():
        product_key = canonical_product_key(row["product"])
        sequence_key = canonical_sequence_key(row["sequence"])
        if row["product_key"] != product_key or row["sequence_key"] != sequence_key:
            con.execute("UPDATE cleavage_records SET product_key=?,sequence_key=? WHERE record_id=?", (product_key, sequence_key, row["record_id"]))
    for row in con.execute("SELECT record_id,product,sequence,product_key,sequence_key FROM synthesis_sequence_records").fetchall():
        product_key = canonical_product_key(row["product"])
        sequence_key = canonical_sequence_key(row["sequence"])
        if row["product_key"] != product_key or row["sequence_key"] != sequence_key:
            con.execute("UPDATE synthesis_sequence_records SET product_key=?,sequence_key=? WHERE record_id=?", (product_key, sequence_key, row["record_id"]))
    for table in ("cleavage_usage_records", "experimental_outcomes", "synthesis_issue_records"):
        try:
            rows = con.execute(f"SELECT record_id,product,sequence,product_key,sequence_key FROM {table}").fetchall()
        except sqlite3.OperationalError:
            rows = []
        for row in rows:
            product_key = canonical_product_key(row["product"])
            sequence_key = canonical_sequence_key(row["sequence"])
            if row["product_key"] != product_key or row["sequence_key"] != sequence_key:
                con.execute(f"UPDATE {table} SET product_key=?,sequence_key=? WHERE record_id=?", (product_key, sequence_key, row["record_id"]))

def initialize(path: str | Path | None = None) -> Path:
    """Create/migrate the experimental DB once per process and return its path.

    Older builds re-ran schema inspection and canonical-key backfill on every
    read operation. Opening Recommendations therefore repeated the same expensive
    sequence parsing several times. The schema is now initialized once per DB
    path in a running app, while a persisted migration version prevents the
    canonical-key backfill from being repeated on every application launch.
    """
    _PERF_COUNTERS["initialize_calls"] += 1
    destination = Path(path) if path else default_db_path()
    try:
        cache_key = str(destination.expanduser().resolve())
    except Exception:
        cache_key = str(destination)
    if cache_key in _INITIALIZED_DB_PATHS and destination.exists():
        _PERF_COUNTERS["cache_hits"] += 1
        # Keep initialize() as an explicit repair point for DBs edited outside the
        # normal write path, but make the common path a handful of indexed/limited
        # probes instead of a full historical sequence backfill.
        with _connect(destination) as con:
            if _lookup_keys_need_backfill(con):
                _backfill_lookup_keys(con)
        return destination
    _PERF_COUNTERS["full_initialize_runs"] += 1
    with _connect(destination) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS import_sources (
                source_id TEXT PRIMARY KEY,
                imported_at TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_path TEXT NOT NULL,
                sha256 TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS loading_records (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                date TEXT NOT NULL DEFAULT '',
                resin_type TEXT NOT NULL DEFAULT '',
                resin_key TEXT NOT NULL DEFAULT '',
                resin_note TEXT NOT NULL DEFAULT '',
                amino_acid_raw TEXT NOT NULL DEFAULT '',
                amino_acid_normalized TEXT NOT NULL DEFAULT '',
                amino_acid_key TEXT NOT NULL DEFAULT '',
                stereochemistry TEXT NOT NULL DEFAULT '',
                protecting_group TEXT NOT NULL DEFAULT '',
                aa_eq REAL,
                base TEXT NOT NULL DEFAULT '',
                base_eq REAL,
                coupling_reagent TEXT NOT NULL DEFAULT '',
                coupling_reagent_eq REAL,
                additive TEXT NOT NULL DEFAULT '',
                additive_eq REAL,
                loading_time_h REAL,
                loading_solvent TEXT NOT NULL DEFAULT '',
                capping_performed INTEGER,
                capping_method TEXT NOT NULL DEFAULT '',
                resin_sample_weight_mg REAL,
                absorbance REAL,
                loading_rate_mmol_g REAL,
                raw_note TEXT NOT NULL DEFAULT '',
                source_id TEXT,
                source_locator TEXT NOT NULL DEFAULT '',
                outlier_flag INTEGER NOT NULL DEFAULT 0,
                work_item_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES import_sources(source_id)
            );

            CREATE TABLE IF NOT EXISTS cleavage_records (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                product TEXT NOT NULL DEFAULT '',
                product_key TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                sequence_key TEXT NOT NULL DEFAULT '',
                scale_mmol REAL,
                operator TEXT NOT NULL DEFAULT '',
                tfa_ml REAL,
                tis_ml REAL,
                water_ml REAL,
                other_scavengers_json TEXT NOT NULL DEFAULT '{}',
                cleavage_eq REAL,
                cleavage_time_h REAL,
                temperature_c REAL,
                ether_ml REAL,
                ether_ratio TEXT NOT NULL DEFAULT '',
                filter_ether_ml REAL,
                filter_speed TEXT NOT NULL DEFAULT '',
                crude_g REAL,
                precipitation_good INTEGER,
                separation_problem INTEGER,
                concentration_recommended INTEGER,
                remove_tis_recommended INTEGER,
                overnight_hardening INTEGER,
                raw_observation TEXT NOT NULL DEFAULT '',
                raw_filter_note TEXT NOT NULL DEFAULT '',
                source_id TEXT,
                source_locator TEXT NOT NULL DEFAULT '',
                outlier_flag INTEGER NOT NULL DEFAULT 0,
                work_item_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES import_sources(source_id)
            );

            CREATE TABLE IF NOT EXISTS synthesis_sequence_records (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                product TEXT NOT NULL DEFAULT '',
                product_key TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                sequence_key TEXT NOT NULL DEFAULT '',
                source_file TEXT NOT NULL DEFAULT '',
                source_page TEXT NOT NULL DEFAULT '',
                source_locator TEXT NOT NULL DEFAULT '',
                row_basis TEXT NOT NULL DEFAULT '',
                raw_note TEXT NOT NULL DEFAULT '',
                source_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES import_sources(source_id)
            );

            CREATE TABLE IF NOT EXISTS cleavage_usage_records (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                product_raw TEXT NOT NULL DEFAULT '',
                product TEXT NOT NULL DEFAULT '',
                product_key TEXT NOT NULL DEFAULT '',
                sequence_raw TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                sequence_key TEXT NOT NULL DEFAULT '',
                scale_mmol REAL,
                operator TEXT NOT NULL DEFAULT '',
                manufacture_period TEXT NOT NULL DEFAULT '',
                synthesis_key TEXT NOT NULL DEFAULT '',
                record_scope TEXT NOT NULL DEFAULT 'single',
                tfa_raw TEXT NOT NULL DEFAULT '', tfa_value REAL, tfa_unit TEXT NOT NULL DEFAULT '', tfa_ml REAL, tfa_status TEXT NOT NULL DEFAULT '',
                water_raw TEXT NOT NULL DEFAULT '', water_value REAL, water_unit TEXT NOT NULL DEFAULT '', water_ml REAL, water_status TEXT NOT NULL DEFAULT '',
                tis_raw TEXT NOT NULL DEFAULT '', tis_value REAL, tis_unit TEXT NOT NULL DEFAULT '', tis_ml REAL, tis_status TEXT NOT NULL DEFAULT '',
                ether_raw TEXT NOT NULL DEFAULT '', ether_value REAL, ether_unit TEXT NOT NULL DEFAULT '', ether_ml REAL, ether_status TEXT NOT NULL DEFAULT '',
                cocktail_total_ml REAL,
                cocktail_ml_per_mmol REAL,
                ether_ml_per_mmol REAL,
                composition_pct_json TEXT NOT NULL DEFAULT '{}',
                unit_review_required INTEGER NOT NULL DEFAULT 0,
                source_file TEXT NOT NULL DEFAULT '',
                source_page TEXT NOT NULL DEFAULT '',
                source_locator TEXT NOT NULL DEFAULT '',
                raw_note TEXT NOT NULL DEFAULT '',
                source_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES import_sources(source_id)
            );

            CREATE TABLE IF NOT EXISTS experimental_outcomes (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT '',
                product TEXT NOT NULL DEFAULT '',
                product_key TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                sequence_key TEXT NOT NULL DEFAULT '',
                work_item_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                success_flag INTEGER,
                yield_percent REAL,
                purity_percent REAL,
                doubling_required INTEGER,
                observation TEXT NOT NULL DEFAULT '',
                source_id TEXT,
                source_locator TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES import_sources(source_id)
            );

            CREATE TABLE IF NOT EXISTS synthesis_issue_records (
                record_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT '',
                product TEXT NOT NULL DEFAULT '',
                product_key TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                sequence_key TEXT NOT NULL DEFAULT '',
                scale_mmol REAL,
                position INTEGER,
                residue TEXT NOT NULL DEFAULT '',
                issue_type TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'Medium',
                observation TEXT NOT NULL DEFAULT '',
                action_taken TEXT NOT NULL DEFAULT '',
                resolution TEXT NOT NULL DEFAULT 'Unknown',
                operator TEXT NOT NULL DEFAULT '',
                work_item_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                source_locator TEXT NOT NULL DEFAULT '',
                parse_confidence REAL,
                parse_status TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                detected_language TEXT NOT NULL DEFAULT '',
                planner_snapshot_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendation_traces (
                trace_id TEXT PRIMARY KEY,
                work_item_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                recommendation_type TEXT NOT NULL DEFAULT '',
                evidence_source TEXT NOT NULL DEFAULT '',
                confidence TEXT NOT NULL DEFAULT '',
                evidence_count INTEGER NOT NULL DEFAULT 0,
                recommended_condition_json TEXT NOT NULL DEFAULT '{}',
                apply_allowed INTEGER NOT NULL DEFAULT 0,
                operator_decision TEXT NOT NULL DEFAULT '',
                actual_condition_json TEXT NOT NULL DEFAULT '{}',
                final_result_links_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS experimental_meta (
                meta_key TEXT PRIMARY KEY,
                meta_value TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_loading_lookup
              ON loading_records(resin_type, amino_acid_normalized, status);
            CREATE INDEX IF NOT EXISTS idx_cleavage_lookup
              ON cleavage_records(product, status);
            CREATE INDEX IF NOT EXISTS idx_sequence_lookup
              ON synthesis_sequence_records(product, status);
            CREATE INDEX IF NOT EXISTS idx_recommendation_trace_run ON recommendation_traces(run_id, recommendation_type, created_at);
            """
        )
        _ensure_column(con, "loading_records", "resin_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "loading_records", "amino_acid_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_records", "product_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_records", "sequence_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_sequence_records", "product_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_sequence_records", "sequence_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_usage_records", "hexane_raw", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_usage_records", "hexane_value", "REAL")
        _ensure_column(con, "cleavage_usage_records", "hexane_unit", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_usage_records", "hexane_ml", "REAL")
        _ensure_column(con, "cleavage_usage_records", "hexane_status", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_usage_records", "hexane_ml_per_mmol", "REAL")
        _ensure_column(con, "loading_records", "work_item_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "loading_records", "run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_records", "work_item_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "cleavage_records", "run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "experimental_outcomes", "run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_issue_records", "run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_issue_records", "parse_confidence", "REAL")
        _ensure_column(con, "synthesis_issue_records", "parse_status", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_issue_records", "parser_version", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_issue_records", "detected_language", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(con, "synthesis_issue_records", "planner_snapshot_json", "TEXT NOT NULL DEFAULT '{}'")
        # V6 traceability/lifecycle metadata is additive. Existing ML eligibility
        # continues to use the legacy status column so migrations cannot silently
        # promote historical data into training truth.
        for table in ("loading_records", "cleavage_records", "experimental_outcomes", "synthesis_issue_records"):
            _ensure_column(con, table, "record_state", "TEXT NOT NULL DEFAULT 'draft'")
            _ensure_column(con, table, "planner_snapshot_json", "TEXT NOT NULL DEFAULT '{}'")
        for table in ("loading_records", "cleavage_records", "experimental_outcomes"):
            _ensure_column(con, table, "actual_condition_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(con, "experimental_outcomes", "crude_g", "REAL")
        con.execute("CREATE INDEX IF NOT EXISTS idx_loading_key_lookup ON loading_records(resin_key, amino_acid_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cleavage_key_lookup ON cleavage_records(product_key, sequence_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_sequence_key_lookup ON synthesis_sequence_records(product_key, sequence_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_usage_sequence_lookup ON cleavage_usage_records(product_key, sequence_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_usage_synthesis_lookup ON cleavage_usage_records(synthesis_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_outcome_lookup ON experimental_outcomes(stage, product_key, sequence_key, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_issue_lookup ON synthesis_issue_records(stage, product_key, sequence_key, status)")
        # If a previous release wrote to another same-profile user-data location,
        # merge it once into the canonical DB. This is intentionally limited to
        # the canonical default path; explicit test/operator DB overrides are not
        # allowed to absorb unrelated local history.
        if _is_canonical_default_path(destination):
            pending: list[Path] = []
            for legacy in legacy_db_candidates(destination):
                if not legacy.is_file():
                    continue
                try:
                    marker, _fingerprint = _legacy_source_fingerprint(legacy)
                except OSError:
                    continue
                if con.execute("SELECT 1 FROM experimental_meta WHERE meta_key=?", (marker,)).fetchone():
                    continue
                ok, integrity = _sqlite_integrity_ok(legacy)
                if not ok:
                    _PERF_COUNTERS["legacy_merge_failures"] += 1
                    con.execute(
                        "INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES('legacy_recovery:last_error',?)",
                        (f"source={legacy}; integrity={integrity}; at={_now()}",),
                    )
                    continue
                if _legacy_has_new_primary_rows(con, legacy):
                    pending.append(legacy)
                else:
                    # No new primary-key rows: mark this exact source revision as
                    # inspected so unchanged historical files are not rescanned.
                    con.execute(
                        "INSERT OR REPLACE INTO experimental_meta(meta_key,meta_value) VALUES(?,?)",
                        (marker, json.dumps({"source": str(legacy), "copied": 0, "backup": "", "merged_at": _now()}, sort_keys=True)),
                    )
            backup_path = _premerge_backup(destination) if pending else None
            for legacy in pending:
                _merge_legacy_database(destination, legacy, con, backup_path=backup_path)
        row = con.execute(
            "SELECT meta_value FROM experimental_meta WHERE meta_key='lookup_backfill_version'"
        ).fetchone()
        try:
            completed_version = int(row[0]) if row is not None else 0
        except Exception:
            completed_version = 0
        if completed_version < _LOOKUP_BACKFILL_VERSION or _lookup_keys_need_backfill(con):
            _backfill_lookup_keys(con)
            con.execute(
                "INSERT INTO experimental_meta(meta_key,meta_value) VALUES('lookup_backfill_version',?) "
                "ON CONFLICT(meta_key) DO UPDATE SET meta_value=excluded.meta_value",
                (str(_LOOKUP_BACKFILL_VERSION),),
            )
    _INITIALIZED_DB_PATHS.add(cache_key)
    return destination


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None

def _trim_float(value: Any) -> str:
    try:
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)



def _register_source(con: sqlite3.Connection, path: Path, kind: str, note: str = "") -> str:
    digest = _sha256(path) if path.is_file() else ""
    existing = con.execute(
        "SELECT source_id FROM import_sources WHERE sha256=? AND source_kind=?",
        (digest, kind),
    ).fetchone() if digest else None
    if existing:
        return str(existing["source_id"])
    source_id = _id()
    con.execute(
        "INSERT INTO import_sources VALUES (?,?,?,?,?,?,?)",
        (source_id, _now(), path.name, kind, str(path), digest, note),
    )
    return source_id


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "—", "–"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _volume_ml(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace(" ", "")
    if not text or text in {"-", "—", "–"}:
        return None
    # summed forms such as 800ml+300ml are common in the historical workbook
    parts = re.findall(r"(\d+(?:\.\d+)?)(ml|l)", text)
    if not parts:
        return _float(text)
    total = 0.0
    for number, unit in parts:
        total += float(number) * (1000.0 if unit == "l" else 1.0)
    return total


def _scale_mmol(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).lower().replace(" ", "")
    number = _float(text)
    if number is None:
        return None
    # Some legacy rows say ml although the report is clearly using synthesis scale.
    return number


def _eq_time(value: Any) -> tuple[float | None, float | None]:
    text = str(value or "").lower().replace(" ", "")
    eq_match = re.search(r"(\d+(?:\.\d+)?)eq", text)
    h_match = re.search(r"(\d+(?:\.\d+)?)h", text)
    return (
        float(eq_match.group(1)) if eq_match else None,
        float(h_match.group(1)) if h_match else None,
    )


def normalize_resin(value: Any) -> str:
    text = str(value or "").strip()
    low = text.lower()
    if "wang" in low:
        return "Wang resin"
    if "rink" in low and "amide" in low:
        return "Rink Amide resin"
    if "trityl" in low or "ctc" in low:
        return "Trityl/2-CTC resin"
    return text


AA_ALIASES = {
    "A": "Fmoc-Ala-OH", "R": "Fmoc-Arg(Pbf)-OH", "N": "Fmoc-Asn(Trt)-OH",
    "D": "Fmoc-Asp(OtBu)-OH", "C": "Fmoc-Cys(Trt)-OH", "Q": "Fmoc-Gln(Trt)-OH",
    "E": "Fmoc-Glu(OtBu)-OH", "G": "Fmoc-Gly-OH", "H": "Fmoc-His(Trt)-OH",
    "I": "Fmoc-Ile-OH", "L": "Fmoc-Leu-OH", "K": "Fmoc-Lys(Boc)-OH",
    "M": "Fmoc-Met-OH", "F": "Fmoc-Phe-OH", "P": "Fmoc-Pro-OH",
    "S": "Fmoc-Ser(tBu)-OH", "T": "Fmoc-Thr(tBu)-OH", "W": "Fmoc-Trp(Boc)-OH",
    "Y": "Fmoc-Tyr(tBu)-OH", "V": "Fmoc-Val-OH",
}

# Loading identity aliases intentionally preserve stereochemistry and the actual
# protected building-block identity.  Recognition can be broad enough to accept
# operator shorthand, but recommendation evidence is still restricted to the exact
# normalized resin + loaded-AA key.  In particular, D-form history never falls
# back to the corresponding L-form.
_AA_THREE_TO_ONE = {
    "ALA":"A", "ARG":"R", "ASN":"N", "ASP":"D", "CYS":"C", "GLN":"Q",
    "GLU":"E", "GLY":"G", "HIS":"H", "ILE":"I", "LEU":"L", "LYS":"K",
    "MET":"M", "PHE":"F", "PRO":"P", "SER":"S", "THR":"T", "TRP":"W",
    "TYR":"Y", "VAL":"V",
}
# Explicit D-form identities mirror the D-AA catalog and deliberately omit Gly,
# which is achiral.  Do not synthesize a fictitious "D-Gly" identity.
_D_AA_ALIASES = {
    code: canonical.replace("Fmoc-", "Fmoc-D-", 1)
    for code, canonical in AA_ALIASES.items()
    if code != "G"
}
_EMPIRICAL_LOADING_SPECIAL_ALIASES = {
    # These names are present in the Private Loading evidence / supplied UV-Vis logs.
    "cit": "Fmoc-Cit-OH", "citrulline": "Fmoc-Cit-OH",
    "hyp": "Fmoc-Hyp(tBu)-OH", "4-hyp": "Fmoc-Hyp(tBu)-OH",
    "trans-4-hyp": "Fmoc-Hyp(tBu)-OH",
    "dab": "Fmoc-Dab(Boc)-OH",
    "cys(acm)": "Fmoc-Cys(Acm)-OH",
    "aeea": "Fmoc-AEEA-OH",
    "n3-lys": "Fmoc-N3-Lys-OH", "azido-lys": "Fmoc-N3-Lys-OH",
    "homo-cys": "Fmoc-Homo-Cys(Trt)-OH", "homocys": "Fmoc-Homo-Cys(Trt)-OH",
}
_EMPIRICAL_LOADING_SPECIAL_IDENTITIES = frozenset(_EMPIRICAL_LOADING_SPECIAL_ALIASES.values())


def _aa_alias_key(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", "", text).casefold()


def normalize_amino_acid(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    compact = re.sub(r"\s+", "", text)
    low = compact.casefold()

    if len(compact) == 1 and compact.upper() in AA_ALIASES:
        return AA_ALIASES[compact.upper()]
    if compact.upper() in _AA_THREE_TO_ONE:
        return AA_ALIASES[_AA_THREE_TO_ONE[compact.upper()]]

    # Data-supported special/non-natural loading building blocks.  Keep the
    # protecting-group form that actually appears in the Loading evidence.
    special = _EMPIRICAL_LOADING_SPECIAL_ALIASES.get(low)
    if special:
        return special

    # D-form shorthand: dL, D-L, (D)L, D-Leu, (D)Leu, etc.  This only resolves
    # identity; it does NOT authorize use of L-form evidence.
    d_one = re.fullmatch(r"(?:\(d\)|d)-?([arndcqehilkmfpstwyv])", low)
    if d_one:
        return _D_AA_ALIASES[d_one.group(1).upper()]
    d_three = re.fullmatch(r"(?:\(d\)|d)-?(ala|arg|asn|asp|cys|gln|glu|his|ile|leu|lys|met|phe|pro|ser|thr|trp|tyr|val)", low)
    if d_three:
        return _D_AA_ALIASES[_AA_THREE_TO_ONE[d_three.group(1).upper()]]
    # Accept protected short names such as D-His(Trt), D-Lys(Boc), or D-Asp(OtBu).
    # The target is still the explicit Fmoc-D building block identity.
    d_protected_aliases = {
        _aa_alias_key(v.removeprefix("Fmoc-").removesuffix("-OH")): v
        for v in _D_AA_ALIASES.values()
    }
    if low in d_protected_aliases:
        return d_protected_aliases[low]

    replacements = {
        "fmoc-arg(pbf)-oh": "Fmoc-Arg(Pbf)-OH",
        "fmoc-asn(trt)-oh": "Fmoc-Asn(Trt)-OH",
        "fmoc-asp(otbu)-oh": "Fmoc-Asp(OtBu)-OH",
        "fmoc-cys(trt)-oh": "Fmoc-Cys(Trt)-OH",
        "fmoc-cys(acm)-oh": "Fmoc-Cys(Acm)-OH",
        "fmoc-gln(trt)-oh": "Fmoc-Gln(Trt)-OH",
        "fmoc-glu(otbu)-oh": "Fmoc-Glu(OtBu)-OH",
        "fmoc-his(trt)-oh": "Fmoc-His(Trt)-OH",
        "fmoc-lys(boc)-oh": "Fmoc-Lys(Boc)-OH",
        "fmoc-ser(tbu)-oh": "Fmoc-Ser(tBu)-OH",
        "fmoc-thr(tbu)-oh": "Fmoc-Thr(tBu)-OH",
        "fmoc-trp(boc)-oh": "Fmoc-Trp(Boc)-OH",
        "fmoc-tyr(tbu)-oh": "Fmoc-Tyr(tBu)-OH",
        "fmoc-hyp(tbu)-oh": "Fmoc-Hyp(tBu)-OH",
        "fmoc-trans-4-hyp-oh": "Fmoc-trans-4-Hyp-OH",
        "fmoc-cit-oh": "Fmoc-Cit-OH",
        "fmoc-dab(boc)-oh": "Fmoc-Dab(Boc)-OH",
        "fmoc-aeea-oh": "Fmoc-AEEA-OH",
        "fmoc-n3-lys-oh": "Fmoc-N3-Lys-OH",
        "fmoc-homo-cys(trt)-oh": "Fmoc-Homo-Cys(Trt)-OH",
    }
    # Canonical full Fmoc-D-* spellings are generated from the standard protected
    # L building blocks so their protection remains explicit and separate.
    replacements.update({_aa_alias_key(v): v for v in _D_AA_ALIASES.values()})
    return replacements.get(low, text)


def describe_amino_acid_identity(value: Any) -> dict[str, Any]:
    """Describe the normalized loading building-block identity without inference.

    This is presentation metadata only. Whether a recommendation is evidence-backed
    is determined later from exact resin + exact normalized-AA records. Recognition
    of an alias must never be interpreted as experimental support.
    """
    normalized = normalize_amino_acid(value)
    low = normalized.casefold()
    if not normalized:
        category = "unknown"
        origin = "unresolved"
    elif low.startswith("fmoc-d-"):
        category = "D-form"
        origin = "D-form identity"
    elif normalized in AA_ALIASES.values():
        category = "standard L/unspecified"
        origin = "standard identity"
    elif normalized in _EMPIRICAL_LOADING_SPECIAL_IDENTITIES:
        category = "non-natural / special building block"
        origin = "data-supported loading alias"
    else:
        category = "non-natural / special building block"
        origin = "literal building-block identity"
    return {
        "input": str(value or "").strip(),
        "normalized": normalized,
        "canonical_key": canonical_amino_acid_key(normalized) if normalized else "",
        "stereochemistry": "D" if low.startswith("fmoc-d-") else "L/unspecified",
        "category": category,
        "identity_origin": origin,
        "recognition_only": True,
    }


def observed_loading_amino_acid_identities(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return canonical loaded-AA identities actually present in Loading records.

    This intentionally derives the operator pick-list from observed data rather than
    exposing a speculative non-natural-AA catalog as recommendation evidence.
    """
    identities: set[str] = set()
    for row in rows:
        raw = row.get("amino_acid_normalized") or row.get("amino_acid_raw") or ""
        normalized = normalize_amino_acid(raw)
        if normalized:
            identities.add(normalized)
    return sorted(identities, key=str.casefold)


def _stereo(name: str) -> str:
    low = name.lower()
    return "D" if "fmoc-d-" in low or low.startswith("d-") else "L/unspecified"


def _protecting_group(name: str) -> str:
    match = re.search(r"\(([^)]+)\)", name)
    return match.group(1) if match else ""


def _keyword_flags(observation: str, filter_note: str = "") -> dict[str, int | None]:
    text = f"{observation}\n{filter_note}".lower()
    good_precip = any(token in text for token in ("석출 잘", "석출은 잘", "침전이 빨", "가루처럼 잘"))
    bad_precip = any(token in text for token in ("석출이 잘 안", "석출x", "침전 안", "석출 안"))
    separation_problem = any(token in text for token in ("분리가 잘 안", "상등액을 버리기 애매", "상층액을 버리기 애매", "상등액 분리 어려"))
    concentrate = any(token in text for token in ("농축 후", "농축해서", "농축후", "농축 추천"))
    remove_tis = "tis는 빼" in text or "tis 빼" in text
    hardening = any(token in text for token in ("overnight", "딱딱", "케이크처럼", "떡지"))
    return {
        "precipitation_good": 0 if bad_precip else (1 if good_precip else None),
        "separation_problem": 1 if separation_problem else 0 if "분리 잘 됨" in text else None,
        "concentration_recommended": 1 if concentrate else 0,
        "remove_tis_recommended": 1 if remove_tis else 0,
        "overnight_hardening": 1 if hardening else 0,
    }


def _crude_g(text: str) -> float | None:
    matches = re.findall(r"(?:cr(?:ude)?\s*[:=]?\s*)(\d+(?:\.\d+)?)\s*g", text, flags=re.I)
    if matches:
        return float(matches[-1])
    return None


def _insert_cleavage(
    con: sqlite3.Connection, row: Mapping[str, Any], *, semantic_seed_dedup: bool = False
) -> bool:
    existing = con.execute(
        """SELECT record_id FROM cleavage_records
           WHERE source_id=? AND source_locator=?""",
        (row.get("source_id"), row.get("source_locator", "")),
    ).fetchone()
    if existing:
        return False
    # Semantic de-duplication is intentionally restricted to the bundled historical
    # seed. General Cleavage Report imports may contain legitimate repeated runs, and
    # those repetitions are evidence that must not be collapsed merely because their
    # measured fields happen to be identical.
    if semantic_seed_dedup:
        semantic = con.execute(
            """SELECT r.record_id FROM cleavage_records r
               JOIN import_sources s ON s.source_id=r.source_id
               WHERE lower(COALESCE(s.source_name,''))='cleavage_report_seed.xlsx'
                 AND COALESCE(r.product_key,'')=COALESCE(?, '')
                 AND COALESCE(r.scale_mmol,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.cleavage_eq,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.cleavage_time_h,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.tfa_ml,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.tis_ml,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.water_ml,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.raw_observation,'')=COALESCE(?, '')
               LIMIT 1""",
            (row.get('product_key'), row.get('scale_mmol'), row.get('cleavage_eq'),
             row.get('cleavage_time_h'), row.get('tfa_ml'), row.get('tis_ml'),
             row.get('water_ml'), row.get('raw_observation')),
        ).fetchone()
        if semantic:
            return False
    keys = [
        "record_id", "status", "product", "product_key", "sequence", "sequence_key", "scale_mmol", "operator",
        "tfa_ml", "tis_ml", "water_ml", "other_scavengers_json", "cleavage_eq",
        "cleavage_time_h", "temperature_c", "ether_ml", "ether_ratio",
        "filter_ether_ml", "filter_speed", "crude_g", "precipitation_good",
        "separation_problem", "concentration_recommended", "remove_tis_recommended",
        "overnight_hardening", "raw_observation", "raw_filter_note", "source_id",
        "source_locator", "outlier_flag", "created_at", "updated_at",
    ]
    values = [row.get(key) for key in keys]
    con.execute(
        f"INSERT INTO cleavage_records ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        values,
    )
    return True


def import_cleavage_report(path: str | Path, db_path: str | Path | None = None, *, semantic_seed_dedup: bool | None = None) -> dict[str, Any]:
    from openpyxl import load_workbook
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    initialize(db_path)
    if semantic_seed_dedup is None:
        semantic_seed_dedup = source.name.casefold() == "cleavage_report_seed.xlsx"
    workbook = load_workbook(source, data_only=True, read_only=True)
    inserted = 0
    with _connect(db_path) as con:
        source_id = _register_source(con, source, "cleavage_report_xlsx")
        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            index = 0
            while index < len(rows):
                row = rows[index]
                product = str(row[0] or "").strip() if row else ""
                # A report block starts with a product row and is followed by Cleavage/TFA.
                if product and index + 1 < len(rows):
                    next_row = rows[index + 1]
                    if str(next_row[0] or "").strip().lower() == "cleavage" and str(next_row[1] or "").strip().upper() == "TFA":
                        scale = _scale_mmol(row[2] if len(row) > 2 else None)
                        operator = str(row[3] or "").strip() if len(row) > 3 else ""
                        tfa_row = next_row
                        tfa_ml = _volume_ml(tfa_row[2] if len(tfa_row) > 2 else None)
                        cleavage_eq, cleavage_time_h = _eq_time(tfa_row[3] if len(tfa_row) > 3 else None)
                        observation = str(tfa_row[4] or "").strip() if len(tfa_row) > 4 else ""
                        components: dict[str, Any] = {}
                        ether_ml = None; ether_ratio = ""; filter_ether_ml = None; filter_speed = ""; filter_note = ""
                        j = index + 2
                        while j < min(index + 8, len(rows)):
                            current = rows[j]
                            section = str(current[0] or "").strip().lower() if current else ""
                            name = str(current[1] or "").strip() if len(current) > 1 else ""
                            value = current[2] if len(current) > 2 else None
                            detail = str(current[3] or "").strip() if len(current) > 3 else ""
                            note = str(current[4] or "").strip() if len(current) > 4 else ""
                            if not any(v not in (None, "") for v in current[:5]):
                                break
                            if section == "filter":
                                filter_ether_ml = _volume_ml(value)
                                filter_speed = detail
                                filter_note = note
                            elif name.upper() == "TIS":
                                components["TIS"] = _volume_ml(value)
                            elif name.upper() in {"H2O", "WATER"}:
                                components["H2O"] = _volume_ml(value)
                            elif name.lower() == "ether":
                                ether_ml = _volume_ml(value)
                                ether_ratio = detail
                            elif name:
                                components[name] = value
                            j += 1
                        flags = _keyword_flags(observation, filter_note)
                        record = {
                            "record_id": _id(), "status": "parsed", "product": product, "product_key": canonical_product_key(product),
                            "sequence": "", "sequence_key": "", "scale_mmol": scale, "operator": operator,
                            "tfa_ml": tfa_ml, "tis_ml": components.pop("TIS", None),
                            "water_ml": components.pop("H2O", None),
                            "other_scavengers_json": json.dumps(components, ensure_ascii=False, default=str),
                            "cleavage_eq": cleavage_eq, "cleavage_time_h": cleavage_time_h,
                            "temperature_c": None, "ether_ml": ether_ml, "ether_ratio": ether_ratio,
                            "filter_ether_ml": filter_ether_ml, "filter_speed": filter_speed,
                            "crude_g": _crude_g(f"{observation}\n{filter_note}"),
                            **flags,
                            "raw_observation": observation, "raw_filter_note": filter_note,
                            "source_id": source_id, "source_locator": f"{sheet.title}!row{index + 1}",
                            "outlier_flag": 0, "created_at": _now(), "updated_at": _now(),
                        }
                        inserted += int(_insert_cleavage(con, record, semantic_seed_dedup=bool(semantic_seed_dedup)))
                        index = j
                        continue
                index += 1
    return {"kind": "cleavage", "inserted": inserted, "source": str(source)}


def _mapping_value(row: Mapping[str, Any], *names: str) -> Any:
    lookup = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def _insert_loading(
    con: sqlite3.Connection, row: Mapping[str, Any], *, semantic_seed_dedup: bool = False
) -> bool:
    existing = con.execute(
        "SELECT record_id FROM loading_records WHERE source_id=? AND source_locator=?",
        (row.get("source_id"), row.get("source_locator", "")),
    ).fetchone()
    if existing:
        return False
    # Only historical seed revisions receive semantic de-duplication. Ordinary CSV
    # imports are allowed to contain repeated experiments, including identical values.
    # Repeats are scientifically useful evidence and must remain separate records.
    if semantic_seed_dedup:
        semantic = con.execute(
            """SELECT r.record_id, r.source_locator FROM loading_records r
               JOIN import_sources s ON s.source_id=r.source_id
               WHERE lower(COALESCE(s.source_name,''))='loading_history_seed.csv'
                 AND COALESCE(r.date,'')=COALESCE(?, '')
                 AND COALESCE(r.resin_key,'')=COALESCE(?, '')
                 AND COALESCE(r.amino_acid_key,'')=COALESCE(?, '')
                 AND COALESCE(r.aa_eq,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.base_eq,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.absorbance,-999999)=COALESCE(?, -999999)
                 AND COALESCE(r.loading_rate_mmol_g,-999999)=COALESCE(?, -999999)
               LIMIT 1""",
            (row.get('date'), row.get('resin_key'), row.get('amino_acid_key'), row.get('aa_eq'),
             row.get('base_eq'), row.get('absorbance'), row.get('loading_rate_mmol_g')),
        ).fetchone()
        if semantic:
            # A later seed revision can enrich an older seed record with an explicit original-source
            # locator without changing any measured chemistry value or operator state.
            previous_locator = str(semantic["source_locator"] or "").strip()
            incoming_locator = str(row.get("source_locator") or "").strip()
            if re.fullmatch(r"row\d+", previous_locator, flags=re.I) and incoming_locator and not re.fullmatch(r"row\d+", incoming_locator, flags=re.I):
                con.execute(
                    "UPDATE loading_records SET source_locator=?, updated_at=? WHERE record_id=?",
                    (incoming_locator, _now(), semantic["record_id"]),
                )
            return False
    keys = [
        "record_id", "status", "date", "resin_type", "resin_key", "resin_note", "amino_acid_raw",
        "amino_acid_normalized", "amino_acid_key", "stereochemistry", "protecting_group", "aa_eq", "base",
        "base_eq", "coupling_reagent", "coupling_reagent_eq", "additive", "additive_eq",
        "loading_time_h", "loading_solvent", "capping_performed", "capping_method",
        "resin_sample_weight_mg", "absorbance", "loading_rate_mmol_g", "raw_note",
        "source_id", "source_locator", "outlier_flag", "created_at", "updated_at",
    ]
    con.execute(
        f"INSERT INTO loading_records ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        [row.get(key) for key in keys],
    )
    return True


def import_loading_csv(path: str | Path, db_path: str | Path | None = None, *, semantic_seed_dedup: bool | None = None) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    initialize(db_path)
    if semantic_seed_dedup is None:
        semantic_seed_dedup = source.name.casefold() == "loading_history_seed.csv"
    inserted = 0
    with source.open("r", encoding="utf-8-sig", newline="") as handle, _connect(db_path) as con:
        reader = csv.DictReader(handle)
        source_id = _register_source(con, source, "loading_csv")
        for number, raw in enumerate(reader, 2):
            aa_raw = str(_mapping_value(raw, "amino_acid", "amino_acid_raw", "aa") or "").strip()
            aa = normalize_amino_acid(_mapping_value(raw, "amino_acid_normalized") or aa_raw)
            resin_raw = _mapping_value(raw, "resin_type", "resin")
            note = str(_mapping_value(raw, "raw_note", "note", "비고") or "")
            capping_raw = _mapping_value(raw, "capping_performed", "capping")
            capping = None
            if capping_raw is not None and str(capping_raw).strip() != "":
                capping = 1 if str(capping_raw).strip().lower() in {"1", "true", "yes", "y", "있음", "약식"} else 0
            explicit_locator = str(_mapping_value(raw, "source_locator", "locator", "source_ref") or "").strip()
            source_file = str(_mapping_value(raw, "source_file", "source_image", "source_photo") or "").strip()
            if source_file and explicit_locator and source_file.casefold() not in explicit_locator.casefold():
                source_locator = f"{source_file} | {explicit_locator}"
            else:
                source_locator = explicit_locator or source_file or f"row{number}"
            resin_normalized = normalize_resin(resin_raw)
            resin_key = canonical_resin_key(resin_raw)
            base_raw = _mapping_value(raw, "base")
            # Loading base is chemistry-specific. Historical Trityl/2-CTC rows may
            # omit the explicit label while still carrying DIEA equivalents, but
            # Wang/Rink coupling-based loading must never be silently relabelled DIEA.
            if base_raw is None or str(base_raw).strip() == "":
                base_value = "DIEA" if resin_key == canonical_resin_key("Trityl/2-CTC resin") else ""
            else:
                base_value = str(base_raw).strip()
            record = {
                "record_id": _id(), "status": str(_mapping_value(raw, "status") or "parsed").lower(),
                "date": str(_mapping_value(raw, "date", "날짜") or ""),
                "resin_type": resin_normalized, "resin_key": resin_key, "resin_note": str(resin_raw or ""),
                "amino_acid_raw": aa_raw, "amino_acid_normalized": aa, "amino_acid_key": canonical_amino_acid_key(aa),
                "stereochemistry": _stereo(aa), "protecting_group": _protecting_group(aa),
                "aa_eq": _float(_mapping_value(raw, "aa_eq", "loading_aa_eq")),
                "base": base_value,
                "base_eq": _float(_mapping_value(raw, "base_eq", "diea_eq")),
                "coupling_reagent": str(_mapping_value(raw, "coupling_reagent") or ""),
                "coupling_reagent_eq": _float(_mapping_value(raw, "coupling_reagent_eq")),
                "additive": str(_mapping_value(raw, "additive") or ""),
                "additive_eq": _float(_mapping_value(raw, "additive_eq")),
                "loading_time_h": _float(_mapping_value(raw, "loading_time_h", "time_h")),
                "loading_solvent": str(_mapping_value(raw, "loading_solvent", "solvent") or ""),
                "capping_performed": capping,
                "capping_method": str(_mapping_value(raw, "capping_method") or ""),
                "resin_sample_weight_mg": _float(_mapping_value(raw, "resin_sample_weight_mg", "resin_weight_mg")),
                "absorbance": _float(_mapping_value(raw, "absorbance", "abs")),
                "loading_rate_mmol_g": _float(_mapping_value(raw, "loading_rate_mmol_g", "loading_rate")),
                "raw_note": note, "source_id": source_id, "source_locator": source_locator,
                "outlier_flag": int(str(_mapping_value(raw, "outlier_flag") or "0").strip() in {"1", "true", "True"}),
                "created_at": _now(), "updated_at": _now(),
            }
            if record["status"] not in STATUSES:
                record["status"] = "parsed"
            inserted += int(_insert_loading(con, record, semantic_seed_dedup=bool(semantic_seed_dedup)))
    flag_loading_outliers(db_path)
    return {"kind": "loading", "inserted": inserted, "source": str(source)}



_SEQUENCE_NATURAL = set("ARNDCQEGHILKMFPSTWYV")
_SEQUENCE_CORE_ALIASES = {
    "AEEA": "AEEA", "AHX": "Ahx", "CHA": "Cha", "AIB": "Aib", "NLE": "Nle",
    "ORN": "Orn", "CIT": "Cit", "HYP": "Hyp", "DAB": "Dab", "NAL": "Nal",
    "DPR": "Dpr", "BALA": "bAla", "B-ALA": "bAla", "BETAALA": "bAla",
    "GALA": "gAla", "G-ALA": "gAla", "GAMMAALA": "gAla", "GABA": "gAla",
}
_SEQUENCE_MODIFIER_ALIASES = {
    "AC": "Ac", "ACETYL": "Ac", "BOC": "Boc", "FMOC": "Fmoc", "FITC": "FITC",
    "BIOTIN": "Biotin", "FAM": "FAM", "5-FAM": "5-FAM", "6-FAM": "6-FAM",
    "TAMRA": "TAMRA", "CY3": "CY3", "CY5": "CY5", "CY7": "CY7", "PAL": "Pal",
    "MYR": "Myr", "GAL": "Gal", "NIC": "Nic", "CAF": "Caf", "DOTA": "DOTA",
    "NOTA": "NOTA", "DABCYL": "Dabcyl", "BHQ": "BHQ", "NH2": "NH2",
    "CONH2": "CONH2", "AMIDE": "AMIDE", "COOH": "COOH", "CO2H": "CO2H", "OH": "OH",
}
_SEQUENCE_WORD_AA = {
    "ALA":"A", "ARG":"R", "ASN":"N", "ASP":"D", "CYS":"C", "GLN":"Q", "GLU":"E",
    "GLY":"G", "HIS":"H", "ILE":"I", "LEU":"L", "LYS":"K", "MET":"M", "PHE":"F",
    "PRO":"P", "SER":"S", "THR":"T", "TRP":"W", "TYR":"Y", "VAL":"V",
}
_SEQUENCE_TABLE_TERMINATORS = {
    "AAS", "AA", "AMINO ACIDS", "AMINO ACID", "CHEMICALS", "DATE", "NAME", "EQ", "MW", "MMOL",
}


def _std_sequence_tokens(value: Any) -> list[str]:
    """Return conservative sequence tokens from one Check-table cell.

    A page-local STD cell may contain one residue (``E``), a D-form spelling
    (``(D)F``), or a compact pair such as ``Ac-E`` / ``Boc-W``.  Only known
    Planner vocabulary is accepted; arbitrary text is never converted into a
    sequence.
    """
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text or text.startswith("=") or len(text) > 35:
        return []
    # Cosmetic leading/trailing dashes are common for terminal markers.
    stripped = text.strip().strip("-").strip()
    compact = re.sub(r"\s+", "", stripped).upper()
    if len(compact) == 1 and compact in _SEQUENCE_NATURAL:
        return [compact]
    if re.fullmatch(r"(?i)d[ARNDCQEGHILKMFPSTWYV]", stripped):
        return ["d" + stripped[-1].upper()]
    bracket_d = re.fullmatch(r"(?i)\(D\)[- ]?([ARNDCQEGHILKMFPSTWYV])", stripped)
    if bracket_d:
        return ["d" + bracket_d.group(1).upper()]
    d_named = re.fullmatch(
        r"\(?D\)?[- ]?(ALA|ARG|ASN|ASP|CYS|GLN|GLU|GLY|HIS|ILE|LEU|LYS|MET|PHE|PRO|SER|THR|TRP|TYR|VAL)",
        compact,
    )
    if d_named:
        return ["d" + _SEQUENCE_WORD_AA[d_named.group(1)]]
    if compact in _SEQUENCE_CORE_ALIASES:
        return [_SEQUENCE_CORE_ALIASES[compact]]
    if compact in _SEQUENCE_MODIFIER_ALIASES:
        return [_SEQUENCE_MODIFIER_ALIASES[compact]]
    if re.fullmatch(r"PEG\d+", compact):
        return [compact]
    # Some real STD tables place two known tokens in one cell (e.g. Ac-E or
    # Boc-W). Split only when every sub-token is independently recognized.
    if "-" in stripped:
        parts = [part for part in stripped.split("-") if part.strip()]
        if len(parts) >= 2:
            nested: list[str] = []
            for part in parts:
                parsed = _std_sequence_tokens(part)
                if len(parsed) != 1:
                    return []
                nested.extend(parsed)
            return nested
    return []


def _std_sequence_token(value: Any) -> str | None:
    """Backward-compatible single-token helper."""
    tokens = _std_sequence_tokens(value)
    return tokens[0] if len(tokens) == 1 else None


def _std_sequence_from_values(values: list[Any], row_number: int, start_index: int, end_index: int) -> tuple[str, str] | None:
    from openpyxl.utils import get_column_letter
    tokens: list[str] = []
    coordinates: list[str] = []
    for index in range(start_index, min(end_index + 1, len(values))):
        cell_tokens = _std_sequence_tokens(values[index])
        if cell_tokens:
            tokens.extend(cell_tokens)
            coordinates.append(f"{get_column_letter(index + 1)}{row_number}")
    modifiers = set(_SEQUENCE_MODIFIER_ALIASES.values())
    structural = [token for token in tokens if token not in modifiers]
    if len(structural) < 2:
        return None
    return "-".join(tokens), ",".join(coordinates)


def extract_synthesis_sequence_records(path: str | Path, *, source_file_label: str = "") -> list[dict[str, Any]]:
    """Extract page-local STD sequences from monthly calculation workbooks.

    Contract: a page's Check table is the source of truth for that page. Repeated
    product names on later pages are separate observations, not sequence conflicts.
    Older sheets that put the product name one row below its sequence are supported
    by choosing the adjacent sequence row with the greater number of recognized tokens.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    source = Path(path)
    workbook = load_workbook(source, data_only=False, read_only=True)
    records: list[dict[str, Any]] = []
    skip_pages = {"틀", "틀2", "서식", "未完", "完", "ETC"}
    try:
        for sheet in workbook.worksheets:
            if sheet.title.strip() in skip_pages:
                continue
            max_rows = min(80, int(sheet.max_row or 80))
            max_cols = min(60, int(sheet.max_column or 60))
            matrix = [list(row) for row in sheet.iter_rows(
                min_row=1, max_row=max_rows, min_col=1, max_col=max_cols, values_only=True
            )]
            anchors: list[tuple[int, int]] = []
            for row_index, row in enumerate(matrix):
                for col_index, value in enumerate(row):
                    if isinstance(value, str) and value.strip().lower() == "check table":
                        anchors.append((row_index, col_index))
            for header_row, product_col in anchors:
                header = matrix[header_row]
                result_col = next((
                    col for col in range(product_col + 1, len(header))
                    if isinstance(header[col], str) and header[col].strip().lower() == "result"
                ), None)
                end_col = (result_col - 1) if result_col is not None else min(len(header) - 1, product_col + 28)
                started = False
                blank_streak = 0
                for row_index in range(header_row + 1, min(len(matrix), header_row + 28)):
                    row = matrix[row_index]
                    raw_product = row[product_col] if product_col < len(row) else None
                    product = raw_product.strip() if isinstance(raw_product, str) else ""
                    if product.upper() in _SEQUENCE_TABLE_TERMINATORS:
                        if started:
                            break
                        continue
                    if not product or product.startswith("="):
                        product = ""
                    same = _std_sequence_from_values(row, row_index + 1, product_col + 1, end_col)
                    previous = (
                        _std_sequence_from_values(matrix[row_index - 1], row_index, product_col + 1, end_col)
                        if row_index > header_row + 1 else None
                    )
                    chosen = None
                    row_basis = ""
                    if product:
                        candidates: list[tuple[int, int, tuple[str, str], str]] = []
                        if same:
                            candidates.append((len(same[0].split("-")), 1, same, "same-row"))
                        if previous:
                            candidates.append((len(previous[0].split("-")), 0, previous, "previous-row"))
                        if candidates:
                            candidates.sort(key=lambda value: (value[0], value[1]), reverse=True)
                            _, _, chosen, row_basis = candidates[0]
                    if product and chosen:
                        sequence, sequence_cells = chosen
                        anchor = f"{get_column_letter(product_col + 1)}{header_row + 1}"
                        product_cell = f"{get_column_letter(product_col + 1)}{row_index + 1}"
                        records.append({
                            "status": "parsed",
                            "product": product,
                            "sequence": sequence,
                            "source_file": str(source_file_label or source.name),
                            "source_page": sheet.title,
                            "source_locator": f"Check table {anchor}; product {product_cell}; sequence {sequence_cells}",
                            "row_basis": row_basis,
                            "raw_note": "Page-local STD sequence from Check table; no cross-page canonicalization.",
                        })
                        started = True
                        blank_streak = 0
                    elif started:
                        if not product and not same:
                            blank_streak += 1
                            if blank_streak >= 3:
                                break
                        else:
                            blank_streak = 0
    finally:
        workbook.close()
    return records


def _insert_sequence_record(
    con: sqlite3.Connection,
    row: Mapping[str, Any],
    *,
    replace_same_provenance: bool = False,
) -> bool:
    if replace_same_provenance:
        # Bundled page-local STD seed is regenerated from the same source
        # workbooks when the parser improves.  The sequence-cell list inside the
        # locator can legitimately change when the parser starts recognizing a
        # previously missed token, so the stable slot is workbook + page + product
        # cell (e.g. ``product A3``), not the full locator text.
        locator = str(row.get("source_locator", "") or "")
        slot_match = re.search(r"\bproduct\s+([A-Z]+\d+)\b", locator, flags=re.I)
        slot = slot_match.group(1).upper() if slot_match else ""
        existing = None
        if slot:
            candidates = con.execute(
                """SELECT record_id, source_locator FROM synthesis_sequence_records
                   WHERE source_file=? AND source_page=?""",
                (row.get("source_file", ""), row.get("source_page", "")),
            ).fetchall()
            for candidate in candidates:
                old_match = re.search(r"\bproduct\s+([A-Z]+\d+)\b", str(candidate["source_locator"] or ""), flags=re.I)
                if old_match and old_match.group(1).upper() == slot:
                    existing = candidate
                    break
        else:
            existing = con.execute(
                """SELECT record_id FROM synthesis_sequence_records
                   WHERE source_file=? AND source_page=? AND source_locator=? AND source_id=?""",
                (row.get("source_file", ""), row.get("source_page", ""), locator, row.get("source_id")),
            ).fetchone()
        if existing:
            con.execute(
                """UPDATE synthesis_sequence_records
                   SET status=?, product=?, product_key=?, sequence=?, sequence_key=?, row_basis=?, raw_note=?, source_id=?, updated_at=?
                   WHERE record_id=?""",
                (
                    row.get("status", "parsed"), row.get("product", ""), canonical_product_key(row.get("product", "")), row.get("sequence", ""), canonical_sequence_key(row.get("sequence", "")),
                    row.get("row_basis", ""), row.get("raw_note", ""), row.get("source_id"),
                    row.get("updated_at") or _now(), existing["record_id"],
                ),
            )
            return False
    existing = con.execute(
        """SELECT record_id FROM synthesis_sequence_records
           WHERE source_id=? AND source_file=? AND source_page=? AND source_locator=? AND product=? AND sequence=?""",
        (row.get("source_id"), row.get("source_file", ""), row.get("source_page", ""), row.get("source_locator", ""), row.get("product", ""), row.get("sequence", "")),
    ).fetchone()
    if existing:
        return False
    keys = [
        "record_id", "status", "product", "product_key", "sequence", "sequence_key", "source_file", "source_page", "source_locator",
        "row_basis", "raw_note", "source_id", "created_at", "updated_at",
    ]
    con.execute(
        f"INSERT INTO synthesis_sequence_records ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        [row.get(key) for key in keys],
    )
    return True


def import_synthesis_workbook(path: str | Path, db_path: str | Path | None = None, *, source_file_label: str = "") -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    initialize(db_path)
    parsed = extract_synthesis_sequence_records(source, source_file_label=source_file_label)
    inserted = 0
    with _connect(db_path) as con:
        source_id = _register_source(
            con, source, "synthesis_check_table_xlsx",
            note="Page-local Check table sequences; repeated products remain separate observations.",
        )
        for raw in parsed:
            now = _now()
            row = dict(raw)
            row["product_key"] = canonical_product_key(row.get("product", ""))
            row["sequence_key"] = canonical_sequence_key(row.get("sequence", ""))
            row.update({"record_id": _id(), "source_id": source_id, "created_at": now, "updated_at": now})
            inserted += int(_insert_sequence_record(con, row))
    return {"kind": "sequence_history", "inserted": inserted, "parsed": len(parsed), "source": str(source)}


def import_sequence_history_csv(path: str | Path, db_path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    initialize(db_path)
    inserted = 0
    with source.open("r", encoding="utf-8-sig", newline="") as handle, _connect(db_path) as con:
        reader = csv.DictReader(handle)
        source_id = _register_source(con, source, "sequence_history_csv")
        for number, raw in enumerate(reader, 2):
            product = str(_mapping_value(raw, "product", "product_key") or "").strip()
            sequence = str(_mapping_value(raw, "sequence") or "").strip()
            if not product or not sequence:
                continue
            status = str(_mapping_value(raw, "status") or "parsed").lower()
            if status not in STATUSES:
                status = "parsed"
            now = _now()
            row = {
                "record_id": _id(), "status": status, "product": product, "product_key": canonical_product_key(product), "sequence": sequence, "sequence_key": canonical_sequence_key(sequence),
                "source_file": str(_mapping_value(raw, "source_file") or source.name),
                "source_page": str(_mapping_value(raw, "source_page", "source_sheet") or ""),
                "source_locator": str(_mapping_value(raw, "source_locator") or f"row{number}"),
                "row_basis": str(_mapping_value(raw, "row_basis") or ""),
                "raw_note": str(_mapping_value(raw, "raw_note", "source_note") or ""),
                "source_id": source_id, "created_at": now, "updated_at": now,
            }
            inserted += int(_insert_sequence_record(
                con, row, replace_same_provenance=(source.name.lower() == "synthesis_sequence_history_seed.csv")
            ))
    return {"kind": "sequence_history", "inserted": inserted, "source": str(source)}

def _insert_cleavage_usage(con: sqlite3.Connection, row: Mapping[str, Any], *, replace_same_provenance: bool = False) -> bool:
    existing = con.execute(
        "SELECT record_id FROM cleavage_usage_records WHERE source_file=? AND source_page=? AND synthesis_key=?",
        (row.get("source_file", ""), row.get("source_page", ""), row.get("synthesis_key", "")),
    ).fetchone()
    if existing:
        if not replace_same_provenance:
            return False
        record_id = existing["record_id"]
        clean = dict(row); clean.pop("record_id", None); clean.pop("created_at", None)
        clean["updated_at"] = row.get("updated_at") or _now()
        assignments = ",".join(f"{key}=?" for key in clean)
        con.execute(f"UPDATE cleavage_usage_records SET {assignments} WHERE record_id=?", [*clean.values(), record_id])
        return False
    keys = list(row)
    con.execute(
        f"INSERT INTO cleavage_usage_records ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        [row[key] for key in keys],
    )
    return True


def import_cleavage_usage_workbook(path: str | Path, db_path: str | Path | None = None, *, source_file_label: str = "") -> dict[str, Any]:
    from suite_gui.material_usage import extract_cleavage_usage_workbook
    source = Path(path)
    initialize(db_path)
    parsed = extract_cleavage_usage_workbook(source, source_file_label=source_file_label)
    inserted = 0
    with _connect(db_path) as con:
        source_id = _register_source(con, source, "material_usage_xlsx", note="V5 cleavage/workup usage import; missing units remain unresolved.")
        for raw in parsed:
            now = _now(); row = dict(raw)
            row.update({"record_id": _id(), "source_id": source_id, "created_at": now, "updated_at": now})
            inserted += int(_insert_cleavage_usage(con, row))
    return {"kind": "cleavage_usage", "inserted": inserted, "parsed": len(parsed), "source": str(source)}


def import_cleavage_usage_csv(path: str | Path, db_path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path)
    initialize(db_path)
    inserted = 0; parsed_count = 0
    with source.open("r", encoding="utf-8-sig", newline="") as handle, _connect(db_path) as con:
        reader = csv.DictReader(handle)
        source_id = _register_source(con, source, "cleavage_usage_csv")
        for raw in reader:
            product = str(raw.get("product") or "").strip(); scale = _float(raw.get("scale_mmol"))
            if not product or scale is None:
                continue
            parsed_count += 1; now = _now()
            row = {key: raw.get(key) for key in raw}
            numeric_fields = {"scale_mmol","tfa_value","tfa_ml","water_value","water_ml","tis_value","tis_ml","ether_value","ether_ml","hexane_value","hexane_ml","cocktail_total_ml","cocktail_ml_per_mmol","ether_ml_per_mmol","hexane_ml_per_mmol"}
            for key in numeric_fields:
                row[key] = _float(row.get(key))
            row["unit_review_required"] = int(_float(row.get("unit_review_required")) or 0)
            row["status"] = str(row.get("status") or "parsed").lower(); row["status"] = row["status"] if row["status"] in STATUSES else "parsed"
            row["product_key"] = canonical_product_key(product); row["sequence_key"] = canonical_sequence_key(row.get("sequence", ""))
            row.update({"record_id": _id(), "source_id": source_id, "created_at": now, "updated_at": now})
            allowed = {r[1] for r in con.execute("PRAGMA table_info(cleavage_usage_records)").fetchall()}
            row = {k:v for k,v in row.items() if k in allowed}
            inserted += int(_insert_cleavage_usage(con, row, replace_same_provenance=(source.name.lower()=="cleavage_usage_seed.csv")))
    return {"kind":"cleavage_usage","inserted":inserted,"parsed":parsed_count,"source":str(source)}


def add_outcome(values: Mapping[str, Any], db_path: str | Path | None = None, *, status: str = "verified") -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    initialize(db_path); now = _now()
    row = {
        "record_id": _id(), "status": status, "stage": str(values.get("stage") or "").strip().lower(),
        "product": str(values.get("product") or "").strip(), "sequence": str(values.get("sequence") or "").strip(),
        "work_item_id": str(values.get("work_item_id") or "").strip(), "run_id": str(values.get("run_id") or "").strip(), "result": str(values.get("result") or "").strip(),
        "success_flag": values.get("success_flag"), "yield_percent": _float(values.get("yield_percent")),
        "purity_percent": _float(values.get("purity_percent")), "doubling_required": values.get("doubling_required"),
        "crude_g": _float(values.get("crude_g")),
        "observation": str(values.get("observation") or "").strip(), "source_id": values.get("source_id"),
        "source_locator": str(values.get("source_locator") or "").strip(),
        "record_state": str(values.get("record_state") or ("verified" if status == "verified" else "excluded" if status == "excluded" else "draft")).strip().lower(),
        "planner_snapshot_json": str(values.get("planner_snapshot_json") or "{}").strip() or "{}",
        "actual_condition_json": str(values.get("actual_condition_json") or "{}").strip() or "{}",
        "created_at": now, "updated_at": now,
    }
    row["product_key"] = canonical_product_key(row["product"]); row["sequence_key"] = canonical_sequence_key(row["sequence"])
    with _connect(db_path) as con:
        keys=list(row); con.execute(f"INSERT INTO experimental_outcomes ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [row[k] for k in keys])
        saved=con.execute("SELECT * FROM experimental_outcomes WHERE record_id=?",(row["record_id"],)).fetchone()
    return dict(saved)


def add_issue(values: Mapping[str, Any], db_path: str | Path | None = None, *, status: str = "verified") -> dict[str, Any]:
    """Store one structured synthesis issue without converting free text into guessed chemistry.

    Issue records are evidence for risk review. They do not directly modify Planner
    conditions and are not automatically treated as synthesis failures.
    """
    if status not in STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    initialize(db_path); now = _now()
    stage = str(values.get("stage") or "Other").strip()
    severity = str(values.get("severity") or "Medium").strip().title()
    if severity not in {"Low", "Medium", "High", "Critical"}:
        severity = "Medium"
    resolution = str(values.get("resolution") or "Unknown").strip().title()
    if resolution not in {"Resolved", "Improved", "Not Resolved", "Unknown"}:
        resolution = "Unknown"
    position = _float(values.get("position"))
    row = {
        "record_id": _id(), "status": status, "recorded_at": str(values.get("recorded_at") or now).strip(),
        "stage": stage, "product": str(values.get("product") or "").strip(),
        "sequence": str(values.get("sequence") or "").strip(), "scale_mmol": _float(values.get("scale_mmol")),
        "position": int(position) if position is not None else None, "residue": str(values.get("residue") or "").strip(),
        "issue_type": str(values.get("issue_type") or "Other").strip(), "severity": severity,
        "observation": str(values.get("observation") or "").strip(),
        "action_taken": str(values.get("action_taken") or "").strip(), "resolution": resolution,
        "operator": str(values.get("operator") or "").strip(), "work_item_id": str(values.get("work_item_id") or "").strip(),
        "run_id": str(values.get("run_id") or "").strip(), "source_locator": str(values.get("source_locator") or "Record Issue dialog").strip(),
        "parse_confidence": _float(values.get("parse_confidence")),
        "parse_status": str(values.get("parse_status") or "").strip(),
        "parser_version": str(values.get("parser_version") or "").strip(),
        "detected_language": str(values.get("detected_language") or "").strip(),
        "planner_snapshot_json": str(values.get("planner_snapshot_json") or "{}").strip() or "{}",
        "record_state": str(values.get("record_state") or ("verified" if status == "verified" else "excluded" if status == "excluded" else "draft")).strip().lower(),
        "created_at": now, "updated_at": now,
    }
    row["product_key"] = canonical_product_key(row["product"]); row["sequence_key"] = canonical_sequence_key(row["sequence"])
    with _connect(db_path) as con:
        keys=list(row); con.execute(f"INSERT INTO synthesis_issue_records ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [row[k] for k in keys])
        saved=con.execute("SELECT * FROM synthesis_issue_records WHERE record_id=?",(row["record_id"],)).fetchone()
    return dict(saved)


def review_cleavage_usage_units(record_id: str, units: Mapping[str, str], db_path: str | Path | None = None) -> dict[str, Any]:
    from suite_gui.material_usage import apply_unit_review
    initialize(db_path)
    with _connect(db_path) as con:
        found=con.execute("SELECT * FROM cleavage_usage_records WHERE record_id=?",(record_id,)).fetchone()
        if not found: raise ValueError("Cleavage usage record was not found.")
        changes=apply_unit_review(dict(found),units); changes["updated_at"]=_now()
        if changes.get("unit_review_required") == 0:
            changes["status"]="verified"
        assignments=",".join(f"{key}=?" for key in changes)
        con.execute(f"UPDATE cleavage_usage_records SET {assignments} WHERE record_id=?",[*changes.values(),record_id])
        row=con.execute("SELECT * FROM cleavage_usage_records WHERE record_id=?",(record_id,)).fetchone()
    return dict(row)


def import_path(path: str | Path, db_path: str | Path | None = None, *, source_label: str = "") -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        try:
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                header = {str(value or "").strip().lower() for value in next(csv.reader(handle), [])}
        except Exception:
            header = set()
        if "synthesis_key" in header and ("tfa_raw" in header or "cocktail_ml_per_mmol" in header):
            return [import_cleavage_usage_csv(source, db_path)]
        if {"product", "sequence"}.issubset(header) or {"product_key", "sequence"}.issubset(header):
            return [import_sequence_history_csv(source, db_path)]
        return [import_loading_csv(source, db_path)]
    if suffix in {".xlsx", ".xlsm"}:
        # Cleavage Report remains a dedicated stable schema. Monthly calculation
        # workbooks are parsed only through page-local Check tables; no other cells
        # are guessed into experimental records.
        try:
            from openpyxl import load_workbook
            wb = load_workbook(source, data_only=True, read_only=True)
            first = wb[wb.sheetnames[0]]
            first_values = [str(cell.value or "") for row in first.iter_rows(min_row=1, max_row=10) for cell in row]
            looks_like_cleavage = any("Cleavage" in value for value in first_values) and any("TFA" in value for value in first_values)
            wb.close()
        except Exception:
            looks_like_cleavage = False
        try:
            from suite_gui.material_usage import extract_cleavage_usage_workbook
            material_rows = extract_cleavage_usage_workbook(source, source_file_label=source_label)
        except Exception:
            material_rows = []
        if material_rows:
            return [import_cleavage_usage_workbook(source, db_path, source_file_label=source_label)]
        if looks_like_cleavage:
            return [import_cleavage_report(source, db_path)]
        parsed = import_synthesis_workbook(source, db_path, source_file_label=source_label)
        if int(parsed.get("parsed", 0)) > 0:
            return [parsed]
        initialize(db_path)
        with _connect(db_path) as con:
            _register_source(con, source, "historical_workbook", note="No supported Cleavage Report or page-local Check table was found; no guessed rows were created.")
        return [{"kind": "registered_workbook", "inserted": 0, "source": str(source)}]
    if suffix == ".zip":
        results: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="spps_import_") as temp:
            with zipfile.ZipFile(source) as archive:
                infos = [info for info in archive.infolist() if not info.is_dir()]
                material_archive = sum(1 for info in infos if "원재료 관리대장" in Path(info.filename).name and not Path(info.filename).name.startswith("~$")) >= 5
                for info in infos:
                    name = Path(info.filename)
                    if name.name.startswith("~$") or name.suffix.lower() not in {".xlsx", ".xlsm", ".csv"}:
                        continue
                    if material_archive and "원재료 관리대장" not in name.name:
                        continue
                    safe = Path(temp) / f"{len(results):04d}_{name.name}"
                    safe.write_bytes(archive.read(info))
                    if material_archive and name.suffix.lower() in {".xlsx", ".xlsm"}:
                        try:
                            parsed = import_cleavage_usage_workbook(safe, db_path, source_file_label=name.as_posix())
                            if int(parsed.get("parsed", 0)) > 0:
                                results.append(parsed); continue
                        except Exception:
                            pass
                    results.extend(import_path(safe, db_path, source_label=name.as_posix()))
        return results
    raise ValueError(f"Unsupported experimental data file: {source.suffix}")



def set_record_state(kind: str, record_ids: Iterable[str], record_state: str, db_path: str | Path | None = None) -> int:
    """Set the V6 lifecycle state without changing ML eligibility status."""
    from suite_gui.decision_support import RECORD_STATES
    state = str(record_state or "").strip().lower()
    if state not in RECORD_STATES:
        raise ValueError(f"Unsupported record_state: {record_state}")
    table = {
        "loading": "loading_records", "cleavage": "cleavage_records",
        "outcome": "experimental_outcomes", "issue": "synthesis_issue_records",
    }.get(kind)
    if table is None:
        raise ValueError("kind must be loading, cleavage, outcome, or issue")
    ids = [str(value) for value in record_ids if str(value)]
    if not ids:
        return 0
    initialize(db_path)
    with _connect(db_path) as con:
        cur = con.execute(
            f"UPDATE {table} SET record_state=?, updated_at=? WHERE record_id IN ({','.join('?' for _ in ids)})",
            [state, _now(), *ids],
        )
        return int(cur.rowcount)


def v6_analytics(db_path: str | Path | None = None) -> dict[str, Any]:
    from suite_gui.experimental_reporting import v6_analytics as report
    return report(db_path)


def quality_findings(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    from suite_gui.experimental_reporting import quality_findings as report
    return report(db_path)


def data_health(db_path: str | Path | None = None) -> dict[str, Any]:
    from suite_gui.experimental_reporting import data_health as report
    return report(db_path)

def preview_path(path: str | Path) -> dict[str, Any]:
    """Parse an import into an isolated temporary DB and return an audit preview.

    The user's real DB is not modified. The exact same import code is exercised, so
    the preview reflects what will actually be stored instead of a second guessed parser.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    with tempfile.TemporaryDirectory(prefix="spps_preview_") as temp:
        preview_db = Path(temp) / "preview.sqlite"
        results = import_path(source, preview_db)
        loading = list_records("loading", preview_db)
        cleavage = list_records("cleavage", preview_db)
        sequence = list_records("sequence", preview_db)
        usage = list_records("cleavage_usage", preview_db)
        outcomes = list_records("outcome", preview_db)
        warnings: list[str] = []
        registered = sum(1 for row in results if row.get("kind") == "registered_workbook")
        if registered:
            warnings.append(f"{registered} workbook(s) had no supported structured layout; no guessed records will be created.")
        if source.suffix.lower() in {".xlsx", ".xlsm", ".zip"} and not sequence and not cleavage and not usage:
            warnings.append("No page-local STD sequence, Cleavage Report, or material-usage record was recognized.")
        unresolved_units = sum(int(row.get("unit_review_required") or 0) for row in usage)
        if unresolved_units:
            warnings.append(f"{unresolved_units} cleavage-usage record(s) contain unitless/unparsed amounts and are excluded from normalized volume learning until reviewed.")
        samples: list[dict[str, Any]] = []
        for row in sequence[:250]:
            samples.append({
                "kind": "Sequence STD", "status": row.get("status", ""), "product": row.get("product", ""),
                "sequence": row.get("sequence", ""), "source": row.get("source_file", ""),
                "locator": row.get("source_locator", ""),
            })
        for row in cleavage[:100]:
            samples.append({
                "kind": "Cleavage", "status": row.get("status", ""), "product": row.get("product", ""),
                "sequence": row.get("sequence", ""), "source": row.get("source_locator", ""),
                "locator": f"eq={row.get('cleavage_eq','')} / time={row.get('cleavage_time_h','')}",
            })
        for row in loading[:100]:
            samples.append({
                "kind": "Loading", "status": row.get("status", ""), "product": row.get("resin_type", ""),
                "sequence": row.get("amino_acid_normalized", ""), "source": row.get("source_locator", ""),
                "locator": f"loading={row.get('loading_rate_mmol_g','')}",
            })
        for row in usage[:150]:
            samples.append({
                "kind": "Cleavage Usage", "status": row.get("status", ""), "product": row.get("product", ""),
                "sequence": row.get("sequence", ""), "source": row.get("source_file", ""),
                "locator": f"scale={row.get('scale_mmol','')} / cocktail={row.get('cocktail_total_ml','')} mL / unit_review={row.get('unit_review_required',0)}",
            })
        return {
            "source": str(source), "results": results,
            "counts": {"loading": len(loading), "cleavage": len(cleavage), "sequence": len(sequence), "cleavage_usage": len(usage), "outcome": len(outcomes)},
            "registered_workbooks": registered, "warnings": warnings, "samples": samples,
        }


def record_counts(db_path: str | Path | None = None) -> dict[str, int]:
    """Return indexed/table counts without materializing full history rows."""
    initialize(db_path)
    tables = {
        "loading": "loading_records",
        "cleavage": "cleavage_records",
        "sequence": "synthesis_sequence_records",
        "cleavage_usage": "cleavage_usage_records",
        "outcome": "experimental_outcomes",
        "issue": "synthesis_issue_records",
        "recommendation_trace": "recommendation_traces",
    }
    counts: dict[str, int] = {}
    with _connect(db_path) as con:
        for key, table in tables.items():
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[key] = int(row[0]) if row else 0
    return counts


def list_records(kind: str, db_path: str | Path | None = None, *, statuses: Iterable[str] | None = None) -> list[dict[str, Any]]:
    initialize(db_path)
    table = {
        "loading": "loading_records", "cleavage": "cleavage_records", "sequence": "synthesis_sequence_records",
        "cleavage_usage": "cleavage_usage_records", "outcome": "experimental_outcomes", "issue": "synthesis_issue_records",
    }.get(kind)
    if table is None:
        raise ValueError("kind must be loading, cleavage, sequence, cleavage_usage, outcome, or issue")
    clauses = ""
    params: list[Any] = []
    if statuses:
        values = [value for value in statuses if value in STATUSES]
        if values:
            clauses = f" WHERE status IN ({','.join('?' for _ in values)})"
            params.extend(values)
    with _connect(db_path) as con:
        rows = con.execute(f"SELECT * FROM {table}{clauses} ORDER BY created_at, record_id", params).fetchall()
    return [dict(row) for row in rows]


def set_status(kind: str, record_ids: Iterable[str], status: str, db_path: str | Path | None = None) -> int:
    if status not in STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    table = {
        "loading": "loading_records", "cleavage": "cleavage_records", "sequence": "synthesis_sequence_records",
        "cleavage_usage": "cleavage_usage_records", "outcome": "experimental_outcomes", "issue": "synthesis_issue_records",
    }.get(kind)
    if table is None:
        raise ValueError("kind must be loading, cleavage, sequence, cleavage_usage, outcome, or issue")
    ids = [str(value) for value in record_ids if str(value)]
    if not ids:
        return 0
    with _connect(db_path) as con:
        columns={str(row[1]) for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if "record_state" in columns and status in {"verified","excluded"}:
            cur = con.execute(
                f"UPDATE {table} SET status=?, record_state=?, updated_at=? WHERE record_id IN ({','.join('?' for _ in ids)})",
                [status, status, _now(), *ids],
            )
        else:
            cur = con.execute(
                f"UPDATE {table} SET status=?, updated_at=? WHERE record_id IN ({','.join('?' for _ in ids)})",
                [status, _now(), *ids],
            )
        return int(cur.rowcount)



def update_record(kind: str, record_id: str, changes: Mapping[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    table = "loading_records" if kind == "loading" else "cleavage_records" if kind == "cleavage" else None
    if table is None:
        raise ValueError("kind must be loading or cleavage")
    editable = {
        "loading": {"status", "date", "resin_type", "resin_note", "amino_acid_raw", "amino_acid_normalized", "aa_eq", "base", "base_eq", "coupling_reagent", "coupling_reagent_eq", "additive", "additive_eq", "loading_time_h", "loading_solvent", "capping_performed", "capping_method", "resin_sample_weight_mg", "absorbance", "loading_rate_mmol_g", "raw_note", "outlier_flag"},
        "cleavage": {"status", "product", "sequence", "scale_mmol", "operator", "tfa_ml", "tis_ml", "water_ml", "other_scavengers_json", "cleavage_eq", "cleavage_time_h", "temperature_c", "ether_ml", "ether_ratio", "filter_ether_ml", "filter_speed", "crude_g", "precipitation_good", "separation_problem", "concentration_recommended", "remove_tis_recommended", "overnight_hardening", "raw_observation", "raw_filter_note", "outlier_flag"},
    }[kind]
    clean = {str(key): value for key, value in changes.items() if str(key) in editable}
    if "status" in clean and clean["status"] not in STATUSES:
        raise ValueError(f"Unsupported status: {clean['status']}")
    if not clean:
        raise ValueError("No editable fields were supplied.")
    if kind == "loading":
        if "resin_type" in clean:
            clean["resin_type"] = normalize_resin(clean["resin_type"])
            clean["resin_key"] = canonical_resin_key(clean["resin_type"])
        if "amino_acid_raw" in clean or "amino_acid_normalized" in clean:
            raw_aa = clean.get("amino_acid_normalized") or clean.get("amino_acid_raw") or ""
            clean["amino_acid_normalized"] = normalize_amino_acid(raw_aa)
            clean["amino_acid_key"] = canonical_amino_acid_key(clean["amino_acid_normalized"])
    else:
        if "product" in clean:
            clean["product_key"] = canonical_product_key(clean["product"])
        if "sequence" in clean:
            clean["sequence_key"] = canonical_sequence_key(clean["sequence"])
    clean["updated_at"] = _now()
    with _connect(db_path) as con:
        found = con.execute(f"SELECT record_id FROM {table} WHERE record_id=?", (record_id,)).fetchone()
        if not found:
            raise ValueError("Experimental record was not found.")
        assignments = ",".join(f"{key}=?" for key in clean)
        con.execute(f"UPDATE {table} SET {assignments} WHERE record_id=?", [*clean.values(), record_id])
        row = con.execute(f"SELECT * FROM {table} WHERE record_id=?", (record_id,)).fetchone()
    return dict(row)


def add_record(kind: str, values: Mapping[str, Any], db_path: str | Path | None = None, *, status: str = "verified") -> dict[str, Any]:
    """Insert one operator-entered experimental record without fabricating missing values.

    V5 additionally allows direct operator creation of cleavage_usage rows when the
    user records observed or theoretical cleavage/workup amounts.
    """
    if status not in STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    initialize(db_path)
    table = {
        "loading": "loading_records",
        "cleavage": "cleavage_records",
        "cleavage_usage": "cleavage_usage_records",
    }.get(kind)
    if table is None:
        raise ValueError("kind must be loading, cleavage, or cleavage_usage")
    editable = {
        "loading": {"date", "resin_type", "resin_note", "amino_acid_raw", "amino_acid_normalized", "stereochemistry", "protecting_group", "aa_eq", "base", "base_eq", "coupling_reagent", "coupling_reagent_eq", "additive", "additive_eq", "loading_time_h", "loading_solvent", "capping_performed", "capping_method", "resin_sample_weight_mg", "absorbance", "loading_rate_mmol_g", "raw_note", "outlier_flag", "work_item_id", "run_id", "record_state", "planner_snapshot_json", "actual_condition_json"},
        "cleavage": {"product", "sequence", "scale_mmol", "operator", "tfa_ml", "tis_ml", "water_ml", "other_scavengers_json", "cleavage_eq", "cleavage_time_h", "temperature_c", "ether_ml", "ether_ratio", "filter_ether_ml", "filter_speed", "crude_g", "precipitation_good", "separation_problem", "concentration_recommended", "remove_tis_recommended", "overnight_hardening", "raw_observation", "raw_filter_note", "outlier_flag", "work_item_id", "run_id", "record_state", "planner_snapshot_json", "actual_condition_json"},
        "cleavage_usage": {"product_raw", "product", "sequence_raw", "sequence", "scale_mmol", "operator", "manufacture_period", "synthesis_key", "record_scope", "tfa_raw", "tfa_value", "tfa_unit", "tfa_ml", "tfa_status", "water_raw", "water_value", "water_unit", "water_ml", "water_status", "tis_raw", "tis_value", "tis_unit", "tis_ml", "tis_status", "ether_raw", "ether_value", "ether_unit", "ether_ml", "ether_status", "hexane_raw", "hexane_value", "hexane_unit", "hexane_ml", "hexane_status", "cocktail_total_ml", "cocktail_ml_per_mmol", "ether_ml_per_mmol", "hexane_ml_per_mmol", "composition_pct_json", "unit_review_required", "source_file", "source_page", "source_locator", "raw_note"},
    }[kind]
    now = _now()
    row = {str(k): v for k, v in values.items() if str(k) in editable}
    row.update({"record_id": _id(), "status": status, "created_at": now, "updated_at": now})
    if kind in {"loading", "cleavage"}:
        row.setdefault("record_state", "verified" if status == "verified" else "excluded" if status == "excluded" else "draft")
        row.setdefault("planner_snapshot_json", "{}")
        row.setdefault("actual_condition_json", "{}")
    if kind == "loading":
        raw = str(row.get("amino_acid_raw") or row.get("amino_acid_normalized") or "").strip()
        if raw and not row.get("amino_acid_normalized"):
            row["amino_acid_normalized"] = normalize_amino_acid(raw)
        name = str(row.get("amino_acid_normalized") or raw)
        row.setdefault("stereochemistry", _stereo(name))
        row.setdefault("protecting_group", _protecting_group(name))
        if row.get("resin_type"):
            row["resin_type"] = normalize_resin(row["resin_type"])
        row["resin_key"] = canonical_resin_key(row.get("resin_type", ""))
        row["amino_acid_key"] = canonical_amino_acid_key(row.get("amino_acid_normalized") or raw)
    elif kind == "cleavage":
        row["product_key"] = canonical_product_key(row.get("product", ""))
        row["sequence_key"] = canonical_sequence_key(row.get("sequence", ""))
    else:
        product = str(row.get("product") or row.get("product_raw") or "").strip()
        sequence = str(row.get("sequence") or row.get("sequence_raw") or "").strip()
        row["product"] = product
        row["product_raw"] = str(row.get("product_raw") or product)
        row["product_key"] = canonical_product_key(product)
        row["sequence"] = sequence
        row["sequence_raw"] = str(row.get("sequence_raw") or sequence)
        row["sequence_key"] = canonical_sequence_key(sequence)
        row.setdefault("record_scope", "single")
        scale = _safe_float(row.get("scale_mmol"))
        tfa = _safe_float(row.get("tfa_ml"))
        water = _safe_float(row.get("water_ml"))
        tis = _safe_float(row.get("tis_ml"))
        ether = _safe_float(row.get("ether_ml"))
        hexane = _safe_float(row.get("hexane_ml"))
        def _fill_component(prefix: str, value: float | None):
            if value is None:
                row.setdefault(f"{prefix}_raw", "")
                row.setdefault(f"{prefix}_status", "")
                row.setdefault(f"{prefix}_unit", "")
            else:
                row[f"{prefix}_raw"] = str(row.get(f"{prefix}_raw") or _trim_float(value))
                row[f"{prefix}_value"] = value
                row[f"{prefix}_unit"] = str(row.get(f"{prefix}_unit") or "mL")
                row[f"{prefix}_ml"] = value
                row[f"{prefix}_status"] = str(row.get(f"{prefix}_status") or "parsed")
        for prefix, value in (("tfa", tfa), ("water", water), ("tis", tis), ("ether", ether), ("hexane", hexane)):
            _fill_component(prefix, value)
        total = row.get("cocktail_total_ml")
        total = _safe_float(total)
        if total is None:
            total = sum(v or 0.0 for v in (tfa, water, tis)) or None
        row["cocktail_total_ml"] = total
        if scale and total is not None:
            row["cocktail_ml_per_mmol"] = total / scale
        if scale and ether is not None:
            row["ether_ml_per_mmol"] = ether / scale
        if scale and hexane is not None:
            row["hexane_ml_per_mmol"] = hexane / scale
        if not row.get("composition_pct_json"):
            basis = sum(v or 0.0 for v in (tfa, water, tis))
            comp = {}
            if basis > 0:
                if tfa: comp["TFA"] = (tfa / basis) * 100.0
                if water: comp["Water"] = (water / basis) * 100.0
                if tis: comp["TIS"] = (tis / basis) * 100.0
            row["composition_pct_json"] = json.dumps(comp, separators=(",", ":"))
        row.setdefault("unit_review_required", 0)
        row.setdefault("source_locator", "Record Cleavage dialog")
        synthesis_key = str(row.get("synthesis_key") or "").strip()
        if not synthesis_key:
            row["synthesis_key"] = "|".join(x for x in [row["product_key"], row["sequence_key"], _trim_float(scale)] if x)
    keys = list(row)
    with _connect(db_path) as con:
        con.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [row[k] for k in keys])
        saved = con.execute(f"SELECT * FROM {table} WHERE record_id=?", (row["record_id"],)).fetchone()
    return dict(saved)

def flag_loading_outliers(db_path: str | Path | None = None) -> int:
    """Flag statistical/physical review candidates without deleting any value."""
    rows = list_records("loading", db_path)
    changed = 0
    with _connect(db_path) as con:
        for row in rows:
            value = row.get("loading_rate_mmol_g")
            flag = 1 if value is not None and (float(value) < 0 or float(value) > 2.5) else 0
            # Absorbance/loading transcription mistakes often create implausible >2.5 mmol/g values.
            if flag != int(row.get("outlier_flag") or 0):
                con.execute("UPDATE loading_records SET outlier_flag=?, updated_at=? WHERE record_id=?", (flag, _now(), row["record_id"]))
                changed += 1
    return changed


def sources(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    initialize(db_path)
    with _connect(db_path) as con:
        rows = con.execute("SELECT * FROM import_sources ORDER BY imported_at DESC").fetchall()
    return [dict(row) for row in rows]


__all__ = ["performance_counters", 
    "SCHEMA_VERSION", "STATUSES", "default_db_path", "legacy_db_candidates", "initialize", "set_record_state", "v6_analytics", "quality_findings", "import_cleavage_report",
    "import_loading_csv", "import_sequence_history_csv", "import_synthesis_workbook", "extract_synthesis_sequence_records",
    "import_cleavage_usage_workbook", "import_cleavage_usage_csv", "review_cleavage_usage_units", "add_outcome", "add_issue",
    "preview_path", "data_health", "canonical_product_key", "canonical_sequence_key", "canonical_resin_key", "canonical_amino_acid_key",
    "import_path", "list_records", "normalize_amino_acid", "normalize_resin",
    "describe_amino_acid_identity", "observed_loading_amino_acid_identities",
    "set_status", "update_record", "add_record", "sources", "flag_loading_outliers",
]


# --- R9 recommendation decision -> outcome trace domain -----------------------
RECOMMENDATION_DECISIONS=("Applied as recommended","Applied with modification","Rejected","Not used / informational only")

def add_recommendation_trace(values: Mapping[str,Any], db_path: str|Path|None=None) -> dict[str,Any]:
    initialize(db_path); now=_now(); trace_id=str(values.get('trace_id') or _id())
    recommended=dict(values.get('recommended_condition') or {})
    with _connect(db_path) as con:
        con.execute("""INSERT INTO recommendation_traces(trace_id,work_item_id,run_id,recommendation_type,evidence_source,confidence,evidence_count,recommended_condition_json,apply_allowed,operator_decision,actual_condition_json,final_result_links_json,created_at,resolved_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
            trace_id,str(values.get('work_item_id') or ''),str(values.get('run_id') or ''),str(values.get('recommendation_type') or ''),
            str(values.get('evidence_source') or ''),str(values.get('confidence') or ''),int(values.get('evidence_count') or 0),
            json.dumps(recommended,ensure_ascii=False,default=str),1 if values.get('apply_allowed') else 0,str(values.get('operator_decision') or ''),
            json.dumps(dict(values.get('actual_condition') or {}),ensure_ascii=False,default=str),json.dumps(list(values.get('final_result_links') or []),ensure_ascii=False,default=str),
            now,str(values.get('resolved_at') or ''),str(values.get('note') or '')))
    return get_recommendation_trace(trace_id,db_path)

def get_recommendation_trace(trace_id:str, db_path: str|Path|None=None)->dict[str,Any]:
    initialize(db_path)
    with _connect(db_path) as con: row=con.execute('SELECT * FROM recommendation_traces WHERE trace_id=?',(str(trace_id),)).fetchone()
    if row is None: raise ValueError('Recommendation trace was not found.')
    out=dict(row)
    for source,target,default in [('recommended_condition_json','recommended_condition',{}),('actual_condition_json','actual_condition',{}),('final_result_links_json','final_result_links',[])]:
        try: out[target]=json.loads(out.get(source) or ('[]' if isinstance(default,list) else '{}'))
        except Exception: out[target]=default
    out['apply_allowed']=bool(out.get('apply_allowed')); return out

def list_recommendation_traces(db_path: str|Path|None=None, *, run_id:str='', work_item_id:str='')->list[dict[str,Any]]:
    initialize(db_path); clauses=[]; params=[]
    if run_id: clauses.append('run_id=?'); params.append(str(run_id))
    if work_item_id: clauses.append('work_item_id=?'); params.append(str(work_item_id))
    sql='SELECT trace_id FROM recommendation_traces'+((' WHERE '+' AND '.join(clauses)) if clauses else '')+' ORDER BY created_at DESC'
    with _connect(db_path) as con: ids=[r[0] for r in con.execute(sql,params).fetchall()]
    return [get_recommendation_trace(x,db_path) for x in ids]

def link_recommendation_results(trace_id: str, result_ids: Iterable[Any], db_path: str | Path | None = None) -> dict[str, Any]:
    """Attach canonical Result IDs without changing the recorded operator decision."""
    initialize(db_path)
    existing = get_recommendation_trace(trace_id, db_path)
    links = [str(value) for value in result_ids if str(value or "").strip()]
    # Preserve order and avoid duplicate links.
    links = list(dict.fromkeys(links))
    with _connect(db_path) as con:
        cur = con.execute(
            "UPDATE recommendation_traces SET final_result_links_json=? WHERE trace_id=?",
            (json.dumps(links, ensure_ascii=False), str(trace_id)),
        )
        if not cur.rowcount:
            raise ValueError("Recommendation trace was not found.")
    return get_recommendation_trace(trace_id, db_path)

def resolve_recommendation_trace(trace_id:str, decision:str, *, actual_condition:Mapping[str,Any]|None=None, final_result_links:Iterable[Any]=(), note:str='', db_path: str|Path|None=None)->dict[str,Any]:
    if decision not in RECOMMENDATION_DECISIONS: raise ValueError('Unsupported recommendation decision.')
    initialize(db_path); now=_now()
    with _connect(db_path) as con:
        cur=con.execute('UPDATE recommendation_traces SET operator_decision=?,actual_condition_json=?,final_result_links_json=?,resolved_at=?,note=? WHERE trace_id=?',(decision,json.dumps(dict(actual_condition or {}),ensure_ascii=False,default=str),json.dumps(list(final_result_links or []),ensure_ascii=False,default=str),now,str(note or ''),str(trace_id)))
        if not cur.rowcount: raise ValueError('Recommendation trace was not found.')
    return get_recommendation_trace(trace_id,db_path)
