# Contributing to SPPS Planner

SPPS Planner V8.0.0 is the current public source release. Contributions should improve the existing application **in place** while preserving accepted calculation, workflow, evidence, privacy, and Windows release contracts. Historical R7–R16 development notes document how the final V6 release was stabilized.

## Development setup

From the repository root:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python main_launcher.py
```

## Before changing code

Please keep these rules in mind:

1. Do not rewrite the application from scratch to solve a local issue.
2. Preserve accepted functionality unless the change explicitly intends to replace it and includes regression coverage.
3. Improve existing workflows instead of adding duplicate tabs/modules/recommendation engines for the same job.
4. Do not add runtime monkey patches, placeholder implementations, dummy training data, or fake experimental history.
5. Do not silently replace a working route with a simplified imitation.
6. Keep planned conditions separate from actual measured experimental evidence.
7. Keep model rebuilding explicit; do not retrain after every new result.
8. Preserve exact reagent/protecting-group identity where chemistry depends on it.
9. Keep public releases free of confidential/private experimental history.
10. Preserve Windows-first release/build behavior.

## Validation

Run the complete release verification:

```bat
python tools\verify_release.py
```

For repeated release verification:

```bat
python tools\verify_release.py --passes 5
```

The verifier performs version/release checks, active-route audits, source compilation, Windows release checks, and the complete pytest suite.

You can also run focused checks:

```bat
python tools\verify_windows_release.py
python tools\audit_monkey_patches.py --active-release
python -m pytest -q
```

## Test expectations

Behavior changes should have regression coverage. Especially protect:

- Generate / Apply Change behavior;
- sequence and modified-token parsing;
- resin/loading rules;
- C-terminal behavior;
- Repeat / Doubling;
- Materials / Checklist / Total Materials;
- project/session persistence;
- Batch and Custom DB workflows;
- Cys `100 eq × count` cleavage rule and no double-add regression;
- bounded target-loading recommendations;
- explicit model rebuild / promotion / rollback;
- Run ID linkage;
- bilingual natural-language issue parsing;
- NH4I `<= 0.2 M` rescue limit;
- public data/privacy contracts;
- Windows packaging/release identity.

## Pull-request description

For a meaningful behavior change, explain:

1. the user-facing problem;
2. the old behavior;
3. the new behavior;
4. the scientific/operational reason for the change;
5. the files/modules changed;
6. the tests added or updated;
7. whether data schema/migration behavior changed;
8. whether the public/private data boundary is affected.

## Data safety

Do not commit generated EXE/Installer files, virtual environments, caches, runtime logs, local SQLite databases, model files, exports, user sessions, private data, or confidential experimental records.

See [PUBLIC_DATA_POLICY.md](PUBLIC_DATA_POLICY.md).
