from pathlib import Path
APP_DIR = Path(__file__).resolve().parents[1]
import pandas as pd
from sequence_hotspot_finder.validation import validate_token_db, validate_config


def test_token_db_validation():
    df = pd.read_csv(APP_DIR / 'data/token_db.csv')
    assert isinstance(validate_token_db(df), list)


def test_config_validation():
    assert isinstance(validate_config({'window_size':900,'overlap':150,'batch_size':4,'top_n':30}), list)
