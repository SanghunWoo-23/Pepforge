# Legacy embedded SPPS engine (compatibility module)

**Pepforge suite version: V6.0.0.** The primary standalone synthesis planning workflow is **SPPS Planner V8.0.0 Public** at `vendor/spps_planner_v8/`.

This `apps/spps_planner_app/` tree is preserved for legacy imports, data migration, and compatibility with older project files. It is **not** a separate Pepforge V6 installer. Do not follow historical V5 build instructions from this directory.

## Supported entry points

From the Pepforge root directory:

```bat
python main_launcher.py --tool spps
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

The launcher uses the supported SPPS V8 Public process route when available. The root build batch script handles Pepforge packaging; V8 independent build scripts remain inside `vendor/spps_planner_v8/` solely for separate planner packaging and verification.

SPPS planning is decision support; generated plans are not validated laboratory SOPs.
