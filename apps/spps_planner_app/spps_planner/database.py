from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_compounds(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA_DIR / "compounds.csv"
    df = pd.read_csv(path)
    if "Token" in df.columns:
        df["Token"] = df["Token"].astype(str)
    return df


def load_rules(path: str | Path | None = None) -> dict:
    path = Path(path) if path else DATA_DIR / "process_rules.csv"
    df = pd.read_csv(path)
    return {row["rule"]: row["value"] for _, row in df.iterrows()}


def compound_lookup(compounds: pd.DataFrame) -> dict:
    lookup = {}
    for _, row in compounds.iterrows():
        token = str(row.get("Token", "")).strip()
        if token:
            lookup[token] = row.to_dict()
    return lookup


def save_compounds(df: pd.DataFrame, path: str | Path | None = None) -> None:
    path = Path(path) if path else DATA_DIR / "compounds.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
