from pathlib import Path
from suite_gui.docking_workbench_gui import (
    all_atom_parameter_requirements_df,
    all_atom_validation_template_files,
    parse_external_validation_file,
)


def test_all_atom_parameter_requirements_flags_modified_tokens():
    df = all_atom_parameter_requirements_df('Ac-dK-Aib-PEG2-FAM-R-NH2')
    assert not df.empty
    assert any(df['status'].astype(str).str.contains('parameter', case=False, na=False))
    assert any(df['token'].astype(str).str.contains('FAM', case=False, na=False))


def test_validation_templates_include_major_external_workflows():
    files = all_atom_validation_template_files()
    assert 'gromacs/em.mdp' in files
    assert 'amber/min.in' in files
    assert 'namd/short_validation.conf' in files
    assert 'README_ALL_ATOM_VALIDATION.txt' in files


def test_parse_external_validation_csv_numeric_summary(tmp_path: Path):
    p = tmp_path / 'rmsd.csv'
    p.write_text('time,rmsd\n0,0.1\n1,0.2\n', encoding='utf-8')
    df = parse_external_validation_file(p)
    assert not df.empty
    assert any(df['field'].astype(str).str.contains('rmsd_last', na=False))
