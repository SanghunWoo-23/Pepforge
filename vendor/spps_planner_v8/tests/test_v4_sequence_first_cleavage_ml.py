from pathlib import Path
from suite_gui import experimental_data, ml_advisor_v4


def _add(db, status="parsed"):
    return experimental_data.add_record("cleavage", {"product":"Demo Product","sequence":"Ac-AAAAAA-NH2","scale_mmol":100,"tfa_ml":2850,"tis_ml":0,"water_ml":150,"other_scavengers_json":"{}","cleavage_eq":30,"cleavage_time_h":3,"raw_observation":"synthetic"}, db, status=status)


def test_cleavage_recommendation_is_driven_by_current_sequence_not_product(tmp_path):
    db=tmp_path/"exp.sqlite"; _add(db,"verified")
    result=ml_advisor_v4.cleavage_advice(product="Unrelated Name",sequence="Ac-AAAAAA-NH2",resin="Rink Amide",scale_mmol=1,db_path=db,include_parsed=True)
    rec=result["recommended_condition"]; assert rec is not None and rec["sequence"]=="Ac-AAAAAA-NH2"


def test_empty_sequence_blocks_sequence_apply(tmp_path):
    db=tmp_path/"exp.sqlite"; _add(db,"verified")
    result=ml_advisor_v4.cleavage_advice(product="Anything",sequence="",resin="Rink Amide",scale_mmol=1,db_path=db)
    assert result["recommended_condition"] is None and any("sequence" in w.lower() for w in result["warnings"])


def test_cleavage_ui_syncs_sequence_and_has_short_apply_label():
    src=(Path(__file__).resolve().parents[1]/"suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    assert 'self.clv_sequence.set(_value(getattr(self.gui, "pm_sequence", "")))' in src and 'text="Apply & Update"' in src


def test_loading_ui_mode_can_apply_one_exact_parsed_record_with_confirmation_policy(tmp_path):
    db=tmp_path/"exp.sqlite"
    experimental_data.add_record("loading", {"resin_type":"Trityl/2-CTC resin","amino_acid_raw":"Fmoc-Arg(Pbf)-OH","amino_acid_normalized":"Fmoc-Arg(Pbf)-OH","aa_eq":2,"base":"DIEA","base_eq":4,"loading_time_h":4,"loading_rate_mmol_g":0.52}, db, status="parsed")
    result=ml_advisor_v4.loading_advice("Trityl/2-CTC resin","Fmoc-Arg(Pbf)-OH",target_loading_mmol_g=0.52,db_path=db,include_parsed=True,allow_parsed_apply=True)
    assert result["recommended_condition"]["apply_allowed"] is True


def test_exact_sequence_record_preserves_recorded_composition(tmp_path):
    db=tmp_path/"exp.sqlite"; _add(db,"verified")
    result=ml_advisor_v4.cleavage_advice(product="Demo Product",sequence="Ac-AAAAAA-NH2",resin="Rink Amide",scale_mmol=500,db_path=db,include_parsed=True)
    rec=result["recommended_condition"]; assert rec is not None and rec["cleavage_eq"]==30.0 and rec["cleavage_time_h"]==3.0 and rec["composition_pct"]=={"TFA":95.0,"Water":5.0} and rec["scaled_total_ml"]==15000.0


def test_stale_product_name_cannot_override_different_sequence(tmp_path):
    db=tmp_path/"exp.sqlite"; _add(db,"verified")
    result=ml_advisor_v4.cleavage_advice(product="Demo Product",sequence="Ac-GGGGGG-NH2",resin="Rink Amide",scale_mmol=500,db_path=db,include_parsed=True)
    rec=result["recommended_condition"]; assert rec is not None and rec["condition_source"]=="chemistry_rule_reference"
