from __future__ import annotations
import json, shutil, datetime, zipfile
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
import pandas as pd


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(str(text), encoding="utf-8")


def load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_fasta_or_sequence(text: str) -> Dict[str, str]:
    text = str(text).strip()
    if not text:
        raise ValueError("Input sequence is empty.")
    records: Dict[str, str] = {}
    if text.startswith(">"):
        name, lines = None, []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    records[name] = "".join(lines).strip()
                name = line[1:].strip() or f"sequence_{len(records)+1}"
                lines = []
            else:
                lines.append(line)
        if name is not None:
            records[name] = "".join(lines).strip()
    else:
        records["direct_input"] = text
    return records


def load_optional_csv(path: Optional[str | Path]) -> Optional[pd.DataFrame]:
    if path is None:
        return None
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    return pd.read_csv(p)


def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_run_summary(path: str | Path, summary: dict) -> None:
    lines = ["Sequence Hotspot Finder run summary", "=" * 42, ""]
    for k, v in summary.items():
        lines.append(f"{k}: {v}")
    write_text(path, "\n".join(lines) + "\n")


def package_outputs(zip_path: str | Path, files: Dict[str, str | Path]) -> str:
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, fpath in files.items():
            if fpath is None:
                continue
            p = Path(fpath)
            if p.exists():
                zf.write(p, arcname=arcname)
    return str(zip_path)
