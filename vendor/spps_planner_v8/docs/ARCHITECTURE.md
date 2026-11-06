# SPPS Planner V8.0.0 — Source Architecture

## Canonical application flow

```text
main_launcher.py
  → suite_gui.spps_tk_gui
  → suite_gui.release
  → suite_gui.controller.SPPSGui
  → Project Manager / Batch Manager / Work Item views
```

Project Manager: **Add/Edit peptide → Sequence + Resin + Scale + Loading + Exact bottles → Generate**, or **Auto Plan (Optional) → Review → Generate Full Plan**. The generated synthesis Plan is connected to Materials, Checklist, Total Materials, Cleavage and Workup. The operator can edit the Plan and use Apply Change without changing the underlying engine.

## Core source paths

- `suite_gui/modules/project_manager_panel.py`, `suite_gui/project_workflow.py`: Project Manager and editable setup.
- `suite_gui/auto_plan_option_v8.py`: optional preview and confirmation before generation.
- `suite_gui/modules/batch_manager_panel.py`, `suite_gui/batch_workflow.py`: independent batch material preparation.
- `suite_gui/sequence_risk_map_v8.py`, `suite_gui/sequence_risk_ui_v8.py`: rule-based, residue-level screening.
- `suite_gui/recommendation/`, `suite_gui/v8_decision_support.py`: evidence-aware advice; does not autonomously impose new synthesis conditions.
- `suite_gui/state_persistence.py`, `suite_gui/persistence_workflow.py`: JSON validation, atomic saves, backup and conflict handling.
- `apps/spps_planner_app/spps_planner/engine.py`: existing chemistry calculation core. Changes here require dedicated chemistry-regression tests.
- `apps/spps_planner_app/data/`: shared reagent references and an empty public actual-runs template.
- `tests/`, `tools/`: regression and release integrity checks.

## Scientific and data boundaries

Rule-based sequence warnings are not observed failure probabilities. Chemistry defaults, operator-approved conditions, and historical laboratory evidence are distinct classes. Public releases exclude Private seed/history artifacts, database files and user runtime records. Source tests are not Windows installer verification.

See `README.md` / `README_KO.md` and `docs/WINDOWS_BUILD_KO.md`.
