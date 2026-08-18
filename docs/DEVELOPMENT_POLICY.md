# Pepforge Development Policy

## Non-negotiable principles

### 1. No monkey patch architecture
Do not repair features by replacing classes/functions at runtime or attaching ad-hoc methods after construction. Fix the owning module/class through ordinary source code.

### 2. No placeholders disguised as functionality
A visible button must lead to real behavior or clearly state that the capability is unavailable. Placeholder output must not be presented as scientific result.

### 3. Preserve working features
Refactoring should not silently remove existing user-visible behavior. If behavior must change, document the change and test the affected workflow.

### 4. No fabricated scientific numbers
Every quantitative scientific parameter should have an explicit source or a clearly documented estimation method. Unsupported values remain unsupported.

### 5. Fail visibly
GUI callbacks should expose validation failures and operational errors through useful user-facing messages and logs. A windowed build must not fail silently because a console is absent.

### 6. Lightweight by default
Keep core runtime dependencies focused. Large optional ML/research dependencies should remain optional unless they are required for a core path.

### 7. Windows-first, source-friendly
Changes should remain compatible with the supported source launcher and the maintained Windows packaging path.

## Definition of done

A feature is done when:

```text
UI/input
→ callback
→ validation
→ core logic
→ output/result
→ error path
```

has been checked at the relevant level, not merely when the module imports.
