"""V2.2.13 operator-requested final restoration.

Restores position-based AA eq/doubling controls, exact sequence-length plan
construction, Apply Change synchronization, cleavage inclusion in totals,
compact checklist UI, operator-facing label cleanup, and stable peptide-item
state handling without deleting legacy functionality.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Any

APP_VERSION = "V4.0.0"
VERSION_LABEL = "SPPS Planner V4.0.0"


def _walk(widget):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk(child)


def _get(var, default=""):
    try:
        return var.get()
    except Exception:
        return default


def _set(var, value):
    try:
        var.set(value)
    except Exception:
        pass


def _num(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _parse_ranges(text: str, default: list[tuple[int, int, float]]) -> list[tuple[int, int, float]]:
    """Parse C-terminal position rules.

    Accepted forms include both ranges (``4-7:2``) and a single position
    (``7:2``).  A blank field means "no position-specific override"; it
    must not silently re-enable the old example/default rules.
    """
    raw = str(text or "").strip()
    if not raw:
        return []

    out: list[tuple[int, int, float]] = []
    for part in re.split(r"[,;]+", raw):
        m = re.fullmatch(
            r"\s*(\d+)(?:\s*-\s*(\d+))?\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*",
            part,
        )
        if not m:
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) is not None else a
        v = float(m.group(3))
        out.append((min(a, b), max(a, b), v))
    return out


def _range_value(position: int, rules, fallback: float) -> float:
    for start, end, value in rules:
        if start <= position <= end:
            return value
    return fallback


def _sequence_length(gui) -> int:
    seq = str(_get(getattr(gui, "pm_sequence", None), "") or "").strip()
    try:
        from spps_planner.parser import parse_sequence
        return len(list(parse_sequence(seq).core_tokens or []))
    except Exception:
        return len(re.findall(r"[A-Za-z]", seq))


def _sequence_unit_count(gui) -> int:
    """Count all written synthesis units used by the shared C-term rules.

    Core tokens already include natural AA, d-AA, internal chemicals and
    linkers.  A terminal modifier/label/tag such as Ac, FITC, Biotin or His6
    is one additional synthesis unit.
    """
    seq = str(_get(getattr(gui, "pm_sequence", None), "") or "").strip()
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(seq)
        return len(list(parsed.core_tokens or [])) + (1 if str(parsed.nterm or "").strip() else 0)
    except Exception:
        return _sequence_length(gui)


def _is_aa_row(row: dict[str, Any]) -> bool:
    # Kept for compatibility with older callers.  Position-rule application
    # itself now uses every real synthesis unit, not only Fmoc AA rows.
    return str(row.get("Unit name", "")).strip().lower().startswith("fmoc-")


def _is_position_unit_row(row: dict[str, Any]) -> bool:
    """AA, d-AA, chemical, label, tag and linker share one position system."""
    return bool(str(row.get("Unit name", "") or "").strip()) and not _is_fmoc_removal(row)


def _is_fmoc_removal(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(k, "")) for k in ("Unit name", "Note"))
    key = re.sub(r"[^a-z0-9]+", "", text.lower())
    return "fmocremoval" in key or "deprotectiononly" in key


def _apply_generated_position_rules(gui, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(r) for r in rows if not _is_fmoc_removal(r)]
    seq_units = _sequence_unit_count(gui)
    unit_indices = [i for i, r in enumerate(rows) if _is_position_unit_row(r)]
    # Preserve the established direct-loaded 2-CTC handling: if a historical
    # route emits an extra C-terminal loading unit, remove only that excess.
    if seq_units >= 0 and len(unit_indices) > seq_units:
        remove_count = len(unit_indices) - seq_units
        remove = set(unit_indices[:remove_count])
        rows = [r for i, r in enumerate(rows) if i not in remove]
        unit_indices = [i for i, r in enumerate(rows) if _is_position_unit_row(r)]

    use_eq = bool(_get(getattr(gui, "use_position_aa_eq", None), True))
    use_double = bool(_get(getattr(gui, "use_position_doubling", None), True))
    eq_rules = _parse_ranges(_get(getattr(gui, "position_aa_eq_rules", None), ""), [])
    dbl_rules = _parse_ranges(_get(getattr(gui, "position_doubling_rules", None), ""), [])
    follows = bool(_get(getattr(gui, "reagent_eq_follows_coupling_eq", None), True))
    # Direct-loaded 2-CTC omits the already resin-bound C-terminal residue
    # from the editable Plan. Keep that residue in the positional count.
    # Terminal chemical/label/tag units are included in seq_units, so every
    # real synthesis unit shares the same C-term position system.
    cterm_offset = max(0, seq_units - len(unit_indices))
    for ordinal, row_index in enumerate(unit_indices, start=1):
        # The editable Plan is ordered C -> N across all synthesis units.
        cterm_position = cterm_offset + ordinal
        row = rows[row_index]
        if use_eq:
            fallback = _num(row.get("Unit eq"), _num(_get(getattr(gui, "coupling_eq", None), 5), 5))
            eq = _range_value(cterm_position, eq_rules, fallback)
            row["Unit eq"] = str(int(eq)) if float(eq).is_integer() else str(eq)
            if follows:
                for name_col, eq_col in (("Reagent 1","R1 eq"),("Reagent 2 / catalyst","R2 eq"),("Base","Base eq")):
                    if str(row.get(name_col, "")).strip():
                        row[eq_col] = row["Unit eq"]
        if use_double:
            repeat = int(round(_range_value(cterm_position, dbl_rules, 1.0)))
            row["Repeat"] = str(max(1, repeat))
    for i, row in enumerate(rows, 1):
        row["No"] = str(i)
    return rows



def _find_setup_notebook(gui):
    for w in _walk(gui):
        if isinstance(w, ttk.Notebook):
            try:
                labels = [str(w.tab(t, "text")) for t in w.tabs()]
            except Exception:
                continue
            if "Unit defaults" in labels:
                return w
    return None


def _tab_frame(nb, label):
    for tab in nb.tabs():
        try:
            if str(nb.tab(tab, "text")) == label:
                return nb.nametowidget(tab)
        except Exception:
            pass
    return None


def _install_position_ui(gui):
    gui.use_position_aa_eq = getattr(gui, "use_position_aa_eq", tk.BooleanVar(value=True))
    gui.position_aa_eq_rules = getattr(gui, "position_aa_eq_rules", tk.StringVar(value=""))
    gui.use_position_doubling = getattr(gui, "use_position_doubling", tk.BooleanVar(value=True))
    gui.position_doubling_rules = getattr(gui, "position_doubling_rules", tk.StringVar(value=""))
    nb = _find_setup_notebook(gui)
    frame = _tab_frame(nb, "Unit defaults") if nb else None
    if frame is None:
        return
    # Remove the incorrect V2.2.12 helper checkboxes and explanatory text.
    bad_prefixes = (
        "Use default AA eq", "Use default doubling", "Use the same eq/doubling",
        "Manual per-unit values", "Default AA doubling",
    )
    for w in list(frame.winfo_children()):
        try:
            text = str(w.cget("text"))
        except Exception:
            text = ""
        if text.startswith(bad_prefixes):
            try: w.destroy()
            except Exception: pass
    max_row = 0
    for w in frame.winfo_children():
        try: max_row = max(max_row, int(w.grid_info().get("row", 0)))
        except Exception: pass
    box = ttk.LabelFrame(frame, text="Position rules from C-terminus")
    box.grid(row=max_row+1, column=0, columnspan=8, sticky="ew", padx=4, pady=(8,4))
    box.columnconfigure(2, weight=1)
    ttk.Checkbutton(box, text="AAs eq", variable=gui.use_position_aa_eq).grid(row=0,column=0,sticky="w",padx=5,pady=4)
    ttk.Label(box, text="C-term ranges").grid(row=0,column=1,sticky="e",padx=4)
    ttk.Entry(box, textvariable=gui.position_aa_eq_rules, width=28).grid(row=0,column=2,sticky="ew",padx=4)
    ttk.Checkbutton(box, text="Doubling", variable=gui.use_position_doubling).grid(row=1,column=0,sticky="w",padx=5,pady=4)
    ttk.Label(box, text="C-term ranges").grid(row=1,column=1,sticky="e",padx=4)
    ttk.Entry(box, textvariable=gui.position_doubling_rules, width=28).grid(row=1,column=2,sticky="ew",padx=4)
    ttk.Label(box, text="Example: AAs eq 1-3:1.5, 4-6:2 / Doubling 4-6:2").grid(row=2,column=0,columnspan=3,sticky="w",padx=5,pady=(0,4))


def _clean_selected_labels(gui):
    replacements = {
        "Selected Peptide Editor":"Peptide Editor", "Selected Plan":"Plan",
        "Selected Materials":"Materials", "Selected Total Materials":"Total Materials",
        "Selected Checklist":"Checklist", "Selected Cleavage Cocktail":"Cleavage Cocktail",
    }
    for w in _walk(gui):
        try:
            text = str(w.cget("text"))
        except Exception:
            continue
        new = replacements.get(text)
        if not new and text.lower().startswith("selected "):
            new = text[len("Selected "):]
        if new:
            try: w.configure(text=new)
            except Exception: pass
    for w in _walk(gui):
        if isinstance(w, ttk.Notebook):
            for tab in w.tabs():
                try:
                    text = str(w.tab(tab, "text"))
                    if text in replacements:
                        w.tab(tab, text=replacements[text])
                    elif text.lower().startswith("selected "):
                        w.tab(tab, text=text[len("Selected "):])
                except Exception:
                    pass


def _compact_checklist(gui):
    tree = getattr(gui, "progress_tree", None)
    if tree is not None:
        widths = {"line":45,"done":55,"checked_at":105,"operation":180,"unit":115,"next_step":185,"note":240}
        try:
            for col in tree["columns"]:
                tree.column(col, width=widths.get(col, 100), minwidth=35, stretch=(col in {"operation","next_step","note"}))
        except Exception:
            pass
    # Reduce large fixed spacer panes above checklist where possible.
    for w in _walk(gui):
        if isinstance(w, ttk.Panedwindow):
            try:
                w.after_idle(lambda p=w: [p.sashpos(i, 140) for i in range(max(0, len(p.panes())-1))])
            except Exception:
                pass


def _remove_cleavage_apply_text(gui):
    for w in list(_walk(gui)):
        try: text = str(w.cget("text"))
        except Exception: continue
        if "Apply with Apply Change" in text:
            try: w.destroy()
            except Exception: pass


def _install_title(gui):
    try: gui.title(VERSION_LABEL)
    except Exception: pass
    for w in _walk(gui):
        try:
            if isinstance(w, ttk.Label) and str(w.cget("text")).startswith("SPPS Planner GitHub"):
                w.configure(text=VERSION_LABEL)
        except Exception:
            pass


def apply_post_build(gui):
    _install_title(gui)
    _install_position_ui(gui)
    _clean_selected_labels(gui)
    _compact_checklist(gui)
    _remove_cleavage_apply_text(gui)

