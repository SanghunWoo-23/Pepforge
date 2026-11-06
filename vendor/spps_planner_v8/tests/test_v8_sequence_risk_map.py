"""V8 Alpha 1 boundary and contract checks."""
from suite_gui.sequence_risk_map_v8 import build_sequence_risk_map


def test_residue_mapping_is_one_based_and_n_to_c():
    m = build_sequence_risk_map("Ac-ADGWWWWWW-NH2")
    assert m["nterm"] == "Ac"
    assert m["residue_count"] == 9
    assert [r["position"] for r in m["residues"]] == list(range(1, 10))
    assert m["residues"][1]["token"] == "D"
    assert any(f["rule_id"] == "SEQ-ASPARTIMIDE" and f["positions"] == [2, 3] for f in m["findings"])


def test_provenance_never_pretends_rules_are_experiments():
    m = build_sequence_risk_map("CCCCCC")
    assert m["findings"]
    assert all(f["provenance"]["source_class"] == "Rule-based" for f in m["findings"])
    assert all(not f["provenance"]["experimental_observation"] for f in m["findings"])
    assert all(not f["action_applied"] for f in m["findings"])
    assert not m["recommendations_auto_applied"]


def test_output_is_repeatable_and_references_exist():
    a = build_sequence_risk_map("VILFWYVILFWY")
    b = build_sequence_risk_map("VILFWYVILFWY")
    assert a == b
    ids = {f["id"] for f in a["findings"]}
    assert all(ref["finding_id"] in ids for r in a["residues"] for ref in r["finding_refs"])
    assert any(r["risk_level"] != "NONE" for r in a["residues"])


def test_empty_sequence_does_not_claim_risk_probability():
    m = build_sequence_risk_map("")
    assert m["residue_count"] == 0
    assert m["residues"] == []
    assert "NOT probability" in m["score_meaning"]
