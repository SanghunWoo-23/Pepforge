import pytest
from peptiforg_core.v6_ff_ensemble import refine_sdf_ensemble

def test_ensemble_real_mmff(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol=Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol,randomSeed=10)==0
    source=tmp_path/'input.sdf'
    writer=Chem.SDWriter(str(source));writer.write(mol);writer.close()
    result=refine_sdf_ensemble(source,tmp_path/'out',conformers=3,seed=42)
    assert result['results'][0]['generated_count']>=1
    assert (tmp_path/'out/mmff94s_conformers.sdf').exists()
    assert result['output_sha256']

def test_invalid_and_output_guard(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol=Chem.AddHs(Chem.MolFromSmiles('CCO'));AllChem.EmbedMolecule(mol,randomSeed=1)
    source=tmp_path/'input.sdf';w=Chem.SDWriter(str(source));w.write(mol);w.close()
    with pytest.raises(ValueError):refine_sdf_ensemble(source,tmp_path/'out',conformers=0)
    (tmp_path/'out').mkdir();(tmp_path/'out'/'old.txt').write_text('x')
    with pytest.raises(ValueError):refine_sdf_ensemble(source,tmp_path/'out')

def test_best_converged_and_stereo_audit(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol, randomSeed=99) == 0
    sdf = tmp_path/'stereo.sdf'
    w = Chem.SDWriter(str(sdf)); w.write(mol); w.close()
    report = refine_sdf_ensemble(sdf, tmp_path/'refined', conformers=5, seed=123)
    rows = report['results'][0]['conformers']
    assert all('stereochemistry_preserved' in row for row in rows)
    assert report['best_converged_count'] == 1
    best = list(Chem.SDMolSupplier(str(tmp_path/'refined/mmff94s_best_converged.sdf'), removeHs=False))
    assert len(best) == 1 and best[0] is not None
    assert report['results'][0]['best_converged_conformer_id'] is not None


def test_existing_file_output_rejected_cleanly(tmp_path):
    from rdkit import Chem
    mol = Chem.MolFromSmiles('CCO')
    sdf = tmp_path/'input.sdf'; w=Chem.SDWriter(str(sdf)); w.write(mol); w.close()
    output = tmp_path/'output'; output.write_text('no overwrite')
    with pytest.raises(ValueError, match='output directory'):
        refine_sdf_ensemble(sdf, output)
    assert output.read_text() == 'no overwrite'


def test_diversity_sdf_and_audit(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)N[C@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol, randomSeed=22) == 0
    sdf = tmp_path/'peptide.sdf'
    with Chem.SDWriter(str(sdf)) as writer:
        writer.write(mol)
    report = refine_sdf_ensemble(sdf, tmp_path/'ensemble', conformers=12, seed=41,
                                 diversity_rmsd=0.3, energy_window_kcal_mol=100)
    ids = report['results'][0]['diverse_conformer_ids']
    diverse = list(Chem.SDMolSupplier(str(tmp_path/'ensemble/mmff94s_diverse_converged.sdf'), removeHs=False))
    assert len(diverse) == len(ids) == report['diverse_converged_count']
    assert all(m is not None for m in diverse)
    assert report['diverse_converged_sha256']
    assert report['results'][0]['best_converged_conformer_id'] in ids


def test_invalid_diversity_parameters_do_not_write(tmp_path):
    from rdkit import Chem
    mol = Chem.MolFromSmiles('CCO')
    sdf = tmp_path/'input.sdf'
    with Chem.SDWriter(str(sdf)) as writer:
        writer.write(mol)
    for keyword in ({'diversity_rmsd': 0}, {'energy_window_kcal_mol': float('nan')},
                    {'energy_window_kcal_mol': -1}):
        with pytest.raises(ValueError):
            refine_sdf_ensemble(sdf,tmp_path/'out',**keyword)
    assert not (tmp_path/'out').exists()
