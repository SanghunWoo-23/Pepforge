# Pepforge Public API Contract

Stable import module:

```python
from peptiforg_core.public_api import *
```

Public functions include:

```text
new_project_session
save_project_session
load_project_session
mark_stage
export_session_summary
default_workflow_config
save_workflow_config
load_workflow_config
run_workflow
build_candidate_dashboard
export_candidate_dashboard
make_experimental_template
export_experimental_import_package
export_evidence_engine_report
export_evidence_engine_report_from_project
export_run_comparison_package
```

Scientific boundary:

```text
screening / prioritization / planning / evidence organization: allowed
final Kd proof: blocked
true binder proof: blocked
replacement for external docking/MD engines: blocked
experimental validation bypass: blocked
```

Additional v4.0.2 public function:

```text
run_runtime_validation
```

Additional v4.0.3 public function:

```text
audit_package
```

Additional v4.0.4 public function:

```text
run_regression_audit
```

Additional v4.0.5 public function:

```text
audit_release_integrity
```

Additional v4.0.6 public function:

```text
verify_release_matrix
```

Additional v4.0.7 public function:

```text
release_gate_check
```
