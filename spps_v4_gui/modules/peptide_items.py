"""Peptide Items list behavior for SPPS Planner V4.0.0.

This is now an extracted implementation, not only a wrapper around legacy
``_v2093_*`` globals.  It keeps Shift/Ctrl multi-select, Delete, Duplicate,
Ctrl+A, and drag-reorder on one stable route.
"""
from __future__ import annotations
import copy
from . import gui_common as state


def bind_peptide_items(gui, ns: dict | None = None) -> None:
    try:
        import tkinter as tk
    except Exception:
        tk = None
    lb = getattr(gui, "pm_list", None)
    if lb is None:
        return
    try:
        lb.configure(selectmode=(tk.EXTENDED if tk else "extended"), exportselection=False)
    except Exception:
        pass
    lb.bind("<Delete>", lambda e: (delete_selected(gui), "break"), add=False)
    lb.bind("<Control-a>", lambda e: (lb.selection_set(0, "end"), "break"), add=False)
    lb.bind("<ButtonPress-1>", lambda e: list_button_press(gui, e), add=False)
    lb.bind("<B1-Motion>", lambda e: list_motion(gui, e), add=False)
    lb.bind("<ButtonRelease-1>", lambda e: list_release(gui, e), add=False)


def duplicate_selected(gui, ns: dict | None = None):
    try:
        sels = state.selected_indices(gui)
        if not sels:
            return None
        state.save_active(gui)
        items = getattr(gui, "pm_items", []) or []
        new_indices: list[int] = []
        for idx in sels:
            if 0 <= idx < len(items):
                new = copy.deepcopy(items[idx])
                new["project"] = str(new.get("project") or f"Project-{idx+1:03d}") + "_copy"
                new["peptide"] = str(new.get("peptide") or f"Peptide-{idx+1:03d}") + "_copy"
                try:
                    lot = gui._generate_lot_no()
                    new["lot"] = lot; new["lot_no"] = lot
                except Exception:
                    pass
                new["status"] = "Ready"
                items.append(new)
                new_indices.append(len(items) - 1)
        gui.pm_items = items
        if new_indices:
            state.refresh_list(gui, new_indices)
            state.load_item_to_editor(gui, new_indices[0])
            state.refresh_list(gui, new_indices)
            try: gui.schedule_autosave()
            except Exception: pass
        return new_indices
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror("Duplicate peptide", str(exc))
        except Exception:
            pass
        return None


def delete_selected(gui, ns: dict | None = None):
    try:
        sels = state.selected_indices(gui)
        if not sels:
            return None
        if state.active_index(gui) not in sels:
            state.save_active(gui)
        items = getattr(gui, "pm_items", []) or []
        for idx in sorted(sels, reverse=True):
            if 0 <= idx < len(items):
                del items[idx]
        if not items:
            items = [state.blank_item(gui, 1)]
        gui.pm_items = items
        next_idx = min(sels[0], len(items) - 1)
        state.refresh_list(gui, [next_idx])
        state.load_item_to_editor(gui, next_idx)
        try: gui.schedule_autosave()
        except Exception: pass
        return next_idx
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror("Delete peptide", str(exc))
        except Exception:
            pass
        return None


def move_selected_to(gui, target: int):
    try:
        items = list(getattr(gui, "pm_items", []) or [])
        sels = state.selected_indices(gui)
        if not sels or target in sels or target < 0 or target >= len(items):
            return None
        moving = [items[i] for i in sels]
        selected_set = set(sels)
        remaining = [it for i, it in enumerate(items) if i not in selected_set]
        insert_at = target if target < min(sels) else target - sum(1 for i in sels if i < target) + 1
        insert_at = max(0, min(insert_at, len(remaining)))
        gui.pm_items = remaining[:insert_at] + moving + remaining[insert_at:]
        new_sel = list(range(insert_at, insert_at + len(moving)))
        state.refresh_list(gui, new_sel)
        state.load_item_to_editor(gui, new_sel[0])
        state.refresh_list(gui, new_sel)
        try: gui.schedule_autosave()
        except Exception: pass
        return new_sel
    except Exception:
        return None


def list_button_press(gui, event):
    try:
        idx = gui.pm_list.nearest(event.y)
        gui._v2097_drag_start_index = idx
        gui._v2097_drag_last_target = idx
        gui._v2097_drag_start_y = event.y
        gui._v2097_drag_started = False
    except Exception:
        pass
    return None


def list_motion(gui, event):
    try:
        lb = gui.pm_list
        sels = state.selected_indices(gui)
        start = getattr(gui, "_v2097_drag_start_index", None)
        if start is None or start not in sels:
            return None
        if not getattr(gui, "_v2097_drag_started", False):
            if abs(int(event.y) - int(getattr(gui, "_v2097_drag_start_y", event.y))) < 6:
                return None
            gui._v2097_drag_started = True
        target = lb.nearest(event.y)
        if target != getattr(gui, "_v2097_drag_last_target", None):
            move_selected_to(gui, target)
            gui._v2097_drag_last_target = target
        return "break"
    except Exception:
        return None


def list_release(gui, event=None):
    for attr in ("_v2097_drag_start_index", "_v2097_drag_last_target", "_v2097_drag_started"):
        try: setattr(gui, attr, None)
        except Exception: pass
    return None
