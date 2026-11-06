from __future__ import annotations

import os

import pytest

from spps_planner.engine import (
    PlanInput,
    generate_cleavage_cocktail,
    generate_step_materials,
    generate_step_reagent_plan,
)


def _aa_plan(inp: PlanInput):
    plan = generate_step_reagent_plan(inp)
    names = plan["protected_reagent"].astype(str)
    return plan[names.str.startswith("Fmoc-") & ~names.str.lower().eq("fmoc removal")]


def test_ctc_synthesizer_uses_the_entire_written_sequence_everywhere():
    inp = PlanInput(
        sequence="AEKIRKELEKQ",
        scale_mmol=0.2,
        resin="CTC(합성기)",
        resin_loading_mmol_g=1.39,
        apply_resin_loading=False,
        default_coupling_reagent="HBTU",
        default_reagent_eq=10,
        default_catalyst="",
        default_catalyst_eq=0,
        default_base="DIEA",
        default_base_eq=5,
        default_reaction_solvent="NMP",
    )
    plan = _aa_plan(inp)
    assert len(plan) == 11
    assert plan.iloc[0]["protected_reagent"] == "Fmoc-Gln(Trt)-OH"
    assert not plan["phase"].astype(str).str.lower().eq("loading").any()

    materials = generate_step_materials(inp)
    assert not materials["phase"].astype(str).str.lower().eq("loading").any()
    assert "Fmoc-Gln(Trt)-OH" in set(materials["material"].astype(str))


def test_cleavage_selected_preset_name_states_actual_components():
    inp = PlanInput(
        sequence="GHK",
        scale_mmol=1.0,
        resin="Rink Amide AM",
        resin_loading_mmol_g=0.8,
        cleavage_preset="DEFAULT_TFA_TIS_WATER",
    )
    cocktail = generate_cleavage_cocktail(inp)
    selected = str(cocktail.iloc[0]["selected_preset"])
    assert "TFA=95" in selected
    assert "TIS=2.5" in selected
    assert "water=2.5" in selected.lower()
    assert "Rink" not in selected and "CTC" not in selected


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_gui_starts_with_one_blank_item_and_final_title():
    from suite_gui.spps_tk_gui import SPPSGui

    app = SPPSGui()
    app.withdraw()
    app.update_idletasks()
    try:
        assert app.title() == "SPPS Planner V8.0.0"
        assert len(app.pm_items) == 1
        assert app.pm_list.size() == 1
        assert app.pm_sequence.get() == ""
        assert not app.pm_selected_plan_tree.get_children()
    finally:
        app.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_gui_resin_choices_have_only_ctc_synthesizer():
    from tkinter import ttk
    from suite_gui.spps_tk_gui import SPPSGui

    app = SPPSGui()
    app.withdraw()
    try:
        app.update_idletasks()
        assert "CTC(합성기)" in app.RESIN_VALUES
        assert "CTC(합성용)" not in app.RESIN_VALUES

        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        resin_combos = []
        for widget in walk(app):
            if isinstance(widget, ttk.Combobox):
                values = [str(v) for v in widget.cget("values")]
                if any("CTC" in v or "Rink Amide" in v for v in values):
                    resin_combos.append(values)
        assert resin_combos
        assert all("CTC(합성기)" in values for values in resin_combos)
        assert all("CTC(합성용)" not in values for values in resin_combos)

        app.pm_resin.set("CTC(합성용)")
        app.update_idletasks()
        assert app.pm_resin.get() == "CTC(합성기)"
    finally:
        app.destroy()
