from pathlib import Path
import importlib.util
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem
from peptiforg_core.v6_flexible_refinement import sample_flexible_conformers

def test_torsion_search(tmp_path):
    m=Chem.AddHs(Chem.MolFromSmiles('NCC(=O)NCC(=O)O'))
    assert AllChem.EmbedMolecule(m,randomSeed=42)==0
    s=tmp_path/'in.sdf';w=Chem.SDWriter(str(s));w.write(m);w.close()
    out=tmp_path/'flex.sdf'; r=sample_flexible_conformers(s,out,samples=3)
    assert r['successful_conformers']>0
    assert out.exists()
    assert all(x.HasProp('Pepforge_MMFF94s_Internal_kcal_mol') for x in Chem.SDMolSupplier(str(out),removeHs=False))

def test_no_fake_parameters(tmp_path):
    s=tmp_path/'bad.sdf';s.write_text('invalid')
    with pytest.raises(ValueError):sample_flexible_conformers(s,tmp_path/'out.sdf')

def test_installer_dry_run():
    path=Path(__file__).resolve().parents[1]/'INSTALL_SCIENCE_ENGINES.py'
    spec=importlib.util.spec_from_file_location('installer',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    p=mod.plan('windows',None)
    assert 'warning' in p and p['steps']==[] or p['manager']
    q=mod.plan('linux','mamba')
    assert any('openff-toolkit' in x for x in q['steps'])

def test_torsion_docking_end_to_end(tmp_path):
    import importlib.util
    from tests.test_v6_ensemble_docking import _inputs
    receptor,sdf=_inputs(tmp_path)
    f=Path(__file__).resolve().parents[1]/'RUN_TORSION_ENSEMBLE_DOCKING.py'
    spec=importlib.util.spec_from_file_location('tdock',f); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    result=m.run(receptor,sdf,tmp_path/'torsion_run',samples=2,max_structures=1,poses=1,max_candidates=6)
    assert result['status']=='COMPLETED', result
    assert result['successful_cases']==1
