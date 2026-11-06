from __future__ import annotations

from pathlib import Path


def test_legacy_controller_and_numbered_patch_sources_are_removed():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "suite_gui" / "legacy_controller.py").exists()
    assert not (root / "suite_gui" / "release_composition.py").exists()
    assert list((root / "suite_gui" / "modules").glob("v[0-9]*.py")) == []
    compat = root / "suite_gui" / "compat"
    assert not compat.exists() or list(compat.glob("*.py")) == []
