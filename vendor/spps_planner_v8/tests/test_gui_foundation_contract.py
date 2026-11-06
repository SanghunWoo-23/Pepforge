from __future__ import annotations


def test_tk_free_constant_preserves_the_legacy_get_contract():
    from suite_gui.gui_primitives import StaticValue, const_var

    marker = object()
    value = const_var(marker)
    assert isinstance(value, StaticValue)
    assert value.get() is marker


def test_static_classic_base_uses_the_shared_gui_foundation():
    from suite_gui import catalogs
    from suite_gui.classic_base import ClassicControllerBase
    from suite_gui.gui_primitives import EditableTree, StaticValue

    from suite_gui import classic_base
    assert classic_base.EditableTree is EditableTree
    assert classic_base._StaticValue is StaticValue
    assert ClassicControllerBase.PLAN_COLUMNS is catalogs.PLAN_COLUMNS
    assert ClassicControllerBase.MATERIAL_COLUMNS is catalogs.MATERIAL_COLUMNS
    assert ClassicControllerBase.REAGENT_VALUES is catalogs.REAGENT_VALUES
    assert ClassicControllerBase.CATALYST_VALUES is catalogs.CATALYST_VALUES
    assert ClassicControllerBase.BASE_VALUES is catalogs.BASE_VALUES
    assert ClassicControllerBase.DEPRO_VALUES is catalogs.DEPRO_VALUES
    assert ClassicControllerBase.RATIO_VALUES is catalogs.RATIO_VALUES
    assert ClassicControllerBase.SOLVENT_VALUES is catalogs.SOLVENT_VALUES
    assert ClassicControllerBase.MW_FALLBACK is catalogs.MW_FALLBACK
    assert ClassicControllerBase.LIQUID_DENSITY is catalogs.LIQUID_DENSITY
    assert (
        ClassicControllerBase.AA_LIKE_LINKER_TOKENS
        is catalogs.AA_LIKE_LINKER_TOKENS
    )
    assert (
        ClassicControllerBase.CHEMICAL_LABEL_TOKENS
        is catalogs.CHEMICAL_LABEL_TOKENS
    )
    assert (
        ClassicControllerBase.CHEMICAL_DISPLAY_NAMES
        is catalogs.CHEMICAL_DISPLAY_NAMES
    )


def test_session_foundation_remains_in_the_final_controller_mro():
    from suite_gui.controller import SPPSGui
    from suite_gui.session_state import SessionStateMixin

    assert SessionStateMixin in SPPSGui.__mro__
    assert callable(SPPSGui._collect_state)
    assert callable(SPPSGui.load_autosave_state)
    assert callable(SPPSGui.on_close)


def test_static_unit_key_remains_static_through_final_class_inheritance():
    """Regression for the Windows startup parse error caused by descriptor loss."""
    import inspect

    from suite_gui.classic_base import ClassicBaseCore, ClassicControllerBase

    assert isinstance(inspect.getattr_static(ClassicBaseCore, "_unit_key"), staticmethod)
    assert isinstance(inspect.getattr_static(ClassicControllerBase, "_unit_key"), staticmethod)
    assert ClassicControllerBase._unit_key("Fmoc-Lys(Boc)-OH") == "FMOCLYSBOCOH"

    instance = object.__new__(ClassicControllerBase)
    assert instance._unit_key("Ac / acetyl cap") == "ACACETYLCAP"
    assert instance._normalize_unit_display_name("Ac") == "Acetic anhydride (Ac2O)"
    assert instance._is_ac_unit("Ac") is True
