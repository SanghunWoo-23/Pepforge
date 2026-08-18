import pandas as pd
from suite_gui import docking_workbench_gui as dw

def test_internal_toy_md_removed_and_external_md_label_is_explicit():
    assert not hasattr(dw,'run_builtin_md_lite')
    df=dw.dynamics_summary_label(pd.DataFrame())
    assert 'external MD only' in set(df['value'].astype(str))
