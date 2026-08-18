"""SPPS Planner V4.0.0 final release adjustments.

This final layer is deliberately narrow: it preserves the accepted V2.2.15
workflow and only normalizes startup, cleavage preset display names, and release
version labeling.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

APP_VERSION = "V4.0.0"
VERSION_LABEL = "SPPS Planner V4.0.0"


ACTIVE_RESINS = [
    "Rink Amide AM", "Rink Amide MBHA", "Rink Amide ChemMatrix",
    "Rink Amide Tentagel", "2-CTC", "CTC(합성기)", "Wang", "HMPB",
    "Sieber Amide", "PAL resin", "Tentagel", "Manual",
]
_REMOVED_CTC_ALIASES = {"CTC(합성용)", "CTC 합성용", "CTC-synthesis", "CTC synthesis"}


def _normalize_resin(value):
    text = str(value or "").strip()
    if text in _REMOVED_CTC_ALIASES:
        return "CTC(합성기)"
    return text


def _enforce_resin_choices(gui):
    """Remove the deleted CTC(합성용) UI item without changing other behavior."""
    try:
        gui.RESIN_VALUES = list(ACTIVE_RESINS)
    except Exception:
        pass

    try:
        for item in list(getattr(gui, "pm_items", []) or []):
            if isinstance(item, dict):
                item["resin"] = _normalize_resin(item.get("resin", ""))
    except Exception:
        pass

    try:
        current = _normalize_resin(gui.pm_resin.get())
        if current != str(gui.pm_resin.get() or "").strip():
            gui.pm_resin.set(current)
    except Exception:
        pass

    pm_resin_var = str(getattr(gui, "pm_resin", ""))
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Combobox):
            continue
        try:
            values = [str(v) for v in widget.cget("values")]
            is_resin_widget = (
                str(widget.cget("textvariable")) == pm_resin_var
                or any("CTC" in v or "Rink Amide" in v for v in values)
            )
            if not is_resin_widget:
                continue
            current = _normalize_resin(widget.get())
            widget.configure(values=list(ACTIVE_RESINS))
            if current in ACTIVE_RESINS:
                widget.set(current)
            elif current in {"", "Amide"}:
                # Preserve the accepted blank/default startup state.
                widget.set(current)
        except Exception:
            pass

    try:
        if not getattr(gui, "_v200_resin_alias_trace", False):
            def _migrate_removed_alias(*_args):
                try:
                    value = str(gui.pm_resin.get() or "").strip()
                    normalized = _normalize_resin(value)
                    if normalized != value:
                        gui.pm_resin.set(normalized)
                    for item in list(getattr(gui, "pm_items", []) or []):
                        if isinstance(item, dict) and item.get("resin") in _REMOVED_CTC_ALIASES:
                            item["resin"] = "CTC(합성기)"
                except Exception:
                    pass
            gui.pm_resin.trace_add("write", _migrate_removed_alias)
            gui._v200_resin_alias_trace = True
    except Exception:
        pass


def _walk(widget):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk(child)


def _blank_item():
    return {
        "project": "",
        "peptide": "",
        "sequence": "",
        "copies": "1",
        "scale": "0.2",
        "resin": "Rink Amide AM",
        "loading": "0.8",
        "lot": "",
        "chemistry": "DIC/HOBt",
        "status": "Ready",
        "cleavage_preset": "AUTO",
        "cleavage_components_text": "",
        "loading_time_h": "",
        "cleavage_time_h": "",
    }


def _ensure_one_start_item(gui):
    """Guarantee one blank slot only when the loaded session contains no items."""
    try:
        items = list(getattr(gui, "pm_items", []) or [])
        if items:
            return
        item = _blank_item()
        gui.pm_items = [item]
        gui.pm_list.delete(0, "end")
        try:
            label = gui.pm_display_name(item)
        except Exception:
            label = "New project | New peptide"
        gui.pm_list.insert("end", label)
        # Keep the editor/results empty at startup; the item is loaded only when
        # the operator clicks or double-clicks it.
        gui._v229_active_index = None
    except Exception:
        pass


def _cleavage_display_values():
    try:
        from spps_planner.engine import cleavage_cocktail_presets
        frame = cleavage_cocktail_presets()
        values = ["AUTO"]
        mapping = {}
        for _, row in frame.iterrows():
            code = str(row.get("preset", "") or "").strip()
            components = str(row.get("components", "") or "").strip()
            if not code or code.upper() == "AUTO" or not components or components.startswith("<"):
                continue
            display = "; ".join(part.strip() for part in components.split(";") if part.strip())
            mapping[code] = display
            if display not in values:
                values.append(display)
        return values, mapping
    except Exception:
        return ["AUTO"], {}


def _configure_cleavage_preset(gui):
    values, mapping = _cleavage_display_values()
    try:
        current = str(gui.cleavage_preset.get() or "AUTO").strip()
        if current in mapping:
            gui.cleavage_preset.set(mapping[current])
    except Exception:
        pass
    target_var = str(getattr(gui, "cleavage_preset", ""))
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Combobox):
            continue
        try:
            if str(widget.cget("textvariable")) == target_var:
                widget.configure(values=values, state="normal", width=38)
        except Exception:
            pass


def _apply_title(gui):
    try:
        gui.title(VERSION_LABEL)
    except Exception:
        pass
    for widget in _walk(gui):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")).startswith("SPPS Planner"):
                widget.configure(text=VERSION_LABEL)
        except Exception:
            pass


def _float(value, default=0.0):
    try:
        return float(str(value or "").replace(",", "").strip())
    except Exception:
        return default


def _numstr(value):
    number = _float(value)
    if abs(number - round(number)) < 1e-10:
        return str(int(round(number)))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _ensure_solvent_basis_controls(gui):
    """Create the accepted working-volume controls without a legacy UI layer."""
    defaults = (
        ("solvent_volume_mode", tk.StringVar, "resin_factor"),
        ("amide_ml_per_mmol", tk.StringVar, "10"),
        ("ctc_ml_per_mmol", tk.StringVar, "5"),
        ("solvent_molarity_m", tk.StringVar, "0.2"),
    )
    for name, factory, default in defaults:
        if not hasattr(gui, name):
            setattr(gui, name, factory(value=default))

    if getattr(gui, "_volume_basis_controls_ready", False):
        return
    notebook = None
    panel = getattr(gui, "pm_setup_panel", None)
    for widget in _walk(panel or gui):
        if isinstance(widget, ttk.Notebook):
            try:
                if "Solvents / Wash" in [widget.tab(tab, "text") for tab in widget.tabs()]:
                    notebook = widget
                    break
            except Exception:
                pass
    if notebook is None:
        return
    solvent_tab = None
    for tab in notebook.tabs():
        if str(notebook.tab(tab, "text")) == "Solvents / Wash":
            solvent_tab = notebook.nametowidget(tab)
            break
    if solvent_tab is None:
        return

    box = ttk.LabelFrame(solvent_tab, text="Solvent volume basis / working volume")
    box.grid(row=8, column=0, columnspan=8, sticky="ew", padx=4, pady=(8, 4))
    ttk.Radiobutton(
        box, text="Default resin factor",
        variable=gui.solvent_volume_mode, value="resin_factor",
    ).grid(row=0, column=0, sticky="w", padx=6, pady=2)
    ttk.Label(box, text="Amide/Rink").grid(row=0, column=1, padx=(12, 3))
    ttk.Entry(box, textvariable=gui.amide_ml_per_mmol, width=8).grid(row=0, column=2)
    ttk.Label(box, text="2-CTC/Trityl").grid(row=0, column=3, padx=(12, 3))
    ttk.Entry(box, textvariable=gui.ctc_ml_per_mmol, width=8).grid(row=0, column=4)
    ttk.Label(box, text="mL/mmol").grid(row=0, column=5, padx=4)
    ttk.Radiobutton(
        box, text="Use molarity basis",
        variable=gui.solvent_volume_mode, value="molarity",
    ).grid(row=1, column=0, sticky="w", padx=6, pady=2)
    ttk.Label(box, text="M").grid(row=1, column=1, sticky="e", padx=3)
    ttk.Entry(box, textvariable=gui.solvent_molarity_m, width=8).grid(
        row=1, column=2, sticky="w",
    )
    gui._v257_volume_preview_label = ttk.Label(box, text="")
    gui._v257_volume_preview_label.grid(
        row=2, column=0, columnspan=7, sticky="w", padx=6, pady=(4, 2),
    )
    gui._volume_basis_controls_ready = True


def _update_volume_preview(gui):
    resin = str(getattr(gui, "pm_resin").get() or "").lower()
    is_ctc = any(key in resin for key in ("ctc", "trityl", "chlorotrityl"))
    scale = _float(getattr(gui, "pm_scale").get(), 0.2)
    copies = max(1, int(round(_float(getattr(gui, "pm_copies").get(), 1))))
    mode = str(gui.solvent_volume_mode.get() or "resin_factor")
    if mode == "molarity":
        molarity = max(_float(gui.solvent_molarity_m.get(), 0.2), 1e-12)
        eq = _float(getattr(gui, "coupling_eq").get(), 1)
        volume = scale * copies * eq / molarity
        text = (
            f"Current 1-use mL = {_numstr(volume)} mL  "
            f"(planned mmol / M; M={gui.solvent_molarity_m.get()})"
        )
    else:
        factor_var = gui.ctc_ml_per_mmol if is_ctc else gui.amide_ml_per_mmol
        factor = max(_float(factor_var.get(), 5 if is_ctc else 10), 0.0)
        volume = scale * copies * factor
        family = "2-CTC/Trityl" if is_ctc else "Amide/Rink"
        text = (
            f"Current 1-use mL = {_numstr(volume)} mL  "
            f"({family}: scale × {_numstr(factor)} mL/mmol)"
        )
    label = getattr(gui, "_v257_volume_preview_label", None)
    if label is not None:
        label.configure(text=text)


def _bind_resin_live_preview(gui, ns):
    """Bind the final active resin combobox/variable to the working-volume preview.

    Several legacy UI layers rebuild or replace bindings during startup, so the
    earlier Solvents/Wash trace can point at a stale variable.  Bind once more
    at the final V3.0.0 layer and also listen to the actual ComboboxSelected
    event.  This changes display refresh only; it does not generate/recalculate
    a Plan.
    """
    _ensure_solvent_basis_controls(gui)

    def refresh(*_args):
        pending = getattr(gui, "_v3_volume_preview_after_id", None)
        if pending:
            return

        def run():
            gui._v3_volume_preview_after_id = None
            try:
                _update_volume_preview(gui)
            except Exception:
                pass

        try:
            gui._v3_volume_preview_after_id = gui.after_idle(run)
        except Exception:
            run()

    if not getattr(gui, "_v200_resin_preview_traces", None):
        traces = []
        for variable in (
            getattr(gui, "pm_resin", None),
            getattr(gui, "pm_scale", None),
            getattr(gui, "pm_copies", None),
            getattr(gui, "coupling_eq", None),
            getattr(gui, "solvent_volume_mode", None),
            getattr(gui, "amide_ml_per_mmol", None),
            getattr(gui, "ctc_ml_per_mmol", None),
            getattr(gui, "solvent_molarity_m", None),
        ):
            try:
                traces.append((variable, variable.trace_add("write", refresh)))
            except Exception:
                pass
        gui._v200_resin_preview_traces = traces

    target_var = str(getattr(gui, "pm_resin", ""))
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Combobox):
            continue
        try:
            if str(widget.cget("textvariable")) != target_var:
                continue
            if not getattr(widget, "_v200_resin_preview_bound", False):
                widget.bind("<<ComboboxSelected>>", refresh, add="+")
                widget._v200_resin_preview_bound = True
        except Exception:
            pass
    refresh()


def apply_post_build(gui, ns):
    """Apply the accepted V3.0.0 display/startup corrections."""
    _ensure_one_start_item(gui)
    _enforce_resin_choices(gui)
    _bind_resin_live_preview(gui, ns)
    _configure_cleavage_preset(gui)
    _apply_title(gui)
    # Reassert after legacy idle callbacks that may repopulate combobox values.
    try:
        gui.after_idle(
            lambda _gui=gui: (
                _enforce_resin_choices(_gui),
                _bind_resin_live_preview(_gui, ns),
            )
        )
        for delay in (100, 400, 1000):
            gui.after(
                delay,
                lambda _gui=gui: (
                    _enforce_resin_choices(_gui),
                    _bind_resin_live_preview(_gui, ns),
                ),
            )
    except Exception:
        pass
