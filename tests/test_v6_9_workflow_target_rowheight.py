from suite_gui.docking_workbench_gui import _clean_protein_sequence, structure_pipeline_df, pdb_to_sequence


def test_target_fasta_sequence_cleaner_accepts_multiline_and_numbers():
    text = '>target protein\n1 MKT ACD\nGGH 20\n'
    assert _clean_protein_sequence(text) == 'MKTACDGGH'


def test_target_sequence_without_coordinates_blocks_local_3d_screening():
    df = structure_pipeline_df('Sequence', 'PDB', '>target\nMKTACDGGH', '', None, None)
    row = df[df['stage'] == '3_3d_screening'].iloc[0]
    assert row['status'] == 'BLOCKED'
    assert 'target coordinates' in str(row['note']).lower()



def test_no_music_note_glyph_in_cys_workflow_doc():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / 'suite_gui' / 'spps_tk_gui.py'
    txt = p.read_text(encoding='utf-8')
    assert '♪' not in txt and '♫' not in txt and '♬' not in txt
    assert 'optional Cys scavenger' in txt
