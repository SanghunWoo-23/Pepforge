from pathlib import Path
APP_DIR = Path(__file__).resolve().parents[1]
from sequence_hotspot_finder.engine import analyze_input, load_config


def test_no_esm_run(tmp_path):
    cfg = load_config(APP_DIR / 'data/default_config.json')
    cfg['use_esm'] = False
    result = analyze_input('>x\nAc-K-dA-Ahx-W-FITC', config=cfg, token_db_path=APP_DIR / 'data/token_db.csv', sidechain_mod_db_path=APP_DIR / 'data/sidechain_mod_db.csv', outdir=tmp_path)
    assert Path(result['full_csv']).exists()
    assert Path(result['top_csv']).exists()
    assert Path(result['zip_path']).exists()
    assert not result['full_df'].empty
