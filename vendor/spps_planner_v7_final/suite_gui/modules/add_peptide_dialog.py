"""Project Manager Add-peptide dialog for SPPS Planner V7.

This module owns only the Add workflow UI.  Project Manager and Batch Manager
remain the canonical workspaces; confirming the dialog delegates to the normal
``pm_add_peptide(item)`` route.
"""
from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from suite_gui import calculation_context


COUPLING_REAGENTS = (
    "DIC", "DCC", "EDC", "EDC-HCl", "HBTU", "HATU", "HCTU", "TBTU", "TCTU",
    "TSTU", "TNTU", "PyBOP", "PyAOP", "PyBrOP", "PyClocK", "COMU",
    "DEPBT", "CDI", "Ghosez reagent",
)
# Coupling additives/catalysts only.  HOBt bottle forms are deliberately
# distinct identities: anhydrous (MW 135.13) and hydrate (MW 153.14).
ADDITIVES = (
    "", "HOBt (anhydrous)", "HOBt hydrate", "HOBt monohydrate", "HOBt", "HOAt", "Oxyma", "Oxyma Pure",
    "K-Oxyma", "Cl-HOBt", "6-Cl-HOBt", "DMAP", "NHS", "HOSu",
    "Sulfo-NHS", "HOOBt", "HOSBt",
)
BASES = (
    "", "NMM", "DIPEA", "DIEA", "TEA", "Triethylamine", "Pyridine",
    "2,4,6-Collidine", "2,6-Lutidine", "TMP",
)
SOLVENTS = ("DMF", "NMP", "DCM", "DMF/DCM", "NMP/DCM", "DMF/NMP")

# These presets are labels, not new chemistry calculations. Named Project
# chemistries are retained where compatible; exact bottle-form identity is
# always stored in the peptide item so hydrate/anhydrous forms stay distinct.
PRESETS = {
    "DIC + HOBt (anhydrous)": ("DIC/HOBt", "DIC", "HOBt (anhydrous)", "", "DMF"),
    "DIC + HOBt hydrate": ("DIC/HOBt", "DIC", "HOBt hydrate", "", "DMF"),
    "DIC + Oxyma": ("DIC/Oxyma", "DIC", "Oxyma", "", "DMF"),
    "DIC + Oxyma Pure": ("DIC/Oxyma", "DIC", "Oxyma Pure", "", "DMF"),
    "HBTU + NMM": ("HBTU/NMM", "HBTU", "", "NMM", "DMF"),
    "HBTU + HOBt (anhydrous) + DIPEA": ("HBTU/HOBt/DIPEA", "HBTU", "HOBt (anhydrous)", "DIPEA", "DMF"),
    "HBTU + HOBt hydrate + DIPEA": ("HBTU/HOBt/DIPEA", "HBTU", "HOBt hydrate", "DIPEA", "DMF"),
    "HATU + DIPEA": ("HATU/DIPEA", "HATU", "", "DIPEA", "DMF"),
    "HCTU + DIPEA": ("HCTU/DIPEA", "HCTU", "", "DIPEA", "DMF"),
    "PyBOP + DIPEA": ("PyBOP/DIPEA", "PyBOP", "", "DIPEA", "DMF"),
    "COMU + DIPEA": ("Manual", "COMU", "", "DIPEA", "DMF"),
    "EDC-HCl + HOBt (anhydrous) + NMM": ("Manual", "EDC-HCl", "HOBt (anhydrous)", "NMM", "DMF"),
    "EDC-HCl + HOBt hydrate + NMM": ("Manual", "EDC-HCl", "HOBt hydrate", "NMM", "DMF"),
    "Custom": ("Manual", "DIC", "HOBt (anhydrous)", "", "DMF"),
}


_USER_RECIPE_FILENAME = "coupling_recipe_presets.json"
_USER_RECIPE_SCHEMA = 4


def _user_recipe_path():
    """Return the per-user recipe preset path outside the installed app tree."""
    from spps_planner.user_paths import user_file
    return user_file(_USER_RECIPE_FILENAME)


def _load_user_recipe_state() -> dict[str, Any]:
    """Load recipe shortcuts plus lightweight local usage metadata.

    Schema 1 files from RC14 are accepted unchanged. Usage metadata is intentionally
    local-only and never affects Project or Batch chemistry defaults.
    """
    try:
        from suite_gui.state_persistence import read_json_with_recovery
        data, _source_path, _recovered = read_json_with_recovery(_user_recipe_path())
    except Exception:
        data = {}
    raw = data.get("recipes", {}) if isinstance(data, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    recipes: dict[str, dict[str, str]] = {}
    for name, recipe in raw.items():
        label = str(name or "").strip()
        if not label or not isinstance(recipe, dict):
            continue
        values = {
            key: str(recipe.get(key, "") or "").strip()
            for key in ("reagent", "additive", "base", "solvent")
        }
        if values["reagent"] and values["solvent"]:
            recipes[label] = values
    recent_raw = data.get("recent", []) if isinstance(data, dict) else []
    recent = []
    if isinstance(recent_raw, list):
        for name in recent_raw:
            label = str(name or "").strip()
            if label in recipes and label not in recent:
                recent.append(label)
    recent_bottles_raw = data.get("recent_bottles", {}) if isinstance(data, dict) else {}
    recent_bottles: dict[str, list[str]] = {key: [] for key in ("reagent", "additive", "base", "solvent")}
    if isinstance(recent_bottles_raw, dict):
        for key in recent_bottles:
            rows = recent_bottles_raw.get(key, [])
            if not isinstance(rows, list):
                continue
            seen = set()
            for value in rows:
                label = str(value or "").strip()
                norm = calculation_context.normalized(label)
                if label and norm and norm not in seen:
                    seen.add(norm); recent_bottles[key].append(label)
            recent_bottles[key] = recent_bottles[key][:5]
    favorites_raw = data.get("favorites", []) if isinstance(data, dict) else []
    favorites = []
    if isinstance(favorites_raw, list):
        for name in favorites_raw:
            label = str(name or "").strip()
            if label in recipes and label not in favorites:
                favorites.append(label)
    return {"recipes": recipes, "recent": recent[:5], "recent_bottles": recent_bottles, "favorites": favorites[:20]}


def _load_user_recipes() -> dict[str, dict[str, str]]:
    """Load operator-saved exact coupling bottle recipes."""
    return dict(_load_user_recipe_state()["recipes"])


def _write_user_recipes(
    recipes: dict[str, dict[str, str]],
    recent: list[str] | None = None,
    recent_bottles: dict[str, list[str]] | None = None,
    favorites: list[str] | None = None,
) -> None:
    """Atomically persist user-defined recipe shortcuts and local recent-use hints."""
    from suite_gui.state_persistence import atomic_write_json_with_backup
    clean: dict[str, dict[str, str]] = {}
    for name, recipe in sorted(recipes.items(), key=lambda row: row[0].lower()):
        label = str(name or "").strip()
        if not label or not isinstance(recipe, dict):
            continue
        clean[label] = {
            key: str(recipe.get(key, "") or "").strip()
            for key in ("reagent", "additive", "base", "solvent")
        }
    recent_clean = []
    for name in list(recent or []):
        label = str(name or "").strip()
        if label in clean and label not in recent_clean:
            recent_clean.append(label)
    if recent_bottles is None or favorites is None:
        try:
            existing_state = _load_user_recipe_state()
        except Exception:
            existing_state = {}
        if recent_bottles is None:
            existing = existing_state.get("recent_bottles", {})
            recent_bottles = existing if isinstance(existing, dict) else {}
        if favorites is None:
            rows = existing_state.get("favorites", [])
            favorites = list(rows) if isinstance(rows, list) else []
    bottles_clean: dict[str, list[str]] = {}
    for key in ("reagent", "additive", "base", "solvent"):
        rows = recent_bottles.get(key, []) if isinstance(recent_bottles, dict) else []
        seen = set(); out = []
        for value in rows:
            label = str(value or "").strip()
            norm = calculation_context.normalized(label)
            if label and norm and norm not in seen:
                seen.add(norm); out.append(label)
        bottles_clean[key] = out[:5]
    atomic_write_json_with_backup(
        _user_recipe_path(),
        {
            "schema_version": _USER_RECIPE_SCHEMA,
            "recipes": clean,
            "recent": recent_clean[:5],
            "recent_bottles": bottles_clean,
            "favorites": [x for x in list(favorites or []) if x in clean][:20],
        },
    )


def _touch_recent_bottles(recipe: dict[str, str]) -> dict[str, list[str]]:
    """Remember exact bottles only after the operator commits an Add/Edit setup."""
    state = _load_user_recipe_state()
    recents = {key: list(state.get("recent_bottles", {}).get(key, [])) for key in ("reagent", "additive", "base", "solvent")}
    for key in recents:
        label = str(recipe.get(key, "") or "").strip()
        if not label:
            continue
        norm = calculation_context.normalized(label)
        recents[key] = [x for x in recents[key] if calculation_context.normalized(x) != norm]
        recents[key].insert(0, label)
        recents[key] = recents[key][:5]
    _write_user_recipes(state["recipes"], state["recent"], recents, state.get("favorites", []))
    return recents


def _prioritize_recent_choices(values: tuple[str, ...], recent: list[str]) -> tuple[str, ...]:
    """Move recently committed exact bottles to the top without duplicating entries."""
    if not recent:
        return tuple(values)
    by_norm = {calculation_context.normalized(v): v for v in values if str(v or "").strip()}
    ordered = []
    seen = set()
    if "" in values:
        ordered.append(""); seen.add("")
    for value in recent:
        norm = calculation_context.normalized(value)
        candidate = by_norm.get(norm, str(value or "").strip())
        if candidate and norm and norm not in seen:
            seen.add(norm); ordered.append(candidate)
    for value in values:
        norm = calculation_context.normalized(value)
        token = norm if norm else ""
        if token in seen:
            continue
        seen.add(token); ordered.append(value)
    return tuple(ordered)


def _recipe_identity(recipe: dict[str, str]) -> tuple[str, str, str, str]:
    return tuple(
        calculation_context.normalized(str(recipe.get(key, "") or "").strip())
        for key in ("reagent", "additive", "base", "solvent")
    )


def _find_equivalent_recipe(recipe: dict[str, str], recipes: dict[str, dict[str, str]], exclude: str = "") -> str:
    target = _recipe_identity(recipe)
    for name, saved in recipes.items():
        if name != exclude and _recipe_identity(saved) == target:
            return name
    return ""


def _touch_user_recipe(name: str) -> dict[str, Any]:
    state = _load_user_recipe_state()
    label = str(name or "").strip()
    recent = [x for x in state["recent"] if x != label]
    if label in state["recipes"]:
        recent.insert(0, label)
    _write_user_recipes(state["recipes"], recent, state.get("recent_bottles", {}), state.get("favorites", []))
    return {"recipes": dict(state["recipes"]), "recent": recent[:5]}


def _rename_user_recipe(old_name: str, new_name: str) -> dict[str, dict[str, str]]:
    old_label = str(old_name or "").strip()
    new_label = str(new_name or "").strip()
    if not new_label:
        raise ValueError("Recipe name is required.")
    if len(new_label) > 60:
        raise ValueError("Recipe name must be 60 characters or fewer.")
    state = _load_user_recipe_state()
    recipes = state["recipes"]
    if old_label not in recipes:
        raise ValueError("The selected recipe no longer exists.")
    if new_label != old_label and new_label in recipes:
        raise ValueError(f"A recipe named '{new_label}' already exists.")
    recipe = recipes.pop(old_label)
    recipes[new_label] = recipe
    recent = [new_label if x == old_label else x for x in state["recent"]]
    favorites = [new_label if x == old_label else x for x in state.get("favorites", [])]
    _write_user_recipes(recipes, recent, state.get("recent_bottles", {}), favorites)
    return recipes


def _save_user_recipe(name: str, recipe: dict[str, str]) -> dict[str, dict[str, str]]:
    label = str(name or "").strip()
    if not label:
        raise ValueError("Recipe name is required.")
    if len(label) > 60:
        raise ValueError("Recipe name must be 60 characters or fewer.")
    values = {
        key: str(recipe.get(key, "") or "").strip()
        for key in ("reagent", "additive", "base", "solvent")
    }
    if not values["reagent"]:
        raise ValueError("Coupling reagent is required before saving a recipe.")
    if not values["solvent"]:
        raise ValueError("Solvent is required before saving a recipe.")
    state = _load_user_recipe_state()
    recipes = state["recipes"]
    recipes[label] = values
    recent = [x for x in state["recent"] if x != label]
    recent.insert(0, label)
    _write_user_recipes(recipes, recent, state.get("recent_bottles", {}), state.get("favorites", []))
    return recipes


def _toggle_user_recipe_favorite(name: str) -> tuple[bool, list[str]]:
    """Pin or unpin a saved recipe in the local Quick recipe strip."""
    label = str(name or "").strip()
    state = _load_user_recipe_state()
    if label not in state["recipes"]:
        raise ValueError("Select a saved recipe first.")
    favorites = [x for x in state.get("favorites", []) if x in state["recipes"]]
    if label in favorites:
        favorites = [x for x in favorites if x != label]
        enabled = False
    else:
        favorites.insert(0, label)
        favorites = favorites[:20]
        enabled = True
    _write_user_recipes(state["recipes"], state.get("recent", []), state.get("recent_bottles", {}), favorites)
    return enabled, favorites


def _export_user_recipes(path) -> int:
    """Export portable user recipe data without any project/private experiment state."""
    from pathlib import Path
    from suite_gui.state_persistence import atomic_write_json

    state = _load_user_recipe_state()
    payload = {
        "schema_version": _USER_RECIPE_SCHEMA,
        "export_kind": "SPPS Planner coupling recipes",
        "recipes": state.get("recipes", {}),
        "favorites": state.get("favorites", []),
    }
    atomic_write_json(Path(path), payload)
    return len(payload["recipes"])


def _unique_imported_recipe_name(name: str, recipes: dict[str, dict[str, str]]) -> str:
    base = str(name or "Imported recipe").strip() or "Imported recipe"
    if base not in recipes:
        return base
    n = 2
    while f"{base} (imported {n})" in recipes:
        n += 1
    return f"{base} (imported {n})"


def _import_user_recipes(path) -> dict[str, int]:
    """Merge a portable recipe export, never silently overwriting local recipes."""
    from pathlib import Path
    from suite_gui.state_persistence import read_json_object

    data = read_json_object(Path(path))
    raw = data.get("recipes", {}) if isinstance(data, dict) else {}
    if not isinstance(raw, dict):
        raise ValueError("This file does not contain a valid recipe collection.")

    source_favorites = {str(x or "").strip() for x in (data.get("favorites", []) if isinstance(data, dict) else []) if str(x or "").strip()}
    state = _load_user_recipe_state()
    recipes = dict(state["recipes"])
    favorites = [x for x in state.get("favorites", []) if x in recipes]
    added = renamed = skipped = invalid = 0
    for raw_name, raw_recipe in raw.items():
        name = str(raw_name or "").strip()
        if not name or not isinstance(raw_recipe, dict):
            invalid += 1
            continue
        recipe = {
            key: str(raw_recipe.get(key, "") or "").strip()
            for key in ("reagent", "additive", "base", "solvent")
        }
        if not recipe["reagent"] or not recipe["solvent"]:
            invalid += 1
            continue
        equivalent = _find_equivalent_recipe(recipe, recipes)
        if equivalent:
            if name in source_favorites and equivalent not in favorites:
                favorites.append(equivalent)
            skipped += 1
            continue
        target = name
        if target in recipes:
            target = _unique_imported_recipe_name(target, recipes)
            renamed += 1
        recipes[target] = recipe
        if name in source_favorites and target not in favorites:
            favorites.append(target)
        added += 1
    _write_user_recipes(recipes, state.get("recent", []), state.get("recent_bottles", {}), favorites)
    return {"added": added, "renamed": renamed, "skipped": skipped, "invalid": invalid}

def _delete_user_recipe(name: str) -> dict[str, dict[str, str]]:
    label = str(name or "").strip()
    state = _load_user_recipe_state()
    recipes = state["recipes"]
    if label in recipes:
        recipes.pop(label, None)
        recent = [x for x in state["recent"] if x != label]
        favorites = [x for x in state.get("favorites", []) if x != label]
        _write_user_recipes(recipes, recent, state.get("recent_bottles", {}), favorites)
    return recipes

_CACHED_OUTPUT_FIELDS = (
    "selected_plan_rows", "selected_material_rows", "selected_total_rows",
    "selected_checklist_rows", "selected_cleavage_rows",
)

_PLANNING_SIGNATURE_FIELDS = (
    "sequence", "copies", "scale", "resin", "loading", "apply_loading_calc",
    "loading_aa_eq", "loading_diea_eq", "loading_time_h", "chemistry",
    "default_reagent", "default_catalyst", "default_base",
    "default_coupling_solution_solvent", "coupling_eq",
    "default_reagent_eq", "default_reagent_count",
    "default_catalyst_eq", "default_catalyst_count",
    "default_base_eq", "default_base_count",
    "reagent_eq_follows_coupling_eq",
)


def _catalog_choices() -> dict[str, tuple[str, ...]]:
    """Merge curated Add-dialog choices with the verified reagent library.

    The dialog remains useful with a partial checkout, while a full installation
    automatically exposes newly curated coupling materials without another UI
    patch. Deprotection/scavenger-only rows are intentionally excluded from the
    coupling-additive picker.
    """
    groups = {
        "reagent": list(COUPLING_REAGENTS),
        "additive": list(ADDITIVES),
        "base": list(BASES),
        "solvent": list(SOLVENTS),
    }
    try:
        from spps_planner.database import load_reagent_library
        library = load_reagent_library()
    except Exception:
        library = None
    if library is not None and not library.empty:
        for _, row in library.iterrows():
            name = str(row.get("name", "") or "").strip()
            cls = str(row.get("class", "") or "").strip().lower()
            role = str(row.get("default_role", "") or "").strip().lower()
            notes = str(row.get("notes", "") or "").strip().lower()
            if not name:
                continue
            if "coupling reagent" in cls:
                groups["reagent"].append(name)
            elif "catalyst/additive" in cls:
                if "deprotection" not in notes and "deprotection" not in role and "scavenger" not in role:
                    groups["additive"].append(name)
            elif cls == "base" or role == "base":
                groups["base"].append(name)
            elif cls == "solvent" or role == "solvent":
                groups["solvent"].append(name)
    out = {}
    for key, values in groups.items():
        seen = set()
        ordered = []
        for value in values:
            text = str(value or "").strip()
            norm = calculation_context.normalized(text)
            if text == "":
                if key in {"additive", "base"} and "" not in seen:
                    seen.add(""); ordered.append("")
                continue
            if not norm or norm in seen:
                continue
            seen.add(norm); ordered.append(text)
        out[key] = tuple(ordered)
    return out


def _material_details(name: str) -> dict[str, str]:
    """Return exact local-library details for an operator-entered bottle name."""
    text = str(name or "").strip()
    if not text:
        return {}
    try:
        from spps_planner.database import load_reagent_library
        library = load_reagent_library()
        key = calculation_context.normalized(text)
        for _, row in library.iterrows():
            if calculation_context.normalized(row.get("name", "")) != key:
                continue
            return {
                "name": str(row.get("name", "") or "").strip(),
                "class": str(row.get("class", "") or "").strip(),
                "MW": str(row.get("MW", "") or "").strip(),
                "state": str(row.get("state", "") or "").strip(),
                "role": str(row.get("default_role", "") or "").strip(),
                "notes": str(row.get("notes", "") or "").strip(),
            }
    except Exception:
        pass
    mw, density = calculation_context.material_lookup(text)
    if mw or density:
        return {"name": text, "MW": f"{mw:g}" if mw else "", "state": "", "role": "", "notes": ""}
    return {}


def _filter_choices(values: tuple[str, ...], query: str) -> tuple[str, ...]:
    """Filter bottles by label plus known library role/class/state/notes."""
    text = str(query or "").strip()
    if not text:
        return tuple(values)
    low = text.lower()
    norm = calculation_context.normalized(text)
    matched = []
    for value in values:
        label = str(value or "")
        if not label:
            continue
        detail = _material_details(label)
        metadata = " ".join(str(detail.get(k, "") or "") for k in ("class", "role", "state", "notes"))
        haystack = f"{label} {metadata}".lower()
        normalized_haystack = calculation_context.normalized(f"{label} {metadata}")
        if low in haystack or (norm and norm in normalized_haystack):
            matched.append(label)
    return tuple(matched)


def _role_mismatch_notes(values: dict[str, str]) -> list[str]:
    """Warn when a known library bottle is placed in the wrong recipe field.

    This is advisory rather than blocking because experienced operators may have
    a deliberate nonstandard use. Unknown exact supplier labels remain allowed.
    """
    expected = {
        "reagent": ("activation", "coupling reagent"),
        "additive": ("additive", "catalyst/additive"),
        "base": ("base",),
        "solvent": ("solvent",),
    }
    field_names = {
        "reagent": "Coupling reagent",
        "additive": "Additive / catalyst",
        "base": "Base",
        "solvent": "Solvent",
    }
    notes = []
    for key, accepted in expected.items():
        name = str(values.get(key, "") or "").strip()
        if not name:
            continue
        detail = _material_details(name)
        if not detail:
            continue
        role = str(detail.get("role", "") or "").strip().lower()
        cls = str(detail.get("class", "") or "").strip().lower()
        haystack = f"{role} {cls}"
        if not any(token in haystack for token in accepted):
            actual = role or cls or "another role"
            notes.append(f"{field_names[key]}: {name} is stored in the local library as {actual}.")
    return notes


def _item_recipe_values(item: dict[str, Any]) -> dict[str, str]:
    """Read exact stored bottle identities, with conservative legacy fallbacks."""
    chemistry = str(item.get("chemistry", "") or "").strip()
    legacy = {
        "DIC/HOBt": ("DIC", "HOBt", "", "DMF"),
        "DIC/Oxyma": ("DIC", "Oxyma", "", "DMF"),
        "HBTU/NMM": ("HBTU", "", "NMM", "DMF"),
        "HBTU/HOBt/DIPEA": ("HBTU", "HOBt", "DIPEA", "DMF"),
        "HBTU/DIEA": ("HBTU", "", "DIEA", "DMF"),
        "HATU/DIPEA": ("HATU", "", "DIPEA", "DMF"),
        "HCTU/DIPEA": ("HCTU", "", "DIPEA", "DMF"),
        "PyBOP/DIPEA": ("PyBOP", "", "DIPEA", "DMF"),
    }
    fallback = legacy.get(chemistry, ("DIC", "HOBt", "", "DMF"))
    return {
        "reagent": str(item.get("default_reagent") or fallback[0]).strip(),
        "additive": str(item.get("default_catalyst") if item.get("default_catalyst") is not None else fallback[1]).strip(),
        "base": str(item.get("default_base") if item.get("default_base") is not None else fallback[2]).strip(),
        "solvent": str(item.get("default_coupling_solution_solvent") or fallback[3]).strip(),
    }


def _matching_preset(recipe: dict[str, str]) -> str:
    exact = tuple(str(recipe.get(key, "") or "").strip() for key in ("reagent", "additive", "base", "solvent"))
    for label, preset in PRESETS.items():
        if label == "Custom":
            continue
        if exact == tuple(preset[1:]):
            return label
    return "Custom"


def _material_summary(values: dict[str, str]) -> tuple[str, bool]:
    parts = []
    unknown = []
    labels = (("reagent", "Reagent"), ("additive", "Additive"), ("base", "Base"), ("solvent", "Solvent"))
    for key, label in labels:
        name = str(values.get(key, "") or "").strip()
        if not name:
            continue
        detail = _material_details(name)
        if detail:
            mw = detail.get("MW", "")
            state = detail.get("state", "")
            suffix = ", ".join(x for x in ((f"MW {mw} g/mol" if mw else ""), state) if x)
            parts.append(f"{label}: {name}" + (f" ({suffix})" if suffix else ""))
        else:
            parts.append(f"{label}: {name} (custom bottle name)")
            unknown.append(name)
    text = "  |  ".join(parts) if parts else "Choose the coupling chemicals you actually use."
    return text, bool(unknown)


def _recipe_preview(values: dict[str, str]) -> str:
    """Return one operator-friendly line for the exact coupling recipe."""
    reagent = str(values.get("reagent", "") or "").strip()
    additive = str(values.get("additive", "") or "").strip()
    base = str(values.get("base", "") or "").strip()
    solvent = str(values.get("solvent", "") or "").strip() or "DMF"
    parts = [x for x in (reagent, additive, base) if x]
    recipe = " + ".join(parts) if parts else "Choose a coupling reagent"
    if not base and reagent:
        recipe += "  (no base)"
    return f"{recipe}  ·  {solvent}"


def _live_check(values: dict[str, str]) -> tuple[bool, str, str]:
    """Validate Add-dialog essentials without changing Project/Batch state.

    Returns (ready, summary, note). Unknown bottle names are allowed because the
    user may be entering an exact supplier label; they produce a warning rather
    than blocking the Project item.
    """
    sequence = str(values.get("sequence", "") or "").strip()
    if not sequence:
        return False, "Enter a peptide sequence.", ""
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(sequence)
        residues = len(list(parsed.core_tokens or []))
        if residues < 1:
            return False, "Check the peptide sequence.", "No peptide residues were recognized."
        parse_warnings = [str(x).strip() for x in (parsed.warnings or []) if str(x).strip()]
    except Exception as exc:
        return False, "Check the peptide sequence.", str(exc)

    try:
        scale = _float(values.get("scale", ""), "Scale")
        copies = _positive_int(values.get("copies", ""), "Copies")
        loading = _float(values.get("loading", ""), "Resin loading")
    except ValueError as exc:
        return False, str(exc), ""

    resin = str(values.get("resin", "") or "").strip()
    if not resin:
        return False, "Choose a resin.", ""
    reagent = str(values.get("reagent", "") or "").strip()
    if not reagent:
        return False, "Choose a coupling reagent / activator.", ""
    solvent = str(values.get("solvent", "") or "").strip()
    if not solvent:
        return False, "Choose a coupling solvent.", "Do not leave solvent blank; exact bottle identity is part of the saved setup."

    details = []
    unknown = []
    for key in ("reagent", "additive", "base", "solvent"):
        name = str(values.get(key, "") or "").strip()
        if name and not _material_details(name):
            unknown.append(name)
    if parse_warnings:
        details.append("Sequence note: " + "; ".join(parse_warnings[:2]))
    if unknown:
        details.append("Custom bottle name (MW not in local library): " + ", ".join(unknown))
    role_notes = _role_mismatch_notes(values)
    if role_notes:
        details.append("Role check: " + "  ".join(role_notes))
    summary = f"{residues} residues  ·  {scale:g} mmol  ·  {copies} cop{'y' if copies == 1 else 'ies'}  ·  {resin}  ·  loading {loading:g} mmol/g"
    return True, summary, "  |  ".join(details)


def _review_lines(values: dict[str, str]) -> str:
    """Compact human review of the fields most likely to cause setup mistakes."""
    seq = str(values.get("sequence", "") or "").strip()
    if len(seq) > 56:
        seq = seq[:53] + "..."
    return "\n".join((
        f"Peptide: {str(values.get('project', '') or '').strip()} / {str(values.get('peptide', '') or '').strip()}",
        f"Sequence: {seq or '—'}",
        f"Scale / copies: {str(values.get('scale', '') or '').strip()} mmol × {str(values.get('copies', '') or '').strip()}",
        f"Resin / loading: {str(values.get('resin', '') or '').strip()} / {str(values.get('loading', '') or '').strip()} mmol/g"
        + ("  ·  Direct loading ON" if str(values.get("apply_loading_calc", "0")).strip().lower() in {"1", "true", "yes", "on"} else ""),
        f"Bottles: {_recipe_preview(values)}",
    ))


def _edit_change_summary(original: dict[str, Any], values: dict[str, str]) -> tuple[list[str], bool]:
    """Return operator-facing changed fields and whether recalculation is required."""
    original_values = _dialog_values_from_item(original)
    labels = {
        "project": "Project", "peptide": "Peptide name", "sequence": "Sequence",
        "scale": "Scale", "copies": "Copies", "resin": "Resin", "loading": "Loading",
        "apply_loading_calc": "Direct loading",
        "lot": "LOT No.", "reagent": "Coupling reagent", "additive": "Additive / catalyst",
        "base": "Base", "solvent": "Solvent",
    }
    planning = {"sequence", "scale", "copies", "resin", "loading", "apply_loading_calc", "reagent", "additive", "base", "solvent"}
    changed = []
    recalc = False
    for key, label in labels.items():
        before = str(original_values.get(key, "") or "").strip()
        after = str(values.get(key, "") or "").strip()
        if before != after:
            changed.append(label)
            recalc = recalc or key in planning
    return changed, recalc



def _duplicate_project_notes(gui: Any, values: dict[str, str], exclude_index: int | None = None) -> list[str]:
    """Return advisory duplicate-identity notes without treating repeated sequences as errors."""
    project = str(values.get("project", "") or "").strip()
    peptide = str(values.get("peptide", "") or "").strip()
    lot = str(values.get("lot", "") or "").strip()
    notes: list[str] = []
    for idx, row in enumerate(list(getattr(gui, "pm_items", []) or [])):
        if exclude_index is not None and idx == int(exclude_index):
            continue
        item = dict(row or {})
        other_project = str(item.get("project", "") or "").strip()
        other_peptide = str(item.get("peptide", "") or "").strip()
        other_lot = str(item.get("lot", item.get("lot_no", "")) or "").strip()
        label = " / ".join(x for x in (other_project, other_peptide) if x) or f"peptide #{idx + 1}"
        if lot and other_lot and lot.casefold() == other_lot.casefold():
            notes.append(f"LOT No. '{lot}' is already used by {label}.")
        if project and peptide and other_project.casefold() == project.casefold() and other_peptide.casefold() == peptide.casefold():
            notes.append(f"Project / peptide name already exists: {label}.")
    # Stable de-duplication if both old/new LOT fields point at the same item.
    return list(dict.fromkeys(notes))


def _dialog_snapshot(values: dict[str, str]) -> tuple[tuple[str, str], ...]:
    keys = ("project", "peptide", "sequence", "scale", "copies", "resin", "loading", "apply_loading_calc", "lot", "reagent", "additive", "base", "solvent")
    return tuple((key, str(values.get(key, "") or "").strip()) for key in keys)

def _get(gui: Any, name: str, default: str = "") -> str:
    try:
        return str(getattr(gui, name).get()).strip()
    except Exception:
        return str(default)


def _float(text: str, label: str) -> float:
    try:
        value = float(str(text).replace(",", "").strip())
    except Exception as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if value <= 0:
        raise ValueError(f"{label} must be greater than 0.")
    return value


def _positive_int(text: str, label: str) -> int:
    try:
        value = float(str(text).strip())
    except Exception as exc:
        raise ValueError(f"{label} must be a whole number.") from exc
    if value < 1 or not value.is_integer():
        raise ValueError(f"{label} must be a positive whole number.")
    return int(value)


def _default_names(gui: Any) -> tuple[str, str, str]:
    """Generate collision-free operator defaults from the current Project list."""
    items = [dict(x or {}) for x in list(getattr(gui, "pm_items", []) or [])]
    existing_pairs = {
        (str(x.get("project", "") or "").strip().casefold(), str(x.get("peptide", "") or "").strip().casefold())
        for x in items
    }
    number = max(1, len(items) + 1)
    while True:
        project = f"Project-{number:03d}"
        peptide = f"Peptide-{number:03d}"
        if (project.casefold(), peptide.casefold()) not in existing_pairs:
            break
        number += 1

    try:
        lot_base = str(gui._generate_lot_no()).strip()
    except Exception:
        lot_base = f"SPPS-{datetime.now().strftime('%y%m%d')}-{number:02d}"
    lot_base = lot_base or f"SPPS-{datetime.now().strftime('%y%m%d')}-{number:02d}"
    existing_lots = {
        str(x.get("lot", x.get("lot_no", "")) or "").strip().casefold()
        for x in items if str(x.get("lot", x.get("lot_no", "")) or "").strip()
    }
    lot = lot_base
    suffix = 2
    while lot.casefold() in existing_lots:
        lot = f"{lot_base}-{suffix:02d}"
        suffix += 1
    return project, peptide, lot


def _method_eq_defaults(gui: Any, chemistry: str) -> dict[str, str]:
    """Reuse accepted existing preset values; do not touch Batch defaults."""
    if chemistry == "DIC/HOBt":
        return {
            "coupling_eq": "5", "default_reagent_eq": "5", "default_reagent_count": "1",
            "default_catalyst_eq": "5", "default_catalyst_count": "1",
            "default_base_eq": "0", "default_base_count": "0",
            "reagent_eq_follows_coupling_eq": "True",
        }
    if chemistry == "HBTU/NMM":
        return {
            "coupling_eq": "10", "default_reagent_eq": "10", "default_reagent_count": "1",
            "default_catalyst_eq": "0", "default_catalyst_count": "0",
            "default_base_eq": "5", "default_base_count": "1",
            "reagent_eq_follows_coupling_eq": "False",
        }
    coupling = _get(gui, "coupling_eq", "5") or "5"
    return {
        "coupling_eq": coupling,
        "default_reagent_eq": _get(gui, "default_reagent_eq", coupling) or coupling,
        "default_reagent_count": _get(gui, "default_reagent_count", "1") or "1",
        "default_catalyst_eq": _get(gui, "default_catalyst_eq", coupling) or coupling,
        "default_catalyst_count": _get(gui, "default_catalyst_count", "1") or "1",
        "default_base_eq": _get(gui, "default_base_eq", coupling) or coupling,
        "default_base_count": _get(gui, "default_base_count", "1") or "1",
        "reagent_eq_follows_coupling_eq": _get(gui, "reagent_eq_follows_coupling_eq", "True") or "True",
    }


def build_item_payload(gui: Any, values: dict[str, str]) -> dict[str, Any]:
    sequence = str(values.get("sequence", "")).strip()
    if not sequence:
        raise ValueError("Peptide sequence is required.")
    _float(values.get("scale", ""), "Scale")
    _positive_int(values.get("copies", ""), "Copies")
    _float(values.get("loading", ""), "Resin loading")
    resin = str(values.get("resin", "")).strip()
    if not resin:
        raise ValueError("Resin is required.")

    reagent = str(values.get("reagent", "")).strip()
    additive = str(values.get("additive", "")).strip()
    base = str(values.get("base", "")).strip()
    solvent = str(values.get("solvent", "")).strip()
    if not reagent:
        raise ValueError("Choose a coupling reagent / activator.")
    if not solvent:
        raise ValueError("Choose a coupling solvent.")

    preset_name = str(values.get("preset", "Custom")).strip()
    preset = PRESETS.get(preset_name)
    chemistry = preset[0] if preset else "Manual"
    # If the operator changed any individual field after choosing a preset,
    # keep the exact recipe and label the Project item Manual rather than lying.
    if preset and (reagent, additive, base, solvent) != preset[1:]:
        chemistry = "Manual"
        preset_name = "Custom"

    item = {
        "project": str(values.get("project", "")).strip(),
        "peptide": str(values.get("peptide", "")).strip(),
        "sequence": sequence,
        "copies": str(values.get("copies", "1")).strip() or "1",
        "scale": str(values.get("scale", "0.2")).strip() or "0.2",
        "resin": resin,
        "loading": str(values.get("loading", "0.8")).strip() or "0.8",
        "apply_loading_calc": bool(resin == "2-CTC" and str(values.get("apply_loading_calc", "0")).strip().lower() in {"1", "true", "yes", "on"}),
        "loading_aa_eq": str(values.get("loading_aa_eq", _get(gui, "loading_aa_eq", "2")) or "2").strip(),
        "loading_diea_eq": str(values.get("loading_diea_eq", _get(gui, "loading_diea_eq", "4")) or "4").strip(),
        "loading_time_h": str(values.get("loading_time_h", _get(gui, "loading_time_h", "")) or "").strip(),
        "lot": str(values.get("lot", "")).strip(),
        "lot_no": str(values.get("lot", "")).strip(),
        "chemistry": chemistry,
        "method_label": preset_name,
        "status": "Ready",
        "default_reagent": reagent,
        "default_catalyst": additive,
        "default_base": base,
        "default_coupling_solution_solvent": solvent,
    }
    item.update(_method_eq_defaults(gui, chemistry))
    return item


def _is_blank_startup_item(item: Any) -> bool:
    row = dict(item or {})
    return (
        not str(row.get("sequence") or "").strip()
        and not str(row.get("project") or "").strip()
        and not str(row.get("peptide") or "").strip()
        and not str(row.get("work_item_id") or "").strip()
    )


def _commit_project_item(gui: Any, item: dict[str, Any]) -> None:
    """Use the canonical Project Manager row, reusing only the empty startup slot."""
    items = list(getattr(gui, "pm_items", []) or [])
    if len(items) == 1 and _is_blank_startup_item(items[0]):
        gui.pm_items[0] = dict(item)
        try:
            gui.pm_list.delete(0)
            gui.pm_list.insert(0, gui.pm_display_name(gui.pm_items[0]))
            gui.pm_list.selection_clear(0, "end")
            gui.pm_list.selection_set(0)
            gui.pm_list.activate(0)
        except Exception:
            pass
        try:
            from suite_gui import calculation_context
            from suite_gui.modules import plan_workflow
            plan_workflow._restore_item(gui, 0, calculation_context.namespace())
        except Exception:
            # The normal Add path is still available if a minimal test double has
            # no result widgets / calculation namespace.
            pass
        return
    gui.pm_add_peptide(item)


def _selected_project_index(gui: Any) -> int | None:
    try:
        idx = gui.pm_current_index()
        if idx is not None and 0 <= int(idx) < len(getattr(gui, "pm_items", []) or []):
            return int(idx)
    except Exception:
        pass
    try:
        selected = list(gui.pm_list.curselection())
        if selected:
            idx = int(selected[0])
            if 0 <= idx < len(getattr(gui, "pm_items", []) or []):
                return idx
    except Exception:
        pass
    return None


def _dialog_values_from_item(item: dict[str, Any]) -> dict[str, str]:
    recipe = _item_recipe_values(item)
    return {
        "project": str(item.get("project", "") or "").strip(),
        "peptide": str(item.get("peptide", "") or "").strip(),
        "sequence": str(item.get("sequence", "") or "").strip(),
        "scale": str(item.get("scale", "0.2") or "0.2").strip(),
        "copies": str(item.get("copies", "1") or "1").strip(),
        "resin": str(item.get("resin", "Rink Amide AM") or "Rink Amide AM").strip(),
        "loading": str(item.get("loading", "0.8") or "0.8").strip(),
        "apply_loading_calc": "1" if bool(item.get("apply_loading_calc", str(item.get("resin", "")).strip() == "2-CTC")) else "0",
        "loading_aa_eq": str(item.get("loading_aa_eq", "2") or "2").strip(),
        "loading_diea_eq": str(item.get("loading_diea_eq", "4") or "4").strip(),
        "loading_time_h": str(item.get("loading_time_h", "") or "").strip(),
        "lot": str(item.get("lot", item.get("lot_no", "")) or "").strip(),
        "preset": _matching_preset(recipe),
        **recipe,
    }


def _planning_signature(item: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item.get(key, "") if item.get(key, "") is not None else "").strip() for key in _PLANNING_SIGNATURE_FIELDS)


def _replace_project_item(gui: Any, index: int, item: dict[str, Any]) -> dict[str, Any]:
    """Replace one Project item without creating a second peptide row.

    Identity/provenance fields not owned by the dialog are retained. Cached plan
    outputs are retained only when the planning signature is unchanged; otherwise
    they are removed so stale calculations cannot masquerade as current results.
    """
    items = list(getattr(gui, "pm_items", []) or [])
    if not (0 <= int(index) < len(items)):
        raise IndexError("Selected peptide no longer exists.")
    old = dict(items[int(index)])
    updated = dict(old)
    updated.update(dict(item))

    recipe_fields = (
        "chemistry", "default_reagent", "default_catalyst", "default_base",
        "default_coupling_solution_solvent",
    )
    same_recipe = all(
        str(old.get(key, "") if old.get(key, "") is not None else "").strip()
        == str(updated.get(key, "") if updated.get(key, "") is not None else "").strip()
        for key in recipe_fields
    )
    if same_recipe:
        # The Add/Edit dialog intentionally does not expose eq/count fields.
        # Preserve project-specific values whenever the exact bottle recipe did
        # not change, even when sequence/scale/resin changed and cached outputs
        # therefore need invalidation.
        for key in (
            "coupling_eq", "default_reagent_eq", "default_reagent_count",
            "default_catalyst_eq", "default_catalyst_count",
            "default_base_eq", "default_base_count",
            "reagent_eq_follows_coupling_eq",
        ):
            if key in old:
                updated[key] = old[key]

    if _planning_signature(old) != _planning_signature(updated):
        for key in _CACHED_OUTPUT_FIELDS:
            updated.pop(key, None)
        updated["status"] = "Ready"

    gui.pm_items[int(index)] = updated
    try:
        gui.pm_list.delete(int(index))
        gui.pm_list.insert(int(index), gui.pm_display_name(updated))
        gui.pm_list.selection_clear(0, "end")
        gui.pm_list.selection_set(int(index))
        gui.pm_list.activate(int(index))
    except Exception:
        pass
    try:
        from suite_gui import calculation_context
        from suite_gui.modules import plan_workflow
        plan_workflow._restore_item(gui, int(index), calculation_context.namespace())
    except Exception:
        pass
    try:
        gui.pm_update_summary()
    except Exception:
        pass
    try:
        if hasattr(gui, "batch_tree"):
            gui.refresh_batch_workspace_preview()
    except Exception:
        pass
    return updated


def _apply_item_recipe_to_gui(gui: Any, item: dict[str, Any]) -> None:
    names = (
        "default_reagent", "default_reagent_eq", "default_reagent_count",
        "default_catalyst", "default_catalyst_eq", "default_catalyst_count",
        "default_base", "default_base_eq", "default_base_count",
        "default_coupling_solution_solvent", "coupling_eq",
        "reagent_eq_follows_coupling_eq",
    )
    for name in names:
        if name not in item:
            continue
        try:
            getattr(gui, name).set(item[name])
        except Exception:
            pass


def _center_over_parent(window: tk.Toplevel, parent: Any, width: int = 920, height: int = 640) -> str:
    """Center a dialog over the SPPS Planner window, with a screen-safe fallback."""
    window.update_idletasks()
    try:
        px = int(parent.winfo_rootx())
        py = int(parent.winfo_rooty())
        pw = int(parent.winfo_width())
        ph = int(parent.winfo_height())
    except Exception:
        px = py = 0
        pw = ph = 0

    screen_w = max(1, int(window.winfo_screenwidth()))
    screen_h = max(1, int(window.winfo_screenheight()))
    width = min(int(width), screen_w)
    height = min(int(height), screen_h)

    if pw > 1 and ph > 1:
        x = px + (pw - width) // 2
        y = py + (ph - height) // 2
    else:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

    x = max(0, min(x, max(0, screen_w - width)))
    y = max(0, min(y, max(0, screen_h - height)))
    geometry = f"{width}x{height}+{x}+{y}"
    window.geometry(geometry)
    return geometry


def open_dialog(gui: Any, item_index: int | None = None):
    existing = getattr(gui, "add_peptide_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify(); existing.lift(); existing.focus_force()
            return existing
    except Exception:
        pass

    edit_mode = item_index is not None
    edit_item = None
    if edit_mode:
        items = list(getattr(gui, "pm_items", []) or [])
        if not (0 <= int(item_index) < len(items)):
            raise IndexError("Selected peptide no longer exists.")
        edit_item = dict(items[int(item_index)])
        initial = _dialog_values_from_item(edit_item)
    else:
        project_default, peptide_default, lot_default = _default_names(gui)
        initial = {
            "project": project_default, "peptide": peptide_default, "sequence": "",
            "scale": "0.2", "copies": "1", "resin": "Rink Amide AM",
            "loading": "0.8", "apply_loading_calc": "0",
            "loading_aa_eq": _get(gui, "loading_aa_eq", "2") or "2",
            "loading_diea_eq": _get(gui, "loading_diea_eq", "4") or "4",
            "loading_time_h": _get(gui, "loading_time_h", ""),
            "lot": lot_default,
            "preset": "DIC + HOBt (anhydrous)", "reagent": "DIC",
            "additive": "HOBt (anhydrous)", "base": "", "solvent": "DMF",
        }

    win = tk.Toplevel(gui)
    gui.add_peptide_dialog = win
    gui.add_peptide_dialog_mode = "edit" if edit_mode else "add"
    gui.add_peptide_dialog_item_index = int(item_index) if edit_mode else None
    win.title("Edit peptide setup" if edit_mode else "Add peptide")
    win.transient(gui)
    win.minsize(780, 560)
    _center_over_parent(win, gui, 920, 640)

    scroll_host = ttk.Frame(win)
    scroll_host.pack(fill="both", expand=True)
    scroll_host.rowconfigure(0, weight=1)
    scroll_host.columnconfigure(0, weight=1)
    canvas = tk.Canvas(scroll_host, highlightthickness=0, borderwidth=0)
    scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    shell = ttk.Frame(canvas, padding=14)
    canvas_window = canvas.create_window((0, 0), window=shell, anchor="nw")
    shell.columnconfigure(0, weight=1)

    def _sync_scrollregion(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _fit_shell_width(event):
        canvas.itemconfigure(canvas_window, width=max(1, int(event.width)))

    shell.bind("<Configure>", _sync_scrollregion, add="+")
    canvas.bind("<Configure>", _fit_shell_width, add="+")
    heading = "Edit peptide setup" if edit_mode else "Add peptide"
    subtitle = (
        "Change the peptide setup or exact coupling bottles, then save changes."
        if edit_mode else
        "Fill in the peptide and the coupling chemicals, then press Add peptide."
    )
    ttk.Label(shell, text=heading, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(shell, text=subtitle, foreground="#555").grid(row=1, column=0, sticky="w", pady=(2, 10))

    vars_ = {key: tk.StringVar(value=str(value)) for key, value in initial.items()}
    gui.add_peptide_dialog_vars = vars_
    initial_snapshot = _dialog_snapshot(initial)
    closing_state = {"committed": False}

    step1 = ttk.Labelframe(shell, text="STEP 1 — Peptide setup", padding=10)
    step1.grid(row=2, column=0, sticky="ew", pady=(0, 10))
    for c in (1, 3): step1.columnconfigure(c, weight=1)

    def field(parent, row, col, label, key, width=18):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=4)
        entry = ttk.Entry(parent, textvariable=vars_[key], width=width)
        entry.grid(row=row, column=col+1, sticky="ew", padx=(0, 14), pady=4)
        return entry

    field(step1, 0, 0, "Project", "project")
    field(step1, 0, 2, "Peptide name", "peptide")
    ttk.Label(step1, text="Sequence").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
    seq_entry = ttk.Entry(step1, textvariable=vars_["sequence"])
    seq_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 14), pady=4)
    field(step1, 2, 0, "Scale (mmol)", "scale")
    field(step1, 2, 2, "Copies", "copies")
    ttk.Label(step1, text="Resin").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=4)
    resin_values = list(getattr(gui, "RESIN_VALUES", []) or ["Rink Amide AM", "2-CTC"])
    resin_combo = ttk.Combobox(step1, textvariable=vars_["resin"], values=resin_values, state="normal")
    resin_combo.grid(row=3, column=1, sticky="ew", padx=(0, 14), pady=4)
    field(step1, 3, 2, "Loading (mmol/g)", "loading")
    field(step1, 4, 0, "LOT No.", "lot")
    direct_loading_status_var = tk.StringVar(value="")
    direct_loading_check = ttk.Checkbutton(
        step1,
        text="Direct resin loading (2-CTC only)",
        variable=vars_["apply_loading_calc"],
        onvalue="1",
        offvalue="0",
    )
    direct_loading_check.grid(row=4, column=2, columnspan=2, sticky="w", padx=(0, 14), pady=4)
    ttk.Label(step1, textvariable=direct_loading_status_var, foreground="#666").grid(
        row=5, column=0, columnspan=4, sticky="w", pady=(2, 0)
    )
    template_status_var = tk.StringVar(value="")
    template_bar = ttk.Frame(step1)
    template_bar.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(5, 0))
    copy_settings_btn = ttk.Button(template_bar, text="Copy selected peptide settings", command=lambda: copy_selected_settings())
    if not edit_mode:
        copy_settings_btn.pack(side="left")
    else:
        template_status_var.set("Editing this saved peptide; exact bottle identities are loaded below.")
    ttk.Label(template_bar, textvariable=template_status_var, foreground="#555").pack(side="left", padx=(8, 0))
    ttk.Label(step1, text=("Sequence, peptide name and LOT are not copied." if not edit_mode else "Saving changes updates this peptide only; Batch solution-prep defaults stay unchanged."), foreground="#666").grid(row=7, column=0, columnspan=4, sticky="w", pady=(3, 0))

    step2 = ttk.Labelframe(shell, text="STEP 2 — Coupling chemicals", padding=10)
    catalog_choices = _catalog_choices()
    recent_bottles = _load_user_recipe_state().get("recent_bottles", {})
    for _key in ("reagent", "additive", "base", "solvent"):
        catalog_choices[_key] = _prioritize_recent_choices(catalog_choices[_key], list(recent_bottles.get(_key, [])))
    step2.grid(row=3, column=0, sticky="ew", pady=(0, 10))
    for c in (1, 3): step2.columnconfigure(c, weight=1)

    ttk.Label(step2, text="Method shortcut").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
    preset_combo = ttk.Combobox(step2, textvariable=vars_["preset"], values=list(PRESETS), state="readonly")
    preset_combo.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=4)
    reset_preset_btn = ttk.Button(step2, text="Reset bottles", command=lambda: (apply_preset(), refresh_material_summary()))
    reset_preset_btn.grid(row=0, column=3, sticky="ew", padx=(0, 14), pady=4)

    user_recipes = _load_user_recipes()
    user_recipe_var = tk.StringVar(value="")
    ttk.Label(step2, text="My recipes").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
    user_recipe_combo = ttk.Combobox(step2, textvariable=user_recipe_var, values=list(user_recipes), state="readonly")
    user_recipe_combo.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=4)
    recipe_buttons = ttk.Frame(step2)
    recipe_buttons.grid(row=1, column=2, columnspan=2, sticky="e", padx=(0, 14), pady=4)
    save_recipe_btn = ttk.Button(recipe_buttons, text="Save current…")
    save_recipe_btn.pack(side="left", padx=(0, 5))
    favorite_recipe_btn = ttk.Button(recipe_buttons, text="☆ Favorite", state="disabled")
    favorite_recipe_btn.pack(side="left", padx=(0, 5))
    rename_recipe_btn = ttk.Button(recipe_buttons, text="Rename…", state="disabled")
    rename_recipe_btn.pack(side="left", padx=(0, 5))
    delete_recipe_btn = ttk.Button(recipe_buttons, text="Delete", state="disabled")
    delete_recipe_btn.pack(side="left", padx=(0, 5))
    backup_recipe_btn = ttk.Button(recipe_buttons, text="Backup…")
    backup_recipe_btn.pack(side="left", padx=(0, 5))
    import_recipe_btn = ttk.Button(recipe_buttons, text="Import…")
    import_recipe_btn.pack(side="left")

    recent_recipe_frame = ttk.Frame(step2)
    recent_recipe_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 3))
    ttk.Label(recent_recipe_frame, text="Quick:", foreground="#666").pack(side="left", padx=(0, 6))

    filter_var = tk.StringVar(value="")
    ttk.Label(step2, text="Find bottle").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=4)
    filter_entry = ttk.Entry(step2, textvariable=filter_var)
    filter_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=4)
    ttk.Button(step2, text="Clear", command=lambda: filter_var.set("")).grid(row=3, column=3, sticky="ew", padx=(0, 14), pady=4)

    filter_status_var = tk.StringVar(value="")
    ttk.Label(step2, textvariable=filter_status_var, foreground="#666").grid(row=3, column=3, sticky="s", padx=(0, 14), pady=(24, 0))

    ttk.Label(step2, text="Coupling reagent / activator").grid(row=4, column=0, sticky="w", padx=(0, 6), pady=4)
    reagent_combo = ttk.Combobox(step2, textvariable=vars_["reagent"], values=catalog_choices["reagent"], state="normal")
    reagent_combo.grid(row=4, column=1, sticky="ew", padx=(0, 14), pady=4)
    ttk.Label(step2, text="Additive / catalyst").grid(row=4, column=2, sticky="w", padx=(0, 6), pady=4)
    additive_combo = ttk.Combobox(step2, textvariable=vars_["additive"], values=catalog_choices["additive"], state="normal")
    additive_combo.grid(row=4, column=3, sticky="ew", padx=(0, 14), pady=4)

    ttk.Label(step2, text="Base").grid(row=5, column=0, sticky="w", padx=(0, 6), pady=4)
    base_combo = ttk.Combobox(step2, textvariable=vars_["base"], values=catalog_choices["base"], state="normal")
    base_combo.grid(row=5, column=1, sticky="ew", padx=(0, 14), pady=4)
    ttk.Label(step2, text="Solvent").grid(row=5, column=2, sticky="w", padx=(0, 6), pady=4)
    solvent_combo = ttk.Combobox(step2, textvariable=vars_["solvent"], values=catalog_choices["solvent"], state="normal")
    solvent_combo.grid(row=5, column=3, sticky="ew", padx=(0, 14), pady=4)
    ttk.Label(
        step2,
        text="Pick a shortcut, load one of My recipes, or choose the exact bottles below. HOBt (anhydrous) and HOBt hydrate are different reagents. NMM = base; NMP = solvent. If a bottle is not listed, type its label exactly.",
        foreground="#555", wraplength=820,
    ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))
    recent_bottle_var = tk.StringVar(value="")
    ttk.Label(step2, textvariable=recent_bottle_var, foreground="#666", wraplength=820).grid(
        row=7, column=0, columnspan=4, sticky="w", pady=(4, 0)
    )

    material_summary_var = tk.StringVar(value="")
    material_summary = ttk.Label(step2, textvariable=material_summary_var, foreground="#2f5f3f", wraplength=820)
    material_summary.grid(row=8, column=0, columnspan=4, sticky="w", pady=(7, 0))
    hobt_note_var = tk.StringVar(value="")
    hobt_note = ttk.Label(step2, textvariable=hobt_note_var, foreground="#7a4b00", wraplength=820)
    hobt_note.grid(row=9, column=0, columnspan=4, sticky="w", pady=(3, 0))

    updating = {"preset": False}
    def apply_preset(_event=None):
        preset = PRESETS.get(vars_["preset"].get())
        if not preset:
            return
        updating["preset"] = True
        try:
            _chem, reagent, additive, base, solvent = preset
            vars_["reagent"].set(reagent); vars_["additive"].set(additive)
            vars_["base"].set(base); vars_["solvent"].set(solvent)
        finally:
            updating["preset"] = False

    def mark_custom(_event=None):
        if updating["preset"]:
            return
        recipe = {key: vars_[key].get() for key in ("reagent", "additive", "base", "solvent")}
        vars_["preset"].set(_matching_preset(recipe))

    def refresh_user_recipe_values(selected: str = ""):
        nonlocal user_recipes
        user_recipes = _load_user_recipes()
        names = list(user_recipes)
        user_recipe_combo.configure(values=names)
        if selected and selected in user_recipes:
            user_recipe_var.set(selected)
        elif user_recipe_var.get() not in user_recipes:
            user_recipe_var.set("")
        state = "normal" if user_recipe_var.get() in user_recipes else "disabled"
        delete_recipe_btn.configure(state=state)
        rename_recipe_btn.configure(state=state)
        favorite_recipe_btn.configure(state=state)
        refresh_recent_recipe_buttons()

    def refresh_recent_recipe_buttons():
        for child in recent_recipe_frame.winfo_children()[1:]:
            child.destroy()
        state = _load_user_recipe_state()
        favorites = list(state.get("favorites", []))
        recent = [x for x in state.get("recent", []) if x not in favorites]
        quick = [(name, True) for name in favorites[:3]] + [(name, False) for name in recent[:3]]
        if not quick:
            ttk.Label(recent_recipe_frame, text="No favorite or recent recipes yet", foreground="#888").pack(side="left")
            return
        for name, favorite in quick[:5]:
            ttk.Button(
                recent_recipe_frame, text=(("★ " if favorite else "") + name),
                command=lambda n=name: (user_recipe_var.set(n), load_user_recipe()),
            ).pack(side="left", padx=(0, 5))

    def load_user_recipe(_event=None):
        name = user_recipe_var.get().strip()
        recipe = user_recipes.get(name)
        if not recipe:
            delete_recipe_btn.configure(state="disabled")
            return
        updating["preset"] = True
        try:
            for key in ("reagent", "additive", "base", "solvent"):
                vars_[key].set(str(recipe.get(key, "") or ""))
            vars_["preset"].set(_matching_preset(recipe))
        finally:
            updating["preset"] = False
        filter_var.set("")
        try:
            _touch_user_recipe(name)
        except Exception:
            pass
        delete_recipe_btn.configure(state="normal")
        rename_recipe_btn.configure(state="normal")
        refresh_recent_recipe_buttons()
        template_status_var.set(f"Loaded My recipe: {name}")
        refresh_material_summary()

    def save_current_recipe():
        recipe = {key: vars_[key].get() for key in ("reagent", "additive", "base", "solvent")}
        default_name = _matching_preset(recipe)
        if default_name == "Custom":
            default_name = "My coupling recipe"
        name = simpledialog.askstring(
            "Save coupling recipe",
            "Name this recipe:",
            initialvalue=default_name,
            parent=win,
        )
        if name is None:
            return
        label = str(name).strip()
        existing_same = _find_equivalent_recipe(recipe, user_recipes, exclude=label)
        if existing_same:
            messagebox.showinfo(
                "Save coupling recipe",
                f"The same bottle combination is already saved as '{existing_same}'.\n\nThat existing recipe was selected instead.",
                parent=win,
            )
            user_recipe_var.set(existing_same)
            load_user_recipe()
            return
        if label in user_recipes and user_recipes[label] != {key: str(recipe.get(key, "") or "").strip() for key in ("reagent", "additive", "base", "solvent")}:
            if not messagebox.askyesno(
                "Replace coupling recipe",
                f"A recipe named '{label}' already exists. Replace it with the current bottle combination?",
                parent=win,
            ):
                return
        try:
            recipes = _save_user_recipe(label, recipe)
        except ValueError as exc:
            messagebox.showerror("Save coupling recipe", str(exc), parent=win)
            return
        except Exception as exc:
            messagebox.showerror("Save coupling recipe", f"Could not save the recipe.\n\n{exc}", parent=win)
            return
        user_recipes.clear(); user_recipes.update(recipes)
        refresh_user_recipe_values(label)
        template_status_var.set(f"Saved My recipe: {label}")

    def rename_current_recipe():
        old_name = user_recipe_var.get().strip()
        if not old_name or old_name not in user_recipes:
            return
        new_name = simpledialog.askstring(
            "Rename coupling recipe",
            "New recipe name:",
            initialvalue=old_name,
            parent=win,
        )
        if new_name is None or str(new_name).strip() == old_name:
            return
        try:
            recipes = _rename_user_recipe(old_name, new_name)
        except ValueError as exc:
            messagebox.showerror("Rename coupling recipe", str(exc), parent=win)
            return
        except Exception as exc:
            messagebox.showerror("Rename coupling recipe", f"Could not rename the recipe.\n\n{exc}", parent=win)
            return
        user_recipes.clear(); user_recipes.update(recipes)
        label = str(new_name).strip()
        refresh_user_recipe_values(label)
        template_status_var.set(f"Renamed My recipe: {old_name} → {label}")

    def toggle_current_recipe_favorite():
        name = user_recipe_var.get().strip()
        if not name or name not in user_recipes:
            return
        try:
            enabled, _favorites = _toggle_user_recipe_favorite(name)
        except Exception as exc:
            messagebox.showerror("Favorite coupling recipe", str(exc), parent=win)
            return
        favorite_recipe_btn.configure(text=("★ Favorite" if enabled else "☆ Favorite"))
        refresh_recent_recipe_buttons()
        template_status_var.set(("Pinned favorite recipe: " if enabled else "Unpinned favorite recipe: ") + name)

    def delete_current_recipe():
        name = user_recipe_var.get().strip()
        if not name or name not in user_recipes:
            return
        if not messagebox.askyesno(
            "Delete coupling recipe",
            f"Delete My recipe '{name}'?",
            parent=win,
        ):
            return
        try:
            recipes = _delete_user_recipe(name)
        except Exception as exc:
            messagebox.showerror("Delete coupling recipe", f"Could not delete the recipe.\n\n{exc}", parent=win)
            return
        user_recipes.clear(); user_recipes.update(recipes)
        user_recipe_var.set("")
        refresh_user_recipe_values()
        template_status_var.set(f"Deleted My recipe: {name}")

    def refresh_recent_bottle_hint():
        state = _load_user_recipe_state().get("recent_bottles", {})
        labels = []
        for key, short in (("reagent", "R"), ("additive", "A"), ("base", "B"), ("solvent", "S")):
            rows = list(state.get(key, []))
            if rows:
                labels.append(f"{short}: {rows[0]}")
        recent_bottle_var.set("Recent bottles — " + "  ·  ".join(labels) if labels else "Recent bottles — none yet")

    def refresh_filters(*_args):
        query = filter_var.get()
        filtered = {key: _filter_choices(catalog_choices[key], query) for key in ("reagent", "additive", "base", "solvent")}
        reagent_combo.configure(values=filtered["reagent"])
        additive_combo.configure(values=filtered["additive"])
        base_combo.configure(values=filtered["base"])
        solvent_combo.configure(values=filtered["solvent"])
        if str(query).strip():
            filter_status_var.set(
                f"R {len(filtered['reagent'])} · A {len(filtered['additive'])} · B {len(filtered['base'])} · S {len(filtered['solvent'])}"
            )
        else:
            filter_status_var.set("")

    def copy_selected_settings():
        try:
            idx = gui.pm_current_index()
        except Exception:
            idx = None
        items = list(getattr(gui, "pm_items", []) or [])
        if idx is None or idx < 0 or idx >= len(items) or _is_blank_startup_item(items[idx]):
            template_status_var.set("Select a saved peptide in Project Manager first.")
            return
        item = dict(items[idx])
        for key, item_key in (("scale", "scale"), ("copies", "copies"), ("resin", "resin"), ("loading", "loading")):
            if str(item.get(item_key, "") or "").strip():
                vars_[key].set(str(item[item_key]).strip())
        if str(item.get("resin", "") or "").strip() == "2-CTC":
            vars_["apply_loading_calc"].set("1" if bool(item.get("apply_loading_calc", True)) else "0")
        else:
            vars_["apply_loading_calc"].set("0")
        recipe = _item_recipe_values(item)
        for key, value in recipe.items():
            vars_[key].set(value)
        vars_["preset"].set(_matching_preset(recipe))
        filter_var.set("")
        template_status_var.set("Copied scale, resin, loading and exact coupling bottles.")
        refresh_material_summary()

    def backup_recipes():
        path = filedialog.asksaveasfilename(
            parent=win,
            title="Backup My recipes",
            defaultextension=".json",
            filetypes=(("JSON recipe backup", "*.json"), ("All files", "*.*")),
            initialfile="SPPS_Planner_My_Recipes.json",
        )
        if not path:
            return
        try:
            count = _export_user_recipes(path)
        except Exception as exc:
            messagebox.showerror("Backup My recipes", f"Could not export recipes.\n\n{exc}", parent=win)
            return
        messagebox.showinfo("Backup My recipes", f"Backed up {count} recipe(s).", parent=win)

    def import_recipes():
        path = filedialog.askopenfilename(
            parent=win,
            title="Import My recipes",
            filetypes=(("JSON recipe backup", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            result = _import_user_recipes(path)
        except Exception as exc:
            messagebox.showerror("Import My recipes", f"Could not import recipes.\n\n{exc}", parent=win)
            return
        refresh_user_recipe_values()
        template_status_var.set(
            f"Imported {result['added']} recipe(s); skipped {result['skipped']} duplicate(s)."
        )
        messagebox.showinfo(
            "Import My recipes",
            f"Added: {result['added']}\nRenamed name conflicts: {result['renamed']}\n"
            f"Skipped equivalent recipes: {result['skipped']}\nInvalid rows: {result['invalid']}",
            parent=win,
        )

    def refresh_material_summary(*_args):
        current = {key: vars_[key].get() for key in ("reagent", "additive", "base", "solvent")}
        summary, has_custom = _material_summary(current)
        material_summary_var.set(summary)
        material_summary.configure(foreground="#7a4b00" if has_custom else "#2f5f3f")
        additive = calculation_context.normalized(current.get("additive", ""))
        if additive in {calculation_context.normalized("HOBt hydrate"), calculation_context.normalized("HOBt monohydrate")}:
            hobt_note_var.set("HOBt hydrate selected: MW 153.14 g/mol. This is not the anhydrous 135.13 g/mol bottle form.")
        elif additive in {calculation_context.normalized("HOBt (anhydrous)"), calculation_context.normalized("HOBt")}:
            hobt_note_var.set("Anhydrous/generic HOBt selected: MW 135.13 g/mol. Use HOBt hydrate instead if the bottle is the hydrate form.")
        else:
            hobt_note_var.set("")

    def refresh_direct_loading_state(*_args):
        is_direct = str(vars_["resin"].get() or "").strip() == "2-CTC"
        if is_direct:
            direct_loading_check.configure(state="normal")
            direct_loading_status_var.set(
                "2-CTC requires direct loading in the standard workflow, so this is checked automatically. "
                "Uncheck only when the resin is already loaded."
            )
        else:
            if vars_["apply_loading_calc"].get() != "0":
                vars_["apply_loading_calc"].set("0")
            direct_loading_check.configure(state="disabled")
            direct_loading_status_var.set("Direct loading is not applied to the selected preloaded/synthesizer resin.")

    save_recipe_btn.configure(command=save_current_recipe)
    favorite_recipe_btn.configure(command=toggle_current_recipe_favorite)
    rename_recipe_btn.configure(command=rename_current_recipe)
    delete_recipe_btn.configure(command=delete_current_recipe)
    backup_recipe_btn.configure(command=backup_recipes)
    import_recipe_btn.configure(command=import_recipes)
    user_recipe_combo.bind("<<ComboboxSelected>>", load_user_recipe)
    def refresh_recipe_button_state(*_args):
        state = "normal" if user_recipe_var.get() in user_recipes else "disabled"
        delete_recipe_btn.configure(state=state)
        rename_recipe_btn.configure(state=state)
        favorite_recipe_btn.configure(state=state)
        favorites = _load_user_recipe_state().get("favorites", [])
        favorite_recipe_btn.configure(text=("★ Favorite" if user_recipe_var.get() in favorites else "☆ Favorite"))
    user_recipe_var.trace_add("write", refresh_recipe_button_state)
    refresh_user_recipe_values()

    preset_combo.bind("<<ComboboxSelected>>", lambda event: (apply_preset(event), refresh_material_summary()))
    for combo in (reagent_combo, additive_combo, base_combo, solvent_combo):
        combo.bind("<<ComboboxSelected>>", lambda event: (mark_custom(event), refresh_material_summary()))
        combo.bind("<KeyRelease>", lambda event: (mark_custom(event), refresh_material_summary()))
    for key in ("reagent", "additive", "base", "solvent"):
        vars_[key].trace_add("write", lambda *_args: mark_custom())
        vars_[key].trace_add("write", refresh_material_summary)
    filter_var.trace_add("write", refresh_filters)

    last_resin = {"value": str(vars_["resin"].get() or "").strip()}
    def on_resin_changed(*_args):
        resin_now = str(vars_["resin"].get() or "").strip()
        if resin_now != last_resin["value"]:
            vars_["apply_loading_calc"].set("1" if resin_now == "2-CTC" else "0")
            last_resin["value"] = resin_now
        refresh_direct_loading_state()

    vars_["resin"].trace_add("write", on_resin_changed)
    refresh_direct_loading_state()
    refresh_recent_bottle_hint()
    refresh_filters()
    refresh_material_summary()

    review = ttk.Labelframe(shell, text=("STEP 3 — Check before saving" if edit_mode else "STEP 3 — Check before adding"), padding=10)
    review.grid(row=4, column=0, sticky="ew", pady=(0, 8))
    review.columnconfigure(0, weight=1)
    recipe_preview_var = tk.StringVar(value="")
    ready_summary_var = tk.StringVar(value="")
    ready_note_var = tk.StringVar(value="")
    review_details_var = tk.StringVar(value="")
    edit_change_var = tk.StringVar(value="")
    ttk.Label(review, textvariable=recipe_preview_var, font=("Segoe UI", 11, "bold"), wraplength=820).grid(row=0, column=0, sticky="w")
    ttk.Label(review, textvariable=review_details_var, wraplength=820, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 0))
    edit_change_label = ttk.Label(review, textvariable=edit_change_var, foreground="#7a4b00", wraplength=820)
    edit_change_label.grid(row=2, column=0, sticky="w", pady=(5, 0))
    ready_label = ttk.Label(review, textvariable=ready_summary_var, foreground="#2f5f3f", wraplength=820)
    ready_label.grid(row=3, column=0, sticky="w", pady=(5, 0))
    ready_note_label = ttk.Label(review, textvariable=ready_note_var, foreground="#7a4b00", wraplength=820)
    ready_note_label.grid(row=4, column=0, sticky="w", pady=(3, 0))

    buttons = ttk.Frame(shell)
    buttons.grid(row=5, column=0, sticky="e", pady=(4, 0))

    def confirm():
        raw = {key: var.get() for key, var in vars_.items()}
        ready, summary, note = _live_check(raw)
        if not ready:
            messagebox.showerror("Add peptide", summary + (("\n\n" + note) if note else ""), parent=win)
            return
        duplicate_notes = _duplicate_project_notes(gui, raw, int(item_index) if edit_mode else None)
        if duplicate_notes and not messagebox.askyesno(
            "Possible duplicate peptide",
            "\n".join(duplicate_notes) + "\n\nContinue anyway?",
            parent=win,
        ):
            return
        try:
            item = build_item_payload(gui, raw)
        except ValueError as exc:
            messagebox.showerror("Add peptide", str(exc), parent=win)
            return
        try:
            _touch_recent_bottles({key: raw.get(key, "") for key in ("reagent", "additive", "base", "solvent")})
        except Exception:
            pass
        if edit_mode:
            _replace_project_item(gui, int(item_index), item)
        else:
            _commit_project_item(gui, item)
        try:
            gui.tabs.select(gui.pm_tab_frame)
        except Exception:
            try:
                for tab in gui.tabs.tabs():
                    if str(gui.tabs.tab(tab, "text")) == "Project Manager":
                        gui.tabs.select(tab); break
            except Exception:
                pass
        try:
            gui.schedule_autosave()
        except Exception:
            pass
        closing_state["committed"] = True
        win.destroy()

    ttk.Label(buttons, text=("Ctrl+Enter = Save   Esc = Cancel" if edit_mode else "Ctrl+Enter = Add   Esc = Cancel"), foreground="#666").pack(side="left", padx=(0, 16))
    def request_close():
        if closing_state["committed"]:
            win.destroy(); return
        current = {key: var.get() for key, var in vars_.items()}
        if _dialog_snapshot(current) != initial_snapshot:
            if not messagebox.askyesno(
                "Discard unsaved changes?",
                "This peptide setup has unsaved changes. Discard them and close?",
                parent=win,
            ):
                return
        win.destroy()

    ttk.Button(buttons, text="Cancel", command=request_close).pack(side="right", padx=(6, 0))
    add_btn = ttk.Button(buttons, text=("Save changes" if edit_mode else "Add peptide"), command=confirm, state="disabled")
    add_btn.pack(side="right")

    def refresh_ready_state(*_args):
        current = {key: var.get() for key, var in vars_.items()}
        recipe_preview_var.set("Recipe: " + _recipe_preview(current))
        review_details_var.set(_review_lines(current))
        if edit_mode and edit_item is not None:
            changed, recalc = _edit_change_summary(edit_item, current)
            if changed:
                edit_change_var.set(
                    "Changed: " + ", ".join(changed) +
                    ("  ·  Plan/Materials will be recalculated." if recalc else "  ·  Existing calculation results stay valid.")
                )
            else:
                edit_change_var.set("No setup changes yet.")
        else:
            edit_change_var.set("")
        ready, summary, note = _live_check(current)
        duplicate_notes = _duplicate_project_notes(gui, current, int(item_index) if edit_mode else None)
        if duplicate_notes:
            duplicate_text = "Possible duplicate: " + "  ".join(duplicate_notes)
            note = (note + "  |  " + duplicate_text) if note else duplicate_text
        ready_summary_var.set((("Ready to save — " if edit_mode else "Ready to add — ") if ready else "Not ready — ") + summary)
        ready_label.configure(foreground="#2f5f3f" if ready else "#8a2f2f")
        ready_note_var.set(note)
        add_btn.configure(state="normal" if ready else "disabled")

    for key in ("sequence", "scale", "copies", "resin", "loading", "apply_loading_calc", "reagent", "additive", "base", "solvent"):
        vars_[key].trace_add("write", refresh_ready_state)
    refresh_ready_state()
    gui.add_peptide_confirm_button = add_btn
    gui.add_peptide_reagent_combo = reagent_combo
    gui.add_peptide_additive_combo = additive_combo
    gui.add_peptide_base_combo = base_combo
    gui.add_peptide_solvent_combo = solvent_combo
    gui.add_peptide_preset_combo = preset_combo
    gui.add_peptide_material_summary_var = material_summary_var
    gui.add_peptide_hobt_note_var = hobt_note_var
    gui.add_peptide_recipe_preview_var = recipe_preview_var
    gui.add_peptide_ready_summary_var = ready_summary_var
    gui.add_peptide_ready_note_var = ready_note_var
    gui.add_peptide_filter_var = filter_var
    gui.add_peptide_filter_entry = filter_entry
    gui.add_peptide_template_status_var = template_status_var
    gui.add_peptide_direct_loading_check = direct_loading_check
    gui.add_peptide_direct_loading_status_var = direct_loading_status_var
    gui.add_peptide_reset_preset_button = reset_preset_btn
    gui.add_peptide_copy_settings_button = copy_settings_btn
    gui.add_peptide_user_recipe_var = user_recipe_var
    gui.add_peptide_user_recipe_combo = user_recipe_combo
    gui.add_peptide_save_recipe_button = save_recipe_btn
    gui.add_peptide_favorite_recipe_button = favorite_recipe_btn
    gui.add_peptide_rename_recipe_button = rename_recipe_btn
    gui.add_peptide_delete_recipe_button = delete_recipe_btn
    gui.add_peptide_backup_recipe_button = backup_recipe_btn
    gui.add_peptide_import_recipe_button = import_recipe_btn
    gui.add_peptide_request_close = request_close
    gui.add_peptide_filter_status_var = filter_status_var
    gui.add_peptide_recent_bottle_var = recent_bottle_var
    gui.add_peptide_review_details_var = review_details_var
    gui.add_peptide_edit_change_var = edit_change_var

    scroll_tag = f"AddPeptideScroll_{id(win)}"

    def _wheel(event):
        delta = int(getattr(event, "delta", 0) or 0)
        if delta:
            steps = -1 if delta > 0 else 1
            canvas.yview_scroll(steps, "units")
            return "break"
        num = int(getattr(event, "num", 0) or 0)
        if num in (4, 5):
            canvas.yview_scroll(-1 if num == 4 else 1, "units")
            return "break"
        return None

    win.bind_class(scroll_tag, "<MouseWheel>", _wheel)
    win.bind_class(scroll_tag, "<Button-4>", _wheel)
    win.bind_class(scroll_tag, "<Button-5>", _wheel)

    def _install_scroll_tag(widget):
        try:
            tags = list(widget.bindtags())
            if scroll_tag not in tags:
                tags.insert(1, scroll_tag)
                widget.bindtags(tuple(tags))
            for child in widget.winfo_children():
                _install_scroll_tag(child)
        except tk.TclError:
            return

    _install_scroll_tag(win)
    win.bind("<Prior>", lambda _event: canvas.yview_scroll(-1, "pages"), add="+")
    win.bind("<Next>", lambda _event: canvas.yview_scroll(1, "pages"), add="+")
    win.bind("<Home>", lambda _event: canvas.yview_moveto(0.0), add="+")
    win.bind("<End>", lambda _event: canvas.yview_moveto(1.0), add="+")
    gui.add_peptide_canvas = canvas
    gui.add_peptide_scrollbar = scrollbar

    win.protocol("WM_DELETE_WINDOW", request_close)
    win.bind("<Escape>", lambda _event: request_close())
    win.bind("<Control-Return>", lambda _event: confirm())
    seq_entry.focus_set()
    return win


def open_edit_dialog(gui: Any):
    index = _selected_project_index(gui)
    if index is None:
        messagebox.showinfo("Edit peptide setup", "Select one saved peptide in Project Manager first.", parent=gui)
        return None
    item = dict((getattr(gui, "pm_items", []) or [])[index])
    if _is_blank_startup_item(item):
        messagebox.showinfo("Edit peptide setup", "Add a peptide first, then edit its setup.", parent=gui)
        return None
    return open_dialog(gui, item_index=index)


def configure_add_button(gui: Any) -> None:
    """Use one V7 input dialog for adding and editing Project peptide setup."""
    button = getattr(gui, "pm_add_button", None)
    if button is not None:
        button.configure(command=lambda: open_dialog(gui))
    action_bar = getattr(gui, "pm_action_bar", None)
    existing = getattr(gui, "pm_edit_setup_button", None)
    try:
        exists = bool(existing is not None and existing.winfo_exists())
    except Exception:
        exists = False
    if action_bar is not None and not exists:
        edit_button = ttk.Button(action_bar, text="Edit setup…", command=lambda: open_edit_dialog(gui))
        edit_button.pack(side="left", padx=(9, 3))
        gui.pm_edit_setup_button = edit_button


__all__ = [
    "ADDITIVES", "BASES", "COUPLING_REAGENTS", "PRESETS", "SOLVENTS",
    "build_item_payload", "configure_add_button", "open_dialog", "open_edit_dialog", "_center_over_parent",
    "_catalog_choices", "_material_details", "_material_summary", "_recipe_preview", "_live_check",
    "_filter_choices", "_role_mismatch_notes", "_item_recipe_values", "_matching_preset",
    "_load_user_recipe_state", "_load_user_recipes", "_save_user_recipe", "_delete_user_recipe",
    "_rename_user_recipe", "_toggle_user_recipe_favorite", "_find_equivalent_recipe", "_touch_user_recipe", "_touch_recent_bottles",
    "_prioritize_recent_choices", "_export_user_recipes", "_import_user_recipes",
    "_duplicate_project_notes", "_dialog_snapshot", "_user_recipe_path",
    "_review_lines", "_edit_change_summary", "_dialog_values_from_item", "_replace_project_item", "_planning_signature",
]
