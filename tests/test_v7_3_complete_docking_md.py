import pandas as pd
from suite_gui import docking_workbench_gui as dw

def test_modified_tokens_are_preserved_without_canonical_surrogate():
    rows=dw._split_peptide_model_tokens('FITC-Cha-AEEA-dK-NH2')
    by_token={str(r['token']).upper():r['class'] for r in rows}
    assert by_token['FITC']=='label'
    assert by_token['CHA']=='non_natural_aa'
    assert by_token['AEEA']=='linker'
    assert by_token['DK']=='d_std_aa'

def test_sequence_target_does_not_fabricate_3d_atoms():
    resolved=dw.resolve_target_input('Sequence','', 'MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE')
    assert resolved['mode']=='Sequence' and resolved['status']=='ok'
    assert isinstance(resolved['atoms'],pd.DataFrame) and resolved['atoms'].empty

def test_legacy_fake_aliases_are_removed():
    for name in ['run_vina_like_pose_search','prodigy_like_summary_df','gromacs_like_md_summary_label','run_builtin_md_lite']:
        assert not hasattr(dw,name)
