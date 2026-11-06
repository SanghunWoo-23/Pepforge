"""Regression: opening Recommendations must not change the Plan Treeview fonts."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

from suite_gui.modules.experimental_data_panel import ExperimentalDataWindow


def test_history_styles_do_not_override_main_plan_headers():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is not available on this runner")
    try:
        root.withdraw()
        style = ttk.Style(root)
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        before_header = style.lookup("Treeview.Heading", "font")
        before_body = style.lookup("Treeview", "font")
        before_height = style.lookup("Treeview", "rowheight")

        rec = tk.Toplevel(root)
        try:
            ExperimentalDataWindow._configure_styles(rec)
            assert style.lookup("Treeview.Heading", "font") == before_header
            assert style.lookup("Treeview", "font") == before_body
            assert style.lookup("Treeview", "rowheight") == before_height
            assert style.lookup("SPPS.History.Treeview.Heading", "font")
            area = ttk.Frame(rec)
            area.pack()
            table = ExperimentalDataWindow._tree(rec, area, ["Unit name", "MW"])
            assert table.cget("style") == "SPPS.History.Treeview"
            assert style.lookup("Treeview.Heading", "font") == before_header
        finally:
            rec.destroy()
    finally:
        root.destroy()


def test_recommendation_panel_never_configures_global_treeview_style():
    source = (Path(__file__).resolve().parents[1] / "suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    assert 'style.configure("Treeview",' not in source
    assert 'style.configure("Treeview.Heading",' not in source
    assert 'style="SPPS.History.Treeview"' in source
