from __future__ import annotations

import os
from tkinter import ttk

import pytest


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _visible_toggle(gui):
    buttons = [
        widget
        for widget in _walk(gui)
        if isinstance(widget, ttk.Button)
        and str(widget.cget("text")).strip() in {"Show setup", "Hide setup"}
        and widget.winfo_viewable()
    ]
    assert len(buttons) == 1
    return buttons[0]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_setup_toggle_is_fixed_from_start_through_show_hide(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    from suite_gui.modules import plan_workflow as ctl

    ctl.messagebox.showerror = lambda *a, **k: None
    ctl.messagebox.showinfo = lambda *a, **k: None

    from suite_gui.classic_2094_tk_gui import SPPSGui

    monkeypatch.setattr(SPPSGui, "_state_file_path", lambda self: tmp_path / "state.json", raising=False)
    gui = SPPSGui()
    try:
        gui.geometry("1400x900+0+0")
        gui.deiconify()
        gui.update()

        show = _visible_toggle(gui)
        assert str(show.cget("text")) == "Show setup"
        assert show.winfo_manager() == "pack"
        initial_side = str(show.pack_info().get("side"))
        assert initial_side in {"left", "right"}
        initial = (show.winfo_rootx(), show.winfo_rooty(), show.winfo_width(), show.winfo_height())

        show.invoke()
        gui.update()
        hide = _visible_toggle(gui)
        assert str(hide.cget("text")) == "Hide setup"
        assert str(hide.pack_info().get("side")) == initial_side
        assert (hide.winfo_rootx(), hide.winfo_rooty(), hide.winfo_width(), hide.winfo_height()) == initial

        hide.invoke()
        gui.update()
        show_again = _visible_toggle(gui)
        assert str(show_again.cget("text")) == "Show setup"
        assert str(show_again.pack_info().get("side")) == initial_side
        assert (show_again.winfo_rootx(), show_again.winfo_rooty(), show_again.winfo_width(), show_again.winfo_height()) == initial
    finally:
        gui.destroy()
