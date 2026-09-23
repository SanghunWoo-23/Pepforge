from __future__ import annotations

import inspect
from pathlib import Path

from peptiforg_core.peptide_target_complex_builder import export_complex_builder_package


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_mode_starts_without_hidden_sequence_or_candidate():
    text = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'self.seq_text.insert("1.0", "DELIKFVRWA")' not in text
    assert 'self.candidate_var = tk.StringVar(value="")' in text
    assert 'StringVar(value="Ac-EEMQRR-NH2")' not in text


def test_integrated_spps_cli_sequence_default_is_blank():
    text = (ROOT / "apps" / "spps_planner_app" / "cli.py").read_text(encoding="utf-8")
    assert 'dest="seq", default=""' in text
    assert 'dest="seq", default="Ac-EEMQRR-NH2"' not in text


def test_complex_builder_has_no_hidden_peptide_default():
    param = inspect.signature(export_complex_builder_package).parameters["peptide_sequence"]
    assert param.default == ""
