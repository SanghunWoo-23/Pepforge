from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_experimental_workflow_uses_stable_recommendation_namespace():
    source = (ROOT / "spps_v4_gui" / "experimental_workflow.py").read_text(encoding="utf-8")
    assert "from spps_v4_gui.recommendation import" in source
    assert "ml_advisor_v5." not in source
    assert "condition_optimizer_v5." not in source
    assert "model_registry_v5." not in source


def test_recommendation_namespace_does_not_eager_load_heavy_backends():
    for name in list(sys.modules):
        if name.startswith("spps_v4_gui.recommendation") or name in {
            "spps_v4_gui.ml_advisor_v5", "spps_v4_gui.condition_optimizer_v5", "spps_v4_gui.model_registry_v5"
        }:
            sys.modules.pop(name, None)
    import spps_v4_gui.recommendation  # noqa: F401
    assert "spps_v4_gui.ml_advisor_v5" not in sys.modules
    assert "spps_v4_gui.condition_optimizer_v5" not in sys.modules
    assert "spps_v4_gui.model_registry_v5" not in sys.modules
