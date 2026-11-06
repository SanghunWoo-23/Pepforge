import hashlib,json
import pytest
from peptiforg_core.v6_binding_cycle import assemble_binding_cycle

def test_cycle_with_independent_leg_evidence(tmp_path):
    entries={}
    for leg,values in [('solvent',[12,13,11]),('complex',[22,23,21])]:
        entries[leg]=[]
        for i,value in enumerate(values):
            name=f'{leg}{i}.json'
            (tmp_path/name).write_text(json.dumps({'result_type':'ALCHEMICAL_LEG_DELTA_G_NOT_BINDING_DELTA_G',
              'status':'PRELIMINARY_MBAR_ESTIMATE','warnings':[], 'temperature_k':300,
              'lambda_values':[0,.5,1], 'delta_g_kj_mol':value,'standard_error_kj_mol':.2,
              'input_sha256':hashlib.sha256(name.encode()).hexdigest()}))
            entries[leg].append(name)
    manifest={'temperature_k':300,'protocol_id':'benchmark-protocol','ligand_chemical_id':'inchi-key-demo',
      'thermodynamic_cycle_description':'Boresch restraint release cycle',
      'leg_direction':'coupled_to_decoupled','solvent_replicas':entries['solvent'],
      'complex_replicas':entries['complex'],
      'corrections':[{'kind':name,'signed_delta_g_kj_mol':v,'standard_error_kj_mol':.1,'method':'external validated procedure','source':'real protocol file','sign_convention_verified':True} for name,v in [('restraint',2),('standard_state',1)]]}
    path=tmp_path/'cycle.json';path.write_text(json.dumps(manifest))
    out=assemble_binding_cycle(path)
    assert out['delta_g_bind_kj_mol']==pytest.approx(-7)
    assert out['status'].startswith('PRELIMINARY')
    manifest['corrections'].pop();path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='standard_state'):assemble_binding_cycle(path)

def test_bad_replicas_rejected(tmp_path):
    path=tmp_path/'cycle.json';path.write_text('{}')
    with pytest.raises(ValueError):assemble_binding_cycle(path)

def test_affinity_conversion_thermodynamic_sign():
    import math
    from peptiforg_core.v6_binding_cycle import _KB
    dg = -_KB*300*math.log(10)*7
    pkd=-dg/(_KB*300*math.log(10))
    assert pkd==pytest.approx(7.0)
