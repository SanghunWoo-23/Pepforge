from pathlib import Path
import sys
import math
import shutil
from datetime import datetime
import pandas as pd

try:
    from .user_paths import user_data_file
except Exception:
    user_data_file = None

DATA_DIR = (
    Path(getattr(sys, "_MEIPASS")) / "apps" / "spps_planner_app" / "data"
    if getattr(sys, "_MEIPASS", None)
    else Path(__file__).resolve().parents[1] / "data"
)
REAGENT_LIBRARY_DIR = DATA_DIR / "spps_reagent_library"

# Rows whose bundled definitions are part of the operator-facing V3 Fmoc
# catalog.  These are migrated deliberately when an older bundled default is
# found in the user database; unrelated user-created rows remain untouched.
V3_FMOC_CATALOG_TOKENS = {
    *(f"d{letter}" for letter in "ARNDCEQGHILKMFPSTWYV"),
    "Dab", "Orn", "Nle", "Nva", "Aib", "Sar", "Dap", "Cit",
    "Hyp", "Cha", "hArg", "hLys", "Pen", "Bpa",
    "Ahx", "AEEA", "PEG1", "PEG2", "PEG3", "PEG4", "PEG5CH2",
    "PEG6", "PEG8", "PEG11CH2", "PEG12", "PEG24", "bAla",
    "Ava5", "Aun11", "Ado12", "PEG3AMIDO", "PEG4AMIDO",
    "PEG5AMIDO", "PEG6AMIDO", "PEG8AMIDO", "PEG10AMIDO",
    "PEG12AMIDO", "PEG20AMIDO", "gAla", "GABA",
}

LEGACY_BUNDLED_SOURCE_MARKERS = {
    "formula-normalized proxy",
    "curated linker policy",
    "v2.0.92 curated db",
    "curated/vendor/formula",
}


def _is_legacy_bundled_default(row: pd.Series) -> bool:
    source = _clean_token_value(row.get("Source used", "")).lower()
    protected = _clean_token_value(row.get("Reagent/protected form", "")).lower()
    return source in LEGACY_BUNDLED_SOURCE_MARKERS or any(
        marker in protected
        for marker in (
            "default/proxy", "vendor-specific", "verify vendor form",
            "fmoc-4-aminobutyric acid /", "fmoc-beta-ala-oh",
        )
    )


def _clean_token_value(value) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    # Preserve explicit control tokens such as NONE; only blank actual null/NaN.
    if text.lower() in {"nan", "null"}:
        return ""
    return text


def bundled_compounds_path() -> Path:
    return DATA_DIR / "compounds.csv"


def user_compounds_path() -> Path | None:
    return user_data_file("compounds.csv") if user_data_file is not None else None


def _default_or_user_path(filename: str) -> Path:
    bundled = DATA_DIR / filename
    if user_data_file is not None:
        override = user_data_file(filename)
        if override.exists():
            if filename == "compounds.csv":
                _migrate_user_compounds_if_needed(override, bundled)
            return override
    return bundled


def _ensure_user_copy(filename: str) -> Path:
    if user_data_file is None:
        return DATA_DIR / filename
    target = user_data_file(filename)
    if not target.exists():
        src = DATA_DIR / filename
        if src.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    elif filename == "compounds.csv":
        _migrate_user_compounds_if_needed(target, DATA_DIR / filename)
    return target


def compounds_db_source() -> dict:
    bundled = bundled_compounds_path()
    user = user_compounds_path()
    active = _default_or_user_path("compounds.csv")
    return {
        "active_path": str(active),
        "bundled_path": str(bundled),
        "user_override_path": str(user) if user is not None else "",
        "using_user_override": bool(user is not None and user.exists()),
    }


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_user_compounds() -> Path | None:
    user = user_compounds_path()
    if user is None or not user.exists():
        return None
    backup = user.with_name(f"compounds_backup_{_timestamp()}.csv")
    shutil.copy2(user, backup)
    return backup


def reset_user_compounds() -> Path:
    target = _ensure_user_copy("compounds.csv")
    backup_user_compounds()
    shutil.copy2(bundled_compounds_path(), target)
    return target


def _read_csv_safe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def normalize_compounds_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Token" in df.columns:
        df["Token"] = df["Token"].map(_clean_token_value)
    for col in ["Active?", "Counts as coupling unit?", "Terminal/control only?"]:
        if col in df.columns:
            def norm(v):
                t = str(v).strip().lower()
                if t in {"yes", "y", "true", "1"}: return "Yes"
                if t in {"no", "n", "false", "0"}: return "No"
                if t in {"", "nan", "none", "null"}: return ""
                return str(v).strip()
            df[col] = df[col].map(norm)
    return df


def validate_compounds_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def add(level, column, row_index, issue, value=""):
        rows.append({"level": level, "column": column, "row_index": row_index, "issue": issue, "value": value})
    required = ["Token", "Class", "Reagent/protected form", "Reagent MW (g/mol)", "Product MW contribution (g/mol)", "Counts as coupling unit?", "Active?", "Chemistry profile"]
    for col in required:
        if col not in df.columns:
            add("ERROR", col, "", "Required column is missing.")
    if "Token" in df.columns:
        token = df["Token"].fillna("").astype(str).str.strip()
        terminal = df.get("Terminal/control only?", "").fillna("").astype(str).str.lower().isin(["yes", "true", "1", "y"]) if hasattr(df.get("Terminal/control only?", ""), "fillna") else pd.Series([False]*len(df))
        profile = df.get("Chemistry profile", "").fillna("").astype(str).str.upper() if hasattr(df.get("Chemistry profile", ""), "fillna") else pd.Series([""]*len(df))
        blank_error_mask = token.eq("") & ~(terminal | profile.eq("CONTROL"))
        for i, v in token[blank_error_mask].items():
            add("ERROR", "Token", i, "Token is required unless the row is an explicit terminal/control blank option.", v)
        norm = token.str.lower()
        dup = norm[norm.ne("") & norm.duplicated(keep=False)]
        for i, v in token[dup.index].items():
            add("ERROR", "Token", i, "Duplicate token after case-normalization.", v)
    for col in ["Reagent MW (g/mol)", "Product MW contribution (g/mol)"]:
        if col in df.columns:
            raw = df[col].fillna("").astype(str).str.strip()
            bad = raw.ne("") & pd.to_numeric(raw, errors="coerce").isna()
            for i, v in raw[bad].items():
                add("ERROR", col, i, "Numeric value required or leave blank.", v)
    for col in ["Active?", "Counts as coupling unit?", "Terminal/control only?"]:
        if col in df.columns:
            raw = df[col].fillna("").astype(str).str.strip()
            ok = {"", "yes", "y", "true", "1", "no", "n", "false", "0"}
            for i, v in raw[~raw.str.lower().isin(ok)].items():
                add("ERROR", col, i, "Use Yes/No, True/False, 1/0, or blank.", v)
    return pd.DataFrame(rows)


def _migrate_user_compounds_if_needed(user_path: Path, bundled_path: Path) -> bool:
    if not user_path.exists() or not bundled_path.exists():
        return False
    try:
        user_df = _read_csv_safe(user_path)
        bundled_df = _read_csv_safe(bundled_path)
    except Exception:
        return False
    changed = False
    # Add new schema columns from bundled DB while preserving user edits.
    for col in bundled_df.columns:
        if col not in user_df.columns:
            user_df[col] = ""
            changed = True
    if "Token" in user_df.columns and "Token" in bundled_df.columns:
        user_tokens = user_df["Token"].map(_clean_token_value)
        bundled_rows = {
            _clean_token_value(row.get("Token", "")): row
            for _, row in bundled_df.iterrows()
            if _clean_token_value(row.get("Token", ""))
        }
        for token in V3_FMOC_CATALOG_TOKENS:
            bundled_row = bundled_rows.get(token)
            if bundled_row is None:
                continue
            matching = user_tokens[user_tokens.str.lower().eq(token.lower())].index
            if len(matching) == 0:
                user_df = pd.concat(
                    [user_df, pd.DataFrame([{c: bundled_row.get(c, "") for c in user_df.columns}])],
                    ignore_index=True,
                )
                user_tokens = user_df["Token"].map(_clean_token_value)
                changed = True
                continue
            index = matching[0]
            if _is_legacy_bundled_default(user_df.loc[index]):
                for col in bundled_df.columns:
                    user_df.at[index, col] = bundled_row.get(col, "")
                changed = True
    # Preserve any user-only columns but order bundled columns first.
    ordered = list(bundled_df.columns) + [c for c in user_df.columns if c not in bundled_df.columns]
    user_df = user_df[ordered]
    user_df = normalize_compounds_dataframe(user_df)
    issues = validate_compounds_dataframe(user_df)
    # Do not overwrite an invalid user DB automatically; leave it for DB Editor.
    if changed and not (not issues.empty and issues["level"].eq("ERROR").any()):
        backup_user_compounds()
        user_df.to_csv(user_path, index=False, encoding="utf-8-sig")
        return True
    return False


def merge_bundled_compounds_into_user() -> dict:
    target = _ensure_user_copy("compounds.csv")
    backup = backup_user_compounds()
    bundled = normalize_compounds_dataframe(_read_csv_safe(bundled_compounds_path()))
    user = normalize_compounds_dataframe(_read_csv_safe(target))
    for col in bundled.columns:
        if col not in user.columns:
            user[col] = ""
    for col in user.columns:
        if col not in bundled.columns:
            bundled[col] = ""
    ordered = list(bundled.columns) + [c for c in user.columns if c not in bundled.columns]
    user = user[ordered]
    user_norm = user["Token"].fillna("").astype(str).str.lower() if "Token" in user.columns else pd.Series([], dtype=str)
    added = 0
    if "Token" in bundled.columns:
        for _, row in bundled.iterrows():
            tok = _clean_token_value(row.get("Token", ""))
            if tok and not user_norm.eq(tok.lower()).any():
                user = pd.concat([user, pd.DataFrame([{c: row.get(c, "") for c in user.columns}])], ignore_index=True)
                user_norm = pd.concat([user_norm, pd.Series([tok.lower()])], ignore_index=True)
                added += 1
    issues = validate_compounds_dataframe(user)
    if not issues.empty and issues["level"].eq("ERROR").any():
        raise ValueError("Merged DB has validation errors; save aborted.")
    user.to_csv(target, index=False, encoding="utf-8-sig")
    return {"target": str(target), "backup": str(backup) if backup else "", "added_rows": added, "columns": len(user.columns), "rows": len(user)}


def load_compounds(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else _default_or_user_path("compounds.csv")
    df = pd.read_csv(path)
    df = normalize_compounds_dataframe(df)
    return df


def load_rules(path: str | Path | None = None) -> dict:
    path = Path(path) if path else DATA_DIR / "process_rules.csv"
    df = pd.read_csv(path).dropna(subset=["rule"])
    out = {}
    for _, row in df.iterrows():
        key = _clean_token_value(row.get("rule"))
        if not key:
            continue
        value = row.get("value")
        try:
            if isinstance(value, str) and value.strip() == "":
                out[key] = ""
            else:
                out[key] = float(value)
        except Exception:
            out[key] = value
    return out


def compound_lookup(compounds: pd.DataFrame) -> dict:
    """Index internal sequence tokens and exact protected bottle names."""
    lookup = {}
    if compounds is None or compounds.empty:
        return lookup
    for _, row in compounds.iterrows():
        token = _clean_token_value(row.get("Token", ""))
        protected = _clean_token_value(row.get("Reagent/protected form", ""))
        data = row.to_dict()
        for name in (token, protected):
            if not name:
                continue
            lookup.setdefault(name, data)
            lookup.setdefault(name.upper(), data)
            lookup.setdefault(name.lower(), data)
    return lookup


def load_reagent_library(directory: str | Path | None = None) -> pd.DataFrame:
    """Load coupling reagents, additives, bases, solvents and modifier reagents.

    The library is separate from compounds.csv because it describes auxiliary
    materials such as DIC, HOBt, DIEA, DMF, DCM and TFA. Missing files are
    tolerated so the planner still opens from a partial GitHub checkout.
    """
    directory = Path(directory) if directory else REAGENT_LIBRARY_DIR
    frames = []
    for name in ["coupling_reagents.csv", "catalysts_additives.csv", "bases_solvents_modifiers.csv"]:
        path = directory / name
        if path.exists():
            frames.append(pd.read_csv(path))
    if not frames:
        return pd.DataFrame(columns=["name", "class", "MW", "density_g_mL", "state", "default_role", "notes"])
    df = pd.concat(frames, ignore_index=True)
    if "name" in df.columns:
        df["name"] = df["name"].map(_clean_token_value)
    return df


def reagent_lookup(library: pd.DataFrame | None = None) -> dict:
    library = library if library is not None else load_reagent_library()
    lookup = {}
    if library is None or library.empty:
        return lookup
    for _, row in library.iterrows():
        name = _clean_token_value(row.get("name", ""))
        if not name:
            continue
        data = row.to_dict()
        lookup[name] = data
        lookup.setdefault(name.upper(), data)
        lookup.setdefault(name.lower(), data)
    # Common aliases not always written as separate rows.
    for alias, target in {"DIPEA": "DIEA", "MC": "DCM", "Methylene chloride": "DCM", "Ac2O": "Acetic anhydride"}.items():
        if target in lookup:
            lookup.setdefault(alias, lookup[target])
            lookup.setdefault(alias.upper(), lookup[target])
            lookup.setdefault(alias.lower(), lookup[target])
    return lookup



def audit_compound_database(compounds: pd.DataFrame | None = None, reagent_library: pd.DataFrame | None = None) -> pd.DataFrame:
    """Audit compound and auxiliary reagent databases for calculator-risk issues.

    The audit is intentionally conservative: generic/vendor-form tokens are not
    auto-filled with guessed MW values; they are flagged so the operator can add
    a form-specific row from a CoA/vendor sheet.
    """
    compounds = compounds if compounds is not None else load_compounds()
    reagent_library = reagent_library if reagent_library is not None else load_reagent_library()
    rows = []

    def add(level: str, table: str, item: str, issue: str, action: str = ""):
        rows.append({"level": level, "table": table, "item": item, "issue": issue, "recommended_action": action})

    if compounds is None or compounds.empty:
        add("ERROR", "compounds.csv", "<file>", "Compound DB is empty or missing.", "Restore compounds.csv.")
        return pd.DataFrame(rows)

    required = ["Token", "Class", "Reagent/protected form", "Reagent MW (g/mol)", "Product MW contribution (g/mol)", "Counts as coupling unit?", "Active?", "Chemistry profile"]
    for col in required:
        if col not in compounds.columns:
            add("ERROR", "compounds.csv", col, "Required column is missing.", "Add the column or restore the DB schema.")

    token = compounds.get("Token", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    norm = token.str.lower()
    dup_norms = sorted([x for x in norm[norm.ne("") & norm.duplicated(keep=False)].unique()])
    for n in dup_norms:
        original = ", ".join(token[norm.eq(n)].tolist())
        add("WARNING", "compounds.csv", original, "Duplicate token after case-normalization.", "Merge duplicate rows; parser lookup is case-insensitive.")

    active = compounds.get("Active?", "").astype(str).str.lower().isin(["yes", "true", "1", "y"])
    counts = compounds.get("Counts as coupling unit?", "").astype(str).str.lower().isin(["yes", "true", "1", "y"])
    terminal = compounds.get("Terminal/control only?", "").astype(str).str.lower().isin(["yes", "true", "1", "y"])
    profile = compounds.get("Chemistry profile", "").fillna("").astype(str).str.upper()
    cls = compounds.get("Class", "").fillna("").astype(str)
    mw = pd.to_numeric(compounds.get("Reagent MW (g/mol)", pd.Series([0]*len(compounds))), errors="coerce").fillna(0.0)
    prod = pd.to_numeric(compounds.get("Product MW contribution (g/mol)", pd.Series([0]*len(compounds))), errors="coerce").fillna(0.0)

    for i, row in compounds[active & counts & mw.le(0)].iterrows():
        tok = str(row.get("Token", "")).strip()
        if not tok:
            continue
        prof = str(row.get("Chemistry profile", "")).upper()
        if any(x in prof for x in ("MANUAL", "MACRO")):
            level = "INFO"
            issue = "Manual/macro token has no reagent MW by design."
            action = "Use expanded residues or add a vendor/form-specific row before using this for material mass."
        elif terminal.iloc[i] or prof == "CONTROL":
            level = "INFO"
            issue = "Terminal/control token has no reagent MW."
            action = "Leave as control or add exact reagent MW if it is used as a real coupling unit."
        else:
            level = "WARNING"
            issue = "Active coupling token has missing reagent MW; planned grams will be manual/zero."
            action = "Add Reagent MW from CoA/vendor sheet."
        add(level, "compounds.csv", tok, issue, action)

    for i, row in compounds[active & counts & prod.le(0)].iterrows():
        tok = str(row.get("Token", "")).strip()
        if not tok:
            continue
        prof = str(row.get("Chemistry profile", "")).upper()
        if any(x in prof for x in ("MANUAL", "MACRO")):
            level = "INFO"
            issue = "Manual/macro token has no product MW contribution by design."
            action = "Use expanded residues or add exact product contribution once the form is known."
        elif terminal.iloc[i] or prof == "CONTROL":
            level = "INFO"
            issue = "Terminal/control token has no product MW contribution."
            action = "Leave as control or add contribution if terminal chemistry should affect MW."
        else:
            level = "WARNING"
            issue = "Active coupling token has missing product MW contribution; product MW may be underestimated."
            action = "Add product contribution for final MW/M+H/M+Na calculation."
        add(level, "compounds.csv", tok, issue, action)

    for _, row in compounds[active & profile.str.contains("MANUAL_REQUIRED", na=False)].iterrows():
        tok = str(row.get("Token", "")).strip()
        if tok:
            add("INFO", "compounds.csv", tok, "Generic/manual-required token present.", "Use exact acid/NHS/salt/protected form for final material calculation.")

    if reagent_library is None or reagent_library.empty:
        add("ERROR", "spps_reagent_library", "<folder>", "Auxiliary reagent library is empty or missing.", "Restore spps_reagent_library CSV files.")
    else:
        rname = reagent_library.get("name", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
        rnorm = rname.str.lower()
        for n in sorted([x for x in rnorm[rnorm.ne("") & rnorm.duplicated(keep=False)].unique()]):
            add("WARNING", "spps_reagent_library", ", ".join(rname[rnorm.eq(n)].tolist()), "Duplicate auxiliary reagent name after case-normalization.", "Merge duplicate rows or keep aliases explicit.")
        rmw = pd.to_numeric(reagent_library.get("MW", pd.Series([0]*len(reagent_library))), errors="coerce").fillna(0.0)
        rden = pd.to_numeric(reagent_library.get("density_g_mL", pd.Series([0]*len(reagent_library))), errors="coerce").fillna(0.0)
        state = reagent_library.get("state", "").fillna("").astype(str).str.lower()
        for _, row in reagent_library[rmw.le(0)].iterrows():
            add("WARNING", "spps_reagent_library", str(row.get("name", "")).strip(), "Auxiliary reagent MW is missing.", "Add MW or mark as manual-only.")
        for _, row in reagent_library[state.eq("liquid") & rden.le(0)].iterrows():
            add("WARNING", "spps_reagent_library", str(row.get("name", "")).strip(), "Liquid reagent density is missing; mL cannot be calculated.", "Add density_g_mL.")

    if not rows:
        add("OK", "database", "all", "No DB issue detected by automated audit.", "")
    return pd.DataFrame(rows)

def save_compounds(df: pd.DataFrame, path: str | Path | None = None, *, validate: bool = True, backup: bool = True) -> None:
    # Default GUI edits go to a user-writable override copy.  The bundled DB
    # remains a safe read-only default for installed releases.
    path = Path(path) if path else _ensure_user_copy("compounds.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    df = normalize_compounds_dataframe(df)
    if validate:
        issues = validate_compounds_dataframe(df)
        if not issues.empty and issues["level"].eq("ERROR").any():
            preview = "; ".join(issues.head(5)["issue"].astype(str).tolist())
            raise ValueError(f"DB validation failed before save: {preview}")
    if backup and path.exists() and path.name == "compounds.csv":
        try: backup_user_compounds()
        except Exception: pass
    df.to_csv(path, index=False, encoding="utf-8-sig")
