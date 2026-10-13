"""Version-neutral runtime state ownership for the active Planner UI.

Legacy versioned attributes are synchronized only at this compatibility boundary.
Active code should use the stable accessors below. R9 extends the R8 owner to
Plan edit/re-entry and Project Manager drag state without introducing _v600 names.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

_MISSING = object()

@dataclass
class PlannerUIState:
    active_index: int | None = None
    switching: bool = False
    calculation_namespace: Any = None
    dirty_columns: dict[str, set[str]] = field(default_factory=dict)
    plan_editor: Any = None
    generating: bool = False
    applying: bool = False
    drag_start_y: int | None = None
    drag_last_target: int | None = None
    drag_selection: list[int] = field(default_factory=list)
    dragging: bool = False
    batch_tables: dict[str, Any] = field(default_factory=dict)
    work_item_window: Any = None
    density: str = "Standard"
    shortcuts: dict[str, Any] = field(default_factory=dict)
    cleavage_controls_added: bool = False
    post_cleavage_rescue_added: bool = False
    resin_alias_trace: bool = False
    volume_preview_label: Any = None
    volume_preview_after_id: Any = None
    resin_preview_traces: list[Any] = field(default_factory=list)
    unit_ui_installed: bool = False
    batch_signature: Any = None
    batch_refresh_after_id: Any = None
    batch_layout_signature: Any = None
    live_sync_after_id: Any = None
    trace_tokens: list[Any] = field(default_factory=list)
    drag_start_index: int | None = None
    drag_started: bool = False

def _normalized_index(value: Any) -> int | None:
    try: return None if value is None else int(value)
    except Exception: return None

def ensure_planner_state(gui: Any) -> PlannerUIState:
    state=getattr(gui,'planner_ui_state',None)
    if isinstance(state,PlannerUIState): return state
    legacy_index=getattr(gui,'_v229_active_index',getattr(gui,'_v228_active_index',None))
    namespace=getattr(gui,'_v229_ns',getattr(gui,'_v228_ns',None))
    state=PlannerUIState(
        active_index=_normalized_index(legacy_index),
        switching=bool(getattr(gui,'_v229_switching',getattr(gui,'_v228_switching',False))),
        calculation_namespace=namespace,
        dirty_columns=getattr(gui,'_v229_dirty_columns',{}) or {},
        generating=bool(getattr(gui,'_v229_generating',False)),
        applying=bool(getattr(gui,'_v229_applying',False)),
        dragging=bool(getattr(gui,'_v2212_dragging',False)),
        drag_start_y=getattr(gui,'_v2212_drag_start_y',None),
        drag_last_target=getattr(gui,'_v2212_drag_last_target',None),
        drag_selection=list(getattr(gui,'_v2212_drag_selection',[]) or []),
        batch_tables=getattr(gui,'_v225_batch_tables',{}) or {},
        work_item_window=getattr(gui,'_v3_work_item_window',None),
        density=str(getattr(gui,'_v3_density','Standard') or 'Standard'),
        shortcuts=getattr(gui,'_v3_shortcuts',{}) or {},
        cleavage_controls_added=bool(getattr(gui,'_v2097_cleavage_controls_added',False)),
        post_cleavage_rescue_added=bool(getattr(gui,'_v5_post_cleavage_rescue_added',False)),
        resin_alias_trace=bool(getattr(gui,'_v200_resin_alias_trace',False)),
        volume_preview_label=getattr(gui,'_v257_volume_preview_label',None),
        volume_preview_after_id=getattr(gui,'_v3_volume_preview_after_id',None),
        resin_preview_traces=list(getattr(gui,'_v200_resin_preview_traces',[]) or []),
        unit_ui_installed=bool(getattr(gui,'_v2212_unit_ui_installed',False)),
        batch_signature=getattr(gui,'_v3_batch_signature',None),
        batch_refresh_after_id=getattr(gui,'_v3_batch_refresh_after_id',None),
        batch_layout_signature=getattr(gui,'_v3_batch_layout_signature',None),
        live_sync_after_id=getattr(gui,'_v3_live_sync_after_id',None),
        trace_tokens=list(getattr(gui,'_v229_trace_tokens',getattr(gui,'_v228_trace_tokens',[])) or []),
        drag_start_index=getattr(gui,'_v2097_drag_start_index',None),
        drag_started=bool(getattr(gui,'_v2097_drag_started',False)),
    )
    setattr(gui,'planner_ui_state',state)
    _sync_all(gui,state)
    return state

def _sync_all(gui,state):
    for name in ('_v229_active_index','_v228_active_index'): setattr(gui,name,state.active_index)
    for name in ('_v229_switching','_v228_switching'): setattr(gui,name,bool(state.switching))
    for name in ('_v229_ns','_v228_ns'): setattr(gui,name,state.calculation_namespace)
    setattr(gui,'_v229_dirty_columns',state.dirty_columns)
    setattr(gui,'_v229_generating',bool(state.generating)); setattr(gui,'_v229_applying',bool(state.applying))
    setattr(gui,'_v2212_dragging',bool(state.dragging)); setattr(gui,'_v2212_drag_start_y',state.drag_start_y)
    setattr(gui,'_v2212_drag_last_target',state.drag_last_target); setattr(gui,'_v2212_drag_selection',state.drag_selection)
    setattr(gui,'_v225_batch_tables',state.batch_tables)
    setattr(gui,'_v3_work_item_window',state.work_item_window)
    setattr(gui,'_v3_density',state.density); setattr(gui,'_v3_shortcuts',state.shortcuts)
    setattr(gui,'_v2097_cleavage_controls_added',state.cleavage_controls_added); setattr(gui,'_v5_post_cleavage_rescue_added',state.post_cleavage_rescue_added)
    setattr(gui,'_v200_resin_alias_trace',state.resin_alias_trace); setattr(gui,'_v257_volume_preview_label',state.volume_preview_label)
    setattr(gui,'_v3_volume_preview_after_id',state.volume_preview_after_id); setattr(gui,'_v200_resin_preview_traces',state.resin_preview_traces)
    setattr(gui,'_v2212_unit_ui_installed',state.unit_ui_installed); setattr(gui,'_v3_batch_signature',state.batch_signature)
    setattr(gui,'_v3_batch_refresh_after_id',state.batch_refresh_after_id); setattr(gui,'_v3_batch_layout_signature',state.batch_layout_signature)
    setattr(gui,'_v3_live_sync_after_id',state.live_sync_after_id); setattr(gui,'_v229_trace_tokens',state.trace_tokens); setattr(gui,'_v228_trace_tokens',state.trace_tokens)
    setattr(gui,'_v2097_drag_start_index',state.drag_start_index); setattr(gui,'_v2097_drag_started',state.drag_started)

def get_active_index(gui,default=None):
    s=ensure_planner_state(gui)
    # compatibility callers may still modify either alias directly
    for name in ('_v229_active_index','_v228_active_index','_v2097_active_index'):
        if hasattr(gui,name):
            value=_normalized_index(getattr(gui,name))
            if value!=s.active_index:
                s.active_index=value; _sync_all(gui,s); break
    return default if s.active_index is None else s.active_index

def set_active_index(gui,value):
    s=ensure_planner_state(gui); s.active_index=_normalized_index(value); _sync_all(gui,s)
    # old batch/project selection extensions
    setattr(gui,'_v2097_active_index',s.active_index)
    return s.active_index

def is_switching(gui):
    s=ensure_planner_state(gui)
    for name in ('_v229_switching','_v228_switching','_v2212_switching'):
        if hasattr(gui,name) and bool(getattr(gui,name))!=s.switching:
            s.switching=bool(getattr(gui,name)); _sync_all(gui,s); break
    return s.switching

def set_switching(gui,value):
    s=ensure_planner_state(gui); s.switching=bool(value); _sync_all(gui,s); setattr(gui,'_v2212_switching',s.switching); return s.switching

def get_calculation_namespace(gui,default=None):
    s=ensure_planner_state(gui)
    if s.calculation_namespace is None:
        s.calculation_namespace=getattr(gui,'_v229_ns',getattr(gui,'_v228_ns',None)); _sync_all(gui,s)
    return default if s.calculation_namespace is None else s.calculation_namespace

def set_calculation_namespace(gui,namespace):
    s=ensure_planner_state(gui); s.calculation_namespace=namespace; _sync_all(gui,s); return namespace

def get_dirty_columns(gui):
    s=ensure_planner_state(gui)
    legacy=getattr(gui,'_v229_dirty_columns',s.dirty_columns)
    if legacy is not s.dirty_columns: s.dirty_columns=legacy or {}; _sync_all(gui,s)
    return s.dirty_columns

def set_dirty_columns(gui,value):
    s=ensure_planner_state(gui); s.dirty_columns=value if isinstance(value,dict) else {}; _sync_all(gui,s); return s.dirty_columns

def clear_dirty_columns(gui): return set_dirty_columns(gui,{})

def is_generating(gui):
    s=ensure_planner_state(gui); legacy=bool(getattr(gui,'_v229_generating',s.generating)); s.generating=legacy; _sync_all(gui,s); return s.generating

def set_generating(gui,value):
    s=ensure_planner_state(gui); s.generating=bool(value); _sync_all(gui,s); return s.generating

def is_applying(gui):
    s=ensure_planner_state(gui); legacy=bool(getattr(gui,'_v229_applying',s.applying)); s.applying=legacy; _sync_all(gui,s); return s.applying

def set_applying(gui,value):
    s=ensure_planner_state(gui); s.applying=bool(value); _sync_all(gui,s); return s.applying

def get_drag_state(gui): return ensure_planner_state(gui)
def update_drag_state(gui,**changes):
    s=ensure_planner_state(gui)
    for key,value in changes.items():
        if hasattr(s,key): setattr(s,key,value)
    _sync_all(gui,s); return s

def get_batch_tables(gui):
    s=ensure_planner_state(gui); legacy=getattr(gui,'_v225_batch_tables',s.batch_tables)
    if legacy is not s.batch_tables: s.batch_tables=legacy or {}; _sync_all(gui,s)
    return s.batch_tables

def set_batch_tables(gui,tables):
    s=ensure_planner_state(gui); s.batch_tables=tables if isinstance(tables,dict) else {}; _sync_all(gui,s); return s.batch_tables

def _get_legacy_synced(gui: Any, field_name: str, legacy_names: tuple[str, ...], default: Any = None):
    s=ensure_planner_state(gui)
    current=getattr(s,field_name,default)
    for name in legacy_names:
        if hasattr(gui,name):
            legacy=getattr(gui,name)
            if legacy is not current and legacy != current:
                setattr(s,field_name,legacy); _sync_all(gui,s); return legacy
    return current

def _set_synced(gui: Any, field_name: str, value: Any):
    s=ensure_planner_state(gui); setattr(s,field_name,value); _sync_all(gui,s); return value

def get_work_item_window(gui): return _get_legacy_synced(gui,'work_item_window',('_v3_work_item_window',),None)
def set_work_item_window(gui,value): return _set_synced(gui,'work_item_window',value)
def get_density(gui,default='Standard'): return _get_legacy_synced(gui,'density',('_v3_density',),default) or default
def set_density(gui,value): return _set_synced(gui,'density',str(value or 'Standard'))
def set_shortcuts(gui,value): return _set_synced(gui,'shortcuts',dict(value or {}))
def get_shortcuts(gui): return _get_legacy_synced(gui,'shortcuts',('_v3_shortcuts',),{}) or {}
def get_flag(gui,name):
    mapping={'cleavage_controls_added':('_v2097_cleavage_controls_added',),'post_cleavage_rescue_added':('_v5_post_cleavage_rescue_added',),'resin_alias_trace':('_v200_resin_alias_trace',),'unit_ui_installed':('_v2212_unit_ui_installed',)}
    return bool(_get_legacy_synced(gui,name,mapping.get(name,()),False))
def set_flag(gui,name,value): return _set_synced(gui,name,bool(value))
def get_volume_preview_label(gui): return _get_legacy_synced(gui,'volume_preview_label',('_v257_volume_preview_label',),None)
def set_volume_preview_label(gui,value): return _set_synced(gui,'volume_preview_label',value)
def get_volume_preview_after_id(gui): return _get_legacy_synced(gui,'volume_preview_after_id',('_v3_volume_preview_after_id',),None)
def set_volume_preview_after_id(gui,value): return _set_synced(gui,'volume_preview_after_id',value)
def get_resin_preview_traces(gui): return _get_legacy_synced(gui,'resin_preview_traces',('_v200_resin_preview_traces',),[]) or []
def set_resin_preview_traces(gui,value): return _set_synced(gui,'resin_preview_traces',list(value or []))
def get_batch_signature(gui): return _get_legacy_synced(gui,'batch_signature',('_v3_batch_signature',),None)
def set_batch_signature(gui,value): return _set_synced(gui,'batch_signature',value)
def get_batch_refresh_after_id(gui): return _get_legacy_synced(gui,'batch_refresh_after_id',('_v3_batch_refresh_after_id',),None)
def set_batch_refresh_after_id(gui,value): return _set_synced(gui,'batch_refresh_after_id',value)
def get_batch_layout_signature(gui): return _get_legacy_synced(gui,'batch_layout_signature',('_v3_batch_layout_signature',),None)
def set_batch_layout_signature(gui,value): return _set_synced(gui,'batch_layout_signature',value)
def get_live_sync_after_id(gui): return _get_legacy_synced(gui,'live_sync_after_id',('_v3_live_sync_after_id',),None)
def set_live_sync_after_id(gui,value): return _set_synced(gui,'live_sync_after_id',value)
def get_trace_tokens(gui): return _get_legacy_synced(gui,'trace_tokens',('_v229_trace_tokens','_v228_trace_tokens'),[]) or []
def set_trace_tokens(gui,value): return _set_synced(gui,'trace_tokens',list(value or []))
def get_tree_editor(tree):
    current=getattr(tree,'plan_editor',None)
    for name in ('_v229_editor','_v228_editor','_v257_editor','_v254_editor'):
        if hasattr(tree,name) and getattr(tree,name) is not current:
            current=getattr(tree,name); setattr(tree,'plan_editor',current); break
    return current
def set_tree_editor(tree,value):
    setattr(tree,'plan_editor',value)
    for name in ('_v229_editor','_v228_editor','_v257_editor','_v254_editor'): setattr(tree,name,value)
    return value
def get_editor_commit(editor):
    return getattr(editor,'commit_plan_edit',getattr(editor,'_v229_commit',None))
def set_editor_commit(editor,callback):
    setattr(editor,'commit_plan_edit',callback); setattr(editor,'_v229_commit',callback); return callback

_NAMESPACE_ALIASES={
'material_lookup':('_v251_lookup','_v248_lookup','_v216_lookup_mw_density','_v29_material_lookup'),
'options_for_column':('_v251_options_for_col','_v250_options_for_col','_v249_options_for_col'),
'bind_selected_plan_editor':('_v254_bind_selected_plan_editor',),
'core_tables':('_v221_core_tables','_v217_core_tables'),
'plan_input':('_v226_plan_input','_v222_plan_input','_v218_plan_input'),
'write_tree':('_v2093_write_tree',),
'recalculate_visible_row':('_v251_recalc_visible_row',),
'apply_volume_to_plan':('_v257_apply_volume_to_plan',),
'visible_plan_protocol_materials':('_v260_visible_plan_protocol_materials',),
'total_from_materials':('_v252_total_from_materials','_v251_total_from_materials'),
'refresh_checklist_protocol':('_v260_refresh_checklist_protocol',),
'schedule_batch_refresh':('_v260_schedule_batch_refresh',),
}
def namespace_callable(namespace: Any,key: str):
    ns=namespace if isinstance(namespace,dict) else getattr(namespace,'__dict__',{})
    stable=ns.get(key)
    if callable(stable): return stable
    for old in _NAMESPACE_ALIASES.get(key,()):
        candidate=ns.get(old)
        if callable(candidate): return candidate
    return None

def get_widget_flag(widget,stable_name,legacy_name,default=False):
    if hasattr(widget,stable_name): return getattr(widget,stable_name)
    value=getattr(widget,legacy_name,default); setattr(widget,stable_name,value); return value
def set_widget_flag(widget,stable_name,legacy_name,value):
    setattr(widget,stable_name,value); setattr(widget,legacy_name,value); return value
def get_resin_preview_bound(widget): return get_widget_flag(widget,"resin_preview_bound","_v200_resin_preview_bound",False)
def set_resin_preview_bound(widget,value): return set_widget_flag(widget,"resin_preview_bound","_v200_resin_preview_bound",bool(value))

__all__=[name for name in globals() if name.startswith(('get_','set_','is_','clear_','update_','ensure_'))]+['PlannerUIState']
