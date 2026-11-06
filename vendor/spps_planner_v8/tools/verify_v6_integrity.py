"""V6 development integrity checks shared by Public and Private builds."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT/'apps'/'spps_planner_app'):
    if str(path) not in sys.path: sys.path.insert(0,str(path))


def verify_all() -> None:
    from spps_planner import build_profile
    from spps_planner.version import VERSION, VERSION_NUMBER
    from suite_gui import data_system, experimental_data, experimental_workflow, risk_engine
    from suite_gui import v6_features
    if VERSION != 'V6.0.0' or VERSION_NUMBER != '6.0.0':
        raise RuntimeError('V6 runtime version mismatch')
    if experimental_data.SCHEMA_VERSION < 9:
        raise RuntimeError('V6 experimental DB schema migration is missing')
    if not str(risk_engine.ENGINE_VERSION).startswith('6.0.0'):
        raise RuntimeError('V6 sequence risk rules are not active')
    required={'evidence_trace','compare_scenarios','execution_summary','analytics_snapshot','record_quality_issues'}
    missing=sorted(name for name in required if not hasattr(v6_features,name))
    if missing: raise RuntimeError('V6 feature helpers missing: '+', '.join(missing))
    lifecycle_required=('start_active_run','finish_active_run','repeat_active_run')
    lifecycle_missing=[name for name in lifecycle_required if not hasattr(data_system,name)]
    if lifecycle_missing: raise RuntimeError('V6 Run lifecycle helpers missing: '+', '.join(lifecycle_missing))
    workflow_required=('run_export_payload','preflight_check','finish_review','repeat_experiment','export_run_package')
    workflow_missing=[name for name in workflow_required if not hasattr(experimental_workflow,name)]
    if workflow_missing:
        raise RuntimeError('V6 Run workflow helper(s) missing: '+', '.join(workflow_missing))
    for rel in (
        'suite_gui/preflight.py', 'suite_gui/run_package.py', 'suite_gui/run_review.py',
        'suite_gui/experimental_reporting.py', 'suite_gui/modules/evidence_detail_dialog.py',
        'suite_gui/modules/classic_batch_controller.py', 'suite_gui/recommendation/__init__.py',
    ):
        if not (ROOT/rel).is_file():
            raise RuntimeError('V6 consolidated module missing: '+rel)

    # SPPS Planner release identity is SPPS-only.  The historical helper
    # function name may remain for import compatibility, but Pepforge assets or
    # fallback paths must not re-enter this package.
    legacy_icons=[ROOT/'assets'/'Pepforge_Icon.ico', ROOT/'assets'/'Pepforge_Icon.png']
    if any(path.exists() for path in legacy_icons):
        raise RuntimeError('Legacy Pepforge icon asset returned')
    icon_helper=(ROOT/'peptiforg_core'/'ui_helpers.py').read_text(encoding='utf-8')
    if 'Pepforge_Icon.' in icon_helper:
        raise RuntimeError('Legacy Pepforge icon fallback returned')

    # GUI/controller architecture must remain direct. Do not restore versioned
    # method wrapper chains or text-based action-button rebinding.
    classic_source=(ROOT/'suite_gui'/'classic_base.py').read_text(encoding='utf-8')
    batch_source=(ROOT/'suite_gui'/'modules'/'classic_batch_controller.py').read_text(encoding='utf-8')
    for token in ('_v23_','_v25_','_v26_','_old_v26'):
        if token in classic_source or token in batch_source:
            raise RuntimeError('Versioned Classic GUI wrapper returned: '+token)
    plan_source=(ROOT/'suite_gui'/'modules'/'plan_workflow.py').read_text(encoding='utf-8')
    if 'workspace_widgets._install_action_buttons(gui, ns)' in plan_source:
        raise RuntimeError('Legacy action-button installer returned to Plan workflow')
    for token in ('text == "Generate"','text == "Apply Change"','text == "Add"','text == "Duplicate"','text == "Delete"'):
        if token in plan_source:
            raise RuntimeError('Text-based action rebinding returned to Plan workflow: '+token)
    exp_workflow_source=(ROOT/'suite_gui'/'experimental_workflow.py').read_text(encoding='utf-8')
    for token in ('ml_advisor_v5.','condition_optimizer_v5.','model_registry_v5.'):
        if token in exp_workflow_source:
            raise RuntimeError('Version-specific recommendation backend leaked into V6 workflow: '+token)

    # The embedded SPPS engine must remain a single canonical pipeline. Historical
    # wrapper/alias stacks made behavior order-dependent even though they were not
    # runtime monkey patches. Do not allow that architecture to return.
    engine_source = (ROOT/'apps'/'spps_planner_app'/'spps_planner'/'engine.py').read_text(encoding='utf-8')
    forbidden_engine_fragments = ('_V219_', '_V221_', '_V222_', 'ORIG_GENERATE', 'FINAL REPAIR', 'patch-stack', 'hotfix')
    stale_engine = [token for token in forbidden_engine_fragments if token in engine_source]
    if stale_engine:
        raise RuntimeError('Embedded engine wrapper/patch stack returned: ' + ', '.join(stale_engine))
    for dead_name in ('_recommend_cleavage_preset_initial', '_generate_cleavage_cocktail_initial', '_plan_summary_initial', '_liquid_display_policy'):
        if f'def {dead_name}(' in engine_source:
            raise RuntimeError('Superseded embedded engine function returned: ' + dead_name)

    # Terminal reagent identity must stay canonical. Purpose prose must never
    # become part of the Unit/Material identity or generated terminal notes.
    from spps_planner.database import load_compounds
    from spps_planner.engine import PlanInput, generate_step_matrix, generate_step_materials, generate_materials
    from suite_gui.calculation_context import material_lookup
    compounds = load_compounds()
    nterm = compounds[compounds['Class'].astype(str).str.lower().eq('n-term modifier')]
    forbidden = (' for n-terminal', ' coupling', 'generic /', ' route /', 'vendor-form required', ' succinyl cap', 'biotinylation acid form')
    bad_names = []
    for _, row in nterm.iterrows():
        value = str(row.get('Reagent/protected form', '') or '')
        if any(token in value.lower() for token in forbidden):
            bad_names.append(f"{row.get('Token')}: {value}")
    if bad_names:
        raise RuntimeError('Non-canonical N-terminal reagent name(s): ' + '; '.join(bad_names[:10]))
    ac_input = PlanInput(sequence='Ac-EEMARR-NH2', scale_mmol=0.2, resin='Rink Amide AM', resin_loading_mmol_g=0.7)
    ac_row = generate_step_matrix(ac_input).iloc[-1]
    if str(ac_row.get('protected_reagent', '')) != 'Acetic anhydride (Ac2O)':
        raise RuntimeError('Ac terminal reagent is not canonical Acetic anhydride (Ac2O)')
    if str(ac_row.get('note', '') or '').strip() or str(ac_row.get('additive', '') or '').strip():
        raise RuntimeError('Generated Ac terminal row contains Note/additive text')
    sm = generate_step_materials(ac_input)
    sm = sm[sm['material'].astype(str).eq('Acetic anhydride (Ac2O)')]
    if len(sm) != 1 or str(sm.iloc[0].get('note', '') or '').strip():
        raise RuntimeError('Ac step-material row is not clean/canonical')
    totals = generate_materials(ac_input)
    totals = totals[totals['reagent'].astype(str).eq('Acetic anhydride (Ac2O)')]
    if len(totals) != 1 or str(totals.iloc[0].get('warning', '') or '').strip():
        raise RuntimeError('Ac total-material row is not clean/canonical')
    mw, density = material_lookup('Acetic anhydride (Ac2O) for N-terminal acetylation')
    if abs(float(mw) - 102.09) > 1e-9 or abs(float(density) - 1.08) > 1e-9:
        raise RuntimeError('Legacy Ac2O alias no longer resolves exact MW/density')
    panel=(ROOT/'suite_gui'/'modules'/'experimental_data_panel.py').read_text(encoding='utf-8')
    stale_visible=('V5 Loading Model','Empirical V5 estimate')
    stale=[token for token in stale_visible if token in panel]
    if stale: raise RuntimeError('Stale user-visible V5 label(s) remain in V6 panel: '+', '.join(stale))
    seed=ROOT/'apps'/'spps_planner_app'/'data'/'experimental_seed'
    if not build_profile.IS_PRIVATE:
        unsafe=[p.name for p in seed.iterdir() if p.is_file() and p.name.lower()!='readme.md'] if seed.is_dir() else []
        if unsafe: raise RuntimeError('Public experimental seed contains non-documentation files: '+', '.join(sorted(unsafe)))
        for name in ('experimental_v5.sqlite','experimental_v6.sqlite'):
            if any(ROOT.rglob(name)):
                raise RuntimeError(f'Public source package contains local experimental DB: {name}')
    print(f"[OK] V6 integrity: flavor={build_profile.BUILD_FLAVOR}, schema={experimental_data.SCHEMA_VERSION}")

if __name__=='__main__':
    verify_all()
