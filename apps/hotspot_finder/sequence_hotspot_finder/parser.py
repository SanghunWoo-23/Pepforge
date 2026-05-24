from __future__ import annotations
import re
from typing import Tuple, Optional
import pandas as pd

NATURAL = set("ACDEFGHIKLMNPQRSTVWY")

SIDECHAIN_RE = re.compile(r"^([A-Za-z0-9.]+)\[([A-Za-z0-9_.+\-]+)\]$")


def normalize_sequence(seq: str) -> str:
    return str(seq).strip().replace(" ", "").replace("\t", "").replace("–", "-").replace("—", "-")


def split_sequence(seq: str) -> list[str]:
    seq = normalize_sequence(seq)
    if "-" in seq:
        return [x for x in seq.split("-") if x]
    return list(seq)


def split_sidechain(token: str) -> Tuple[str, Optional[str]]:
    m = SIDECHAIN_RE.match(token)
    if m:
        return m.group(1), m.group(2)
    return token, None


def parse_sequence(seq: str, token_db: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    tokens = split_sequence(seq)
    db = token_db.copy()
    db["token"] = db["token"].astype(str)
    db_map = {r["token"]: r.to_dict() for _, r in db.iterrows()}
    rows = []
    model_pos = 0
    residue_pos = 0
    for display_pos, tok in enumerate(tokens, start=1):
        base, side_mod = split_sidechain(tok)
        rec = db_map.get(base)
        warning = ""
        if rec is None:
            if base in NATURAL and len(base) == 1:
                rec = {"token": base, "class": "natural_L_amino_acid", "model_token": base, "charge": 0.0, "hydrophobicity": 0.0, "notes": "implicit natural AA"}
            else:
                rec = {"token": base, "class": "unknown", "model_token": "X", "charge": 0.0, "hydrophobicity": 0.0, "notes": "unknown token"}
                warning = f"Unknown token: {tok}. Treated as X."
        cls = str(rec.get("class", "unknown"))
        mt = rec.get("model_token", "")
        if pd.isna(mt):
            mt = ""
        mt = str(mt)
        esm_policy = str(rec.get("esm_policy", "auto")) if "esm_policy" in rec else "auto"
        if esm_policy == "exclude":
            mt = ""
        elif esm_policy.startswith("expand:"):
            mt = esm_policy.split(":", 1)[1]
        is_model_residue = 1 if mt != "" else 0
        if mt != "":
            # multi-aa expansion such as GGGGS occupies several model positions; assign first position for token.
            model_pos += len(mt)
            token_model_position = model_pos - len(mt) + 1
            residue_pos += 1
        else:
            token_model_position = None
        row = {
            "display_position": display_pos,
            "original_position": display_pos,
            "residue_position": residue_pos if mt != "" else None,
            "model_position": token_model_position,
            "input_token": tok,
            "base_token": base,
            "sidechain_mod": side_mod,
            "class": cls,
            "model_token": mt,
            "is_model_residue": is_model_residue,
            "is_natural_L": int(cls == "natural_L_amino_acid"),
            "is_d_form": int(cls == "D_amino_acid"),
            "is_non_natural": int(cls == "non_natural_amino_acid"),
            "is_linker": int(cls == "linker"),
            "is_n_terminal_mod": int(cls == "N_terminal_modification"),
            "is_c_terminal_mod": int(cls == "C_terminal_modification"),
            "is_label": int(cls == "label"),
            "is_sidechain_modified": int(side_mod is not None),
            "charge": float(rec.get("charge", 0.0) or 0.0),
            "hydrophobicity": float(rec.get("hydrophobicity", 0.0) or 0.0),
            "aromaticity": float(rec.get("aromaticity", 0.0) or 0.0) if "aromaticity" in rec else 0.0,
            "polarity": float(rec.get("polarity", 0.0) or 0.0) if "polarity" in rec else 0.0,
            "bulkiness": float(rec.get("bulkiness", 0.0) or 0.0) if "bulkiness" in rec else 0.0,
            "flexibility": float(rec.get("flexibility", 0.0) or 0.0) if "flexibility" in rec else 0.0,
            "hotspot_penalty": float(rec.get("hotspot_penalty", 0.0) or 0.0) if "hotspot_penalty" in rec else 0.0,
            "hotspot_bonus": float(rec.get("hotspot_bonus", 0.0) or 0.0) if "hotspot_bonus" in rec else 0.0,
            "esm_policy": esm_policy,
            "token_notes": rec.get("notes", ""),
            "warning": warning,
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    model_sequence = "".join(df["model_token"].fillna("").astype(str).tolist())
    return df, model_sequence
