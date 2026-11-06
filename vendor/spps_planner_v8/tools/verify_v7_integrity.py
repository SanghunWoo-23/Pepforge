"""V7 release integrity checks shared by Public and Private builds."""
from __future__ import annotations

from pathlib import Path
import ast
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT/'apps'/'spps_planner_app'):
    if str(path) not in sys.path: sys.path.insert(0,str(path))


def verify_production_purity() -> None:
    """Reject runtime patch stacks and stub/placeholder production implementations."""
    roots = (ROOT / "suite_gui", ROOT / "apps" / "spps_planner_app" / "spps_planner")
    violations: list[str] = []
    suspicious_def = re.compile(r"(?:placeholder|dummy|fake|stub)", re.I)
    for source_root in roots:
        for path in source_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            rel = path.relative_to(ROOT)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if suspicious_def.search(node.name):
                        violations.append(f"{rel}:{node.lineno}:suspicious function name {node.name}")
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        violations.append(f"{rel}:{node.lineno}:pass-only function {node.name}")
                    if (len(node.body) == 1 and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, ast.Constant)
                            and node.body[0].value.value is Ellipsis):
                        violations.append(f"{rel}:{node.lineno}:ellipsis-only function {node.name}")
                if isinstance(node, ast.Raise):
                    exc = node.exc
                    if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError":
                        violations.append(f"{rel}:{node.lineno}:NotImplementedError")
                    elif isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                        violations.append(f"{rel}:{node.lineno}:NotImplementedError")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "MethodType":
                        violations.append(f"{rel}:{node.lineno}:MethodType")
                    if node.func.id == "setattr" and node.args and isinstance(node.args[0], ast.Name):
                        target = node.args[0].id
                        if target[:1].isupper():
                            violations.append(f"{rel}:{node.lineno}:class setattr")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "__get__":
                    violations.append(f"{rel}:{node.lineno}:descriptor rebinding")
            lowered = source.lower()
            for marker in ("pass  # todo", "placeholder_implementation", "dummy_production", "todo_implementation"):
                if marker in lowered:
                    violations.append(f"{rel}:forbidden marker {marker}")
    if violations:
        raise RuntimeError("V7 production-purity gate failed: " + "; ".join(violations))


def verify_all() -> None:
    verify_production_purity()
    from spps_planner import build_profile
    from spps_planner.version import VERSION, VERSION_NUMBER
    from suite_gui import data_system, experimental_data, experimental_workflow, risk_engine
    from suite_gui import v6_features
    if VERSION != 'V7.0.0' or VERSION_NUMBER != '7.0.0':
        raise RuntimeError('V7 runtime version mismatch')
    if experimental_data.SCHEMA_VERSION < 9:
        raise RuntimeError('V7 inherited experimental DB schema contract is missing')
    if not str(risk_engine.ENGINE_VERSION).startswith('6.0.0'):
        raise RuntimeError('V7 inherited sequence risk rules are not active')
    required={'evidence_trace','compare_scenarios','execution_summary','analytics_snapshot','record_quality_issues'}
    missing=sorted(name for name in required if not hasattr(v6_features,name))
    if missing: raise RuntimeError('V7 compatibility feature helpers missing: '+', '.join(missing))
    lifecycle_required=('start_active_run','finish_active_run','repeat_active_run')
    lifecycle_missing=[name for name in lifecycle_required if not hasattr(data_system,name)]
    if lifecycle_missing: raise RuntimeError('V7 Run lifecycle helpers missing: '+', '.join(lifecycle_missing))
    workflow_required=('run_export_payload','preflight_check','finish_review','repeat_experiment','export_run_package')
    workflow_missing=[name for name in workflow_required if not hasattr(experimental_workflow,name)]
    if workflow_missing:
        raise RuntimeError('V7 Run workflow helper(s) missing: '+', '.join(workflow_missing))
    for rel in (
        'suite_gui/preflight.py', 'suite_gui/run_package.py', 'suite_gui/run_review.py',
        'suite_gui/experimental_reporting.py', 'suite_gui/modules/evidence_detail_dialog.py',
        'suite_gui/modules/classic_batch_controller.py', 'suite_gui/recommendation/__init__.py',
    ):
        if not (ROOT/rel).is_file():
            raise RuntimeError('V7 consolidated module missing: '+rel)

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
            raise RuntimeError('Version-specific recommendation backend leaked into V7 workflow: '+token)

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
    if stale: raise RuntimeError('Stale user-visible V5 label(s) remain in V7 panel: '+', '.join(stale))
    seed=ROOT/'apps'/'spps_planner_app'/'data'/'experimental_seed'
    if not build_profile.IS_PRIVATE:
        unsafe=[p.name for p in seed.iterdir() if p.is_file() and p.name.lower()!='readme.md'] if seed.is_dir() else []
        if unsafe: raise RuntimeError('Public experimental seed contains non-documentation files: '+', '.join(sorted(unsafe)))
        for name in ('experimental_v5.sqlite','experimental_v6.sqlite'):
            if any(ROOT.rglob(name)):
                raise RuntimeError(f'Public source package contains local experimental DB: {name}')
    # V7 must preserve the frozen V6 chemistry engine byte-for-byte.
    import hashlib
    expected_hashes = {
        ROOT/'apps'/'spps_planner_app'/'spps_planner'/'engine.py': '5cf59ad71ea1637df4768d812612a86635b31c691efc153f93ef328d736108de',
        ROOT/'tests'/'test_engine_behavior_snapshots.py': '47ea8329033c5ff88ce8cbf705d3385b20455a7872ba01bbddad88bc726cd886',
    }
    for path, expected in expected_hashes.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f'Locked V6 chemistry hash changed in V7: {path.name} {actual}')
    required_v7_ui = (
        'suite_gui/modules/add_peptide_dialog.py',
    )
    for rel in required_v7_ui:
        if not (ROOT/rel).is_file():
            raise RuntimeError('V7 Project Manager Add UI module missing: '+rel)
    if (ROOT/'suite_gui/modules/quick_synthesis_panel.py').exists():
        raise RuntimeError('Deprecated standalone Quick Synthesis panel remains in the V7 release tree')
    reference = (ROOT/'apps'/'spps_planner_app'/'data'/'spps_reagent_references'/'coupling_systems.csv').read_text(encoding='utf-8')
    if 'HBTU/NMM,HBTU,,NMM,DMF' not in reference:
        raise RuntimeError('V7 canonical HBTU/NMM reference is missing')
    print(f"[OK] V7 integrity: flavor={build_profile.BUILD_FLAVOR}, schema={experimental_data.SCHEMA_VERSION}")

if __name__=='__main__':
    verify_all()
