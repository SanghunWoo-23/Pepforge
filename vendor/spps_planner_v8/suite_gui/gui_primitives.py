"""Reusable Tk primitives shared by the SPPS Planner desktop controller."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from tkinter import ttk


class StaticValue:
    """Tk-free fallback exposing the small ``.get()`` API used by UI code."""

    __slots__ = ("_value",)

    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value


def const_var(value=None):
    """Return a Tk-free constant with a ``tk.Variable``-compatible getter."""

    return StaticValue(value)


def open_path(path: Path) -> None:
    """Open a local path with the platform's default application."""

    if os.name == "nt":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def bind_combobox_first_letter_jump(combo):
    """Bind cycling first-letter navigation to a ``ttk.Combobox``."""

    try:
        if not isinstance(combo, ttk.Combobox):
            return combo
        combo._letter_jump_last = (None, -1)

        def jump(event):
            char = getattr(event, "char", "") or ""
            if len(char) != 1 or not char.isalpha() or not char.isascii():
                return None
            values = list(combo.cget("values") or [])
            if not values:
                return None
            key = char.lower()
            last_key, last_position = getattr(
                combo,
                "_letter_jump_last",
                (None, -1),
            )
            start = last_position + 1 if last_key == key else 0
            ordered = list(range(start, len(values))) + list(range(0, start))
            for index in ordered:
                if str(values[index]).lower().startswith(key):
                    combo.set(values[index])
                    combo._letter_jump_last = (key, index)
                    try:
                        combo.event_generate("<<ComboboxSelected>>")
                    except Exception:
                        pass
                    return "break"
            return None

        combo.bind("<KeyPress>", jump, add="+")
    except Exception:
        pass
    return combo


class EditableTree(ttk.Treeview):
    """Excel-like Treeview supporting entry and editable-combobox cells."""

    def __init__(self, master, columns, on_edit=None, combo_values=None, **kwargs):
        super().__init__(master, columns=columns, show="headings", **kwargs)
        self._on_edit = on_edit
        self._edit_entry = None
        self._combo_values = combo_values or {}
        for column in columns:
            self.heading(column, text=column)
            self.column(
                column,
                width=180,
                minwidth=110,
                anchor="w",
                stretch=True,
            )
        self.bind("<Double-1>", self._begin_edit)

    def _begin_edit(self, event):
        if self.identify("region", event.x, event.y) != "cell":
            return
        row_id = self.identify_row(event.y)
        column_id = self.identify_column(event.x)
        if not row_id or not column_id:
            return
        column_index = int(column_id.replace("#", "")) - 1
        columns = list(self["columns"])
        if column_index < 0 or column_index >= len(columns):
            return
        column_name = columns[column_index]
        if column_name == "No":
            return
        bounds = self.bbox(row_id, column_id)
        if not bounds:
            return
        x, y, width, height = bounds
        values = list(self.item(row_id, "values"))
        old_value = values[column_index] if column_index < len(values) else ""
        if self._edit_entry is not None:
            self._edit_entry.destroy()

        choices = self._combo_values.get(column_name)
        if choices:
            editor = ttk.Combobox(self, values=choices, state="normal")
            bind_combobox_first_letter_jump(editor)
            editor.set(str(old_value))
        else:
            editor = ttk.Entry(self)
            editor.insert(0, str(old_value))
            editor.select_range(0, "end")
        editor.focus_set()
        editor.place(x=x, y=y, width=width, height=height)
        self._edit_entry = editor

        def commit(_event=None):
            new_value = editor.get()
            values[column_index] = new_value
            self.item(row_id, values=values)
            editor.destroy()
            self._edit_entry = None
            if self._on_edit:
                self._on_edit(row_id, column_name, new_value)

        def cancel(_event=None):
            editor.destroy()
            self._edit_entry = None

        def live_preview(_event=None):
            try:
                new_value = editor.get()
                live_values = list(self.item(row_id, "values"))
                live_values += [""] * max(0, len(columns) - len(live_values))
                live_values[column_index] = new_value
                self.item(row_id, values=live_values)
                if self._on_edit:
                    self._on_edit(row_id, column_name, new_value)
            except Exception:
                pass

        editor.bind("<KeyRelease>", live_preview, add="+")
        editor.bind("<<ComboboxSelected>>", live_preview, add="+")
        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)


__all__ = [
    "EditableTree",
    "StaticValue",
    "bind_combobox_first_letter_jump",
    "const_var",
    "open_path",
]
