import pandas as pd
from sequence_hotspot_finder.parser import parse_sequence


def test_modified_parser():
    db = pd.read_csv('data/token_db.csv')
    df, model = parse_sequence('Ac-K-dA-Ahx-W-FITC', db)
    assert model == 'KAXW'
    assert df.loc[2, 'is_d_form'] == 1
    assert df.loc[3, 'is_linker'] == 1
    assert df.loc[5, 'is_label'] == 1


def test_sidechain_parser():
    db = pd.read_csv('data/token_db.csv')
    df, model = parse_sequence('K[Biotin]-dR-W-NH2', db)
    assert df.loc[0, 'sidechain_mod'] == 'Biotin'
    assert model == 'KRW'
