"""Direct custom-material database workflow for SPPS Planner V4.0.0."""
from __future__ import annotations

import re
from typing import Any, Iterable

from tkinter import messagebox
import tkinter as tk
from tkinter import ttk


MATERIAL_CLASSES = (
    "AA/Chemical",
    "Coupling reagent",
    "Catalyst/additive",
    "Base",
    "Solvent",
    "Cleavage cocktail",
    "Resin",
    "Other",
)

_COLUMN_CLASSES = {
    "Unit name": ("AA/Chemical", "Other"),
    "Reagent 1": ("Coupling reagent",),
    "Reagent 2 / catalyst": ("Catalyst/additive",),
    "Base": ("Base",),
    "Coupling solvent": ("Solvent",),
}


def canonical_name(value: Any) -> str:
    return str(value or "").strip()


def material_key(value: Any) -> str:
    return re.sub(
        r"[^0-9a-z가-힣]+", "", canonical_name(value).lower(),
    )


def _variable(gui: Any, name: str, default: str) -> Any:
    variable = getattr(gui, name, None)
    if variable is None:
        variable = tk.StringVar(master=gui, value=default)
        setattr(gui, name, variable)
    return variable


def initialize(gui: Any) -> dict[str, dict[str, str]]:
    if not isinstance(getattr(gui, "custom_materials", None), dict):
        gui.custom_materials = {}
    _variable(gui, "custom_material_name", "")
    _variable(gui, "custom_material_class", "AA/Chemical")
    _variable(gui, "custom_material_mw", "")
    _variable(gui, "custom_material_density", "")
    _variable(gui, "custom_material_note", "")
    return gui.custom_materials


def _number_text(value: Any, label: str) -> str:
    text = canonical_name(value)
    if text:
        try:
            float(text.replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be numeric or blank.") from exc
    return text


def store_record(
    gui: Any,
    *,
    name: Any,
    material_class: Any = "Other",
    mw: Any = "",
    density: Any = "",
    note: Any = "",
) -> dict[str, str]:
    """Validate and store one real custom-material record."""
    materials = getattr(gui, "custom_materials", None)
    if not isinstance(materials, dict):
        materials = {}
        gui.custom_materials = materials
    clean_name = canonical_name(name)
    if not clean_name:
        raise ValueError("Material name is required.")
    clean_class = canonical_name(material_class) or "Other"
    if clean_class not in MATERIAL_CLASSES:
        raise ValueError(f"Unknown material class: {clean_class}")
    record = {
        "name": clean_name,
        "class": clean_class,
        "mw": _number_text(mw, "MW"),
        "density": _number_text(density, "Density"),
        "note": canonical_name(note),
    }
    materials[material_key(clean_name)] = record
    return record


def record(gui: Any, name: Any) -> dict[str, str] | None:
    materials = getattr(gui, "custom_materials", {}) or {}
    value = materials.get(material_key(name))
    return value if isinstance(value, dict) else None


def lookup(gui: Any, name: Any) -> tuple[str, str] | None:
    value = record(gui, name)
    if value is None:
        return None
    return str(value.get("mw", "") or ""), str(value.get("density", "") or "")


def custom_options(gui: Any, material_class: str | None = None) -> list[str]:
    materials = getattr(gui, "custom_materials", {}) or {}
    names = {
        canonical_name(value.get("name"))
        for value in materials.values()
        if isinstance(value, dict)
        and (material_class is None or value.get("class") == material_class)
        and canonical_name(value.get("name"))
    }
    return sorted(names, key=str.lower)


def options_for_column(
    gui: Any,
    column: str,
    base_options: Iterable[Any] = (),
) -> list[str]:
    values = [canonical_name(value) for value in base_options]
    for material_class in _COLUMN_CLASSES.get(column, ()):
        values.extend(custom_options(gui, material_class))
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def refresh_tree(gui: Any) -> None:
    tree = getattr(gui, "custom_material_tree", None)
    if tree is None:
        return
    columns = ("name", "class", "mw", "density", "note")
    tree.configure(columns=columns, show="headings")
    widths = {"name": 230, "class": 150, "mw": 90, "density": 110, "note": 300}
    for column in columns:
        tree.heading(column, text=column)
        tree.column(
            column,
            width=widths[column],
            minwidth=70,
            anchor="w",
            stretch=False,
        )
    for item_id in tree.get_children():
        tree.delete(item_id)
    materials = getattr(gui, "custom_materials", {}) or {}
    ordered = sorted(
        (value for value in materials.values() if isinstance(value, dict)),
        key=lambda value: (
            str(value.get("class", "")),
            str(value.get("name", "")).lower(),
        ),
    )
    for value in ordered:
        tree.insert(
            "",
            "end",
            values=[value.get(column, "") for column in columns],
        )


def refresh_setup_comboboxes(gui: Any) -> None:
    """Immediately add custom records to matching visible setup selectors."""
    def walk(widget: Any):
        yield widget
        try:
            for child in widget.winfo_children():
                yield from walk(child)
        except Exception:
            return

    for widget in walk(gui):
        if not isinstance(widget, ttk.Combobox):
            continue
        try:
            values = [str(value) for value in (widget.cget("values") or ())]
            joined = "|".join(values)
            additions: list[str] = []
            if any(token in joined for token in ("DIC", "HBTU", "HOBt", "Anhydrous", "hydrate")):
                additions += custom_options(gui, "Coupling reagent")
                additions += custom_options(gui, "Catalyst/additive")
            if any(token in joined for token in ("DIEA", "DIPEA")):
                additions += custom_options(gui, "Base")
            if any(token in joined for token in ("DMF", "NMP", "DCM")):
                additions += custom_options(gui, "Solvent")
            if additions:
                widget.configure(
                    values=options_for_column(gui, "", values + additions),
                )
        except Exception:
            pass


def add_or_update(gui: Any) -> dict[str, str] | None:
    initialize(gui)
    try:
        value = store_record(
            gui,
            name=gui.custom_material_name.get(),
            material_class=gui.custom_material_class.get(),
            mw=gui.custom_material_mw.get(),
            density=gui.custom_material_density.get(),
            note=gui.custom_material_note.get(),
        )
    except ValueError as exc:
        try:
            messagebox.showerror("Custom material", str(exc))
        except Exception:
            pass
        return None
    refresh_tree(gui)
    refresh_setup_comboboxes(gui)
    try:
        gui.save_autosave_state()
    except Exception:
        pass
    return value


def delete_selected(gui: Any) -> list[str]:
    tree = getattr(gui, "custom_material_tree", None)
    if tree is None:
        return []
    removed: list[str] = []
    for item_id in list(tree.selection()):
        values = list(tree.item(item_id, "values"))
        if values:
            name = canonical_name(values[0])
            if getattr(gui, "custom_materials", {}).pop(material_key(name), None) is not None:
                removed.append(name)
    refresh_tree(gui)
    refresh_setup_comboboxes(gui)
    try:
        gui.save_autosave_state()
    except Exception:
        pass
    return removed


def load_selected(gui: Any, _event: Any = None) -> dict[str, str] | None:
    tree = getattr(gui, "custom_material_tree", None)
    if tree is None or not tree.selection():
        return None
    values = list(tree.item(tree.selection()[0], "values"))
    values += [""] * (5 - len(values))
    names = (
        "custom_material_name",
        "custom_material_class",
        "custom_material_mw",
        "custom_material_density",
        "custom_material_note",
    )
    for name, value in zip(names, values):
        getattr(gui, name).set(value)
    return record(gui, values[0])


def _setup_notebook(gui: Any) -> Any:
    def walk(widget: Any) -> Any:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook):
                labels = [str(child.tab(tab_id, "text")) for tab_id in child.tabs()]
                if "Unit defaults" in labels and "Reagents" in labels:
                    return child
            result = walk(child)
            if result is not None:
                return result
        return None

    return walk(gui)


def restore_tab(gui: Any) -> Any:
    """Build the accepted Custom DB tab without legacy patch callbacks."""
    initialize(gui)
    notebook = _setup_notebook(gui)
    if notebook is None:
        return None
    for tab_id in notebook.tabs():
        if str(notebook.tab(tab_id, "text")) == "Custom DB":
            gui._v245_custom_tab_added = True
            refresh_tree(gui)
            refresh_setup_comboboxes(gui)
            return tab_id

    frame = ttk.Frame(notebook, padding=6)
    notebook.add(frame, text="Custom DB")
    gui._v245_custom_tab_added = True
    for column in range(8):
        frame.columnconfigure(column, weight=1)
    ttk.Label(frame, text="Material name").grid(row=0, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(frame, textvariable=gui.custom_material_name, width=28).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    ttk.Label(frame, text="Class").grid(row=0, column=2, sticky="w", padx=4, pady=3)
    ttk.Combobox(
        frame,
        textvariable=gui.custom_material_class,
        values=MATERIAL_CLASSES,
        state="readonly",
        width=20,
    ).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
    ttk.Label(frame, text="MW").grid(row=1, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(frame, textvariable=gui.custom_material_mw, width=16).grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    ttk.Label(frame, text="Density(g/mL)").grid(row=1, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(frame, textvariable=gui.custom_material_density, width=16).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
    ttk.Label(frame, text="Note").grid(row=2, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(frame, textvariable=gui.custom_material_note, width=60).grid(
        row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=3,
    )
    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=0, columnspan=4, sticky="w", pady=4)
    ttk.Button(
        buttons, text="Add / Update material", command=gui.add_custom_material,
    ).pack(side="left", padx=3)
    ttk.Button(
        buttons, text="Delete selected material", command=gui.delete_custom_material,
    ).pack(side="left", padx=3)
    tree = ttk.Treeview(frame, height=8)
    gui.custom_material_tree = tree
    tree.grid(row=4, column=0, columnspan=8, sticky="nsew", padx=4, pady=4)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    horizontal.grid(row=5, column=0, columnspan=8, sticky="ew")
    vertical.grid(row=4, column=8, sticky="ns")
    frame.rowconfigure(4, weight=1)
    tree.bind("<<TreeviewSelect>>", gui.load_custom_material_selection)
    refresh_tree(gui)
    refresh_setup_comboboxes(gui)
    return frame


__all__ = [
    "MATERIAL_CLASSES",
    "add_or_update",
    "canonical_name",
    "custom_options",
    "delete_selected",
    "initialize",
    "load_selected",
    "lookup",
    "material_key",
    "options_for_column",
    "record",
    "refresh_setup_comboboxes",
    "refresh_tree",
    "restore_tab",
    "store_record",
]
