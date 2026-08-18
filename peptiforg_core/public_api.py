
from __future__ import annotations

"""Pepforge Public API v3.0.0.

Stable public import surface for the research release.  This module intentionally
re-exports high-level functions that are safe for scripts and documentation.

Scientific boundary:
Pepforge supports screening, planning, triage, and evidence organization. It does
not prove final Kd, true binding, or replace external docking/MD/experimental validation.
"""

PUBLIC_API_VERSION = "3.0.0"

from peptiforg_core.project_session_manager import (
    new_project_session,
    save_project_session,
    load_project_session,
    mark_stage,
    export_session_summary,
)
from peptiforg_core.workflow_automation_runner import (
    default_workflow_config,
    save_workflow_config,
    load_workflow_config,
    run_workflow,
)
from peptiforg_core.candidate_comparison_dashboard import (
    build_candidate_dashboard,
    export_candidate_dashboard,
)
from peptiforg_core.experimental_data_importer import (
    make_experimental_template,
    export_experimental_import_package,
)
from peptiforg_core.evidence_engine import (
    export_evidence_engine_report,
    export_evidence_engine_report_from_project,
)
from peptiforg_core.run_comparison import (
    export_run_comparison_package,
)
from peptiforg_core.runtime_validation import run_runtime_validation

__all__ = [
    "PUBLIC_API_VERSION",
    "new_project_session",
    "save_project_session",
    "load_project_session",
    "mark_stage",
    "export_session_summary",
    "default_workflow_config",
    "save_workflow_config",
    "load_workflow_config",
    "run_workflow",
    "build_candidate_dashboard",
    "export_candidate_dashboard",
    "make_experimental_template",
    "export_experimental_import_package",
    "export_evidence_engine_report",
    "export_evidence_engine_report_from_project",
    "export_run_comparison_package",
    "run_runtime_validation",
    "audit_package",
    "run_regression_audit",
    "audit_release_integrity",
    "verify_release_matrix",
    "release_gate_check",
]

from peptiforg_core.full_package_audit import audit_package

from peptiforg_core.regression_audit import run_regression_audit

from peptiforg_core.release_integrity import audit_release_integrity

from peptiforg_core.release_verify_matrix import verify_release_matrix

from peptiforg_core.release_gate import release_gate_check
