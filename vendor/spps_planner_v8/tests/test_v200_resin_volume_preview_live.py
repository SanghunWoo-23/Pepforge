from __future__ import annotations

import os
import tkinter.ttk as ttk

import pytest


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_resin_combobox_selection_immediately_updates_volume_preview(monkeypatch, tmp_path):
    """The real Resin combobox selection event must update the yellow preview immediately."""
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
        gui.withdraw()
        gui.pm_scale.set("0.2")
        gui.pm_copies.set("1")
        gui.amide_ml_per_mmol.set("8")
        gui.ctc_ml_per_mmol.set("4")
        gui.solvent_volume_mode.set("resin_factor")
        gui.update()

        target_var = str(gui.pm_resin)
        resin_boxes = [
            w for w in _walk(gui)
            if isinstance(w, ttk.Combobox) and str(w.cget("textvariable")) == target_var
        ]
        assert len(resin_boxes) == 1
        resin_box = resin_boxes[0]
        values = list(resin_box.cget("values"))

        resin_box.current(values.index("Rink Amide AM"))
        resin_box.event_generate("<<ComboboxSelected>>")
        gui.update()
        amide_text = str(gui._v257_volume_preview_label.cget("text"))
        assert "1.6 mL" in amide_text
        assert "Amide/Rink" in amide_text
        assert "× 8 mL/mmol" in amide_text

        # No Generate / Apply Change / tab switch here: the selection itself is the trigger.
        resin_box.current(values.index("2-CTC"))
        resin_box.event_generate("<<ComboboxSelected>>")
        gui.update()
        ctc_text = str(gui._v257_volume_preview_label.cget("text"))
        assert "0.8 mL" in ctc_text
        assert "2-CTC/Trityl" in ctc_text
        assert "× 4 mL/mmol" in ctc_text
    finally:
        gui.destroy()
