import csv
import json
from pathlib import Path

from pepforge_structure_tool.pymol_script import make_pymol_pml
from peptiforg_core.v6_modified_forcefield import evaluate_sdf


def test_pymol_sequence_residue_map(tmp_path):
    path=tmp_path/'input.json'
    path.write_text(json.dumps({'sdf_path':'test.sdf','pdb_path':'test.pdb','atom_ranges':[
        {'token':'dK','kind':'d_std_aa','heavy_start_1based':1,'heavy_end_1based':5},
        {'token':'PEG4','kind':'linker','heavy_start_1based':6,'heavy_end_1based':12},
        {'token':'FITC','kind':'label','heavy_start_1based':13,'heavy_end_1based':20}
    ]}),encoding='utf-8')
    pml=make_pymol_pml(path,prefer='pdb')
    text=pml.read_text()
    assert "resi='3'" in text and "resn='FIT'" in text and 'set seq_view, 1' in text
    with pml.with_name(pml.stem+'_sequence_token_map.tsv').open(encoding='utf-8') as fp:
        rows=list(csv.DictReader(fp,delimiter='\t'))
    assert [r['full_token'] for r in rows]==['dK','PEG4','FITC']


def test_actual_mmff94s_energy(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol=Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol,randomSeed=45)==0
    sdf=tmp_path/'l_alanine.sdf'
    writer=Chem.SDWriter(str(sdf));writer.write(mol);writer.close()
    result=evaluate_sdf(sdf,tmp_path/'audit.json')
    assert result['results'][0]['status']=='EVALUATED'
    assert isinstance(result['results'][0]['energies'][0]['initial_energy_kcal_mol'],float)
    assert result['purpose']=='INTRAMOLECULAR_CONFORMER_ENERGY_ONLY'
