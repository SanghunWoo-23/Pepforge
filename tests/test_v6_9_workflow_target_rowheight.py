from suite_gui.docking_workbench_gui import _clean_protein_sequence, structure_pipeline_df, pdb_to_sequence


def test_target_fasta_sequence_cleaner_accepts_multiline_and_numbers():
    text = '>target protein\n1 MKT ACD\nGGH 20\n'
    assert _clean_protein_sequence(text) == 'MKTACDGGH'


def test_target_sequence_peptide_pdb_pipeline_is_not_rejected():
    df = structure_pipeline_df('Sequence', 'PDB', '>target\nMKTACDGGH', '', None, None)
    statuses = set(df['status'].astype(str))
    assert 'READY_TO_PREPARE' in statuses
    assert any('AlphaFold3' in str(x) for x in df['engine'])


def test_no_music_note_glyph_in_cys_workflow_doc():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / 'suite_gui' / 'spps_tk_gui.py'
    txt = p.read_text(encoding='utf-8')
    assert '♪' not in txt and '♫' not in txt and '♬' not in txt
    assert 'optional Cys scavenger' in txt
