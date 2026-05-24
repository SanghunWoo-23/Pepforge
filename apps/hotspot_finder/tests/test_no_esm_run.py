from pathlib import Path
from sequence_hotspot_finder.engine import analyze_input, load_config


def test_no_esm_run(tmp_path):
    cfg = load_config('data/default_config.json')
    cfg['use_esm'] = False
    result = analyze_input('>x\nAc-K-dA-Ahx-W-FITC', config=cfg, token_db_path='data/token_db.csv', sidechain_mod_db_path='data/sidechain_mod_db.csv', outdir=tmp_path)
    assert Path(result['full_csv']).exists()
    assert Path(result['top_csv']).exists()
    assert Path(result['zip_path']).exists()
    assert not result['full_df'].empty
