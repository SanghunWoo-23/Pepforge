import json
import pytest
from peptiforg_core.v6_abfe_protocol_audit import audit_abfe_protocol


def build(tmp_path):
    sh={'ligand_chemical_id':'pep-dK-Aib','forcefield_id':'amber14-gaff2-identified',
        'water_model':'tip3p','temperature_k':300.,'pressure_bar':1.,
        'charge_model':'am1bcc','ligand_formal_charge':0,'alchemical_protocol_id':'boresch-v1'}
    legs={}
    for leg in ('solvent','complex'):
        legs[leg]=[{'leg':leg,'endpoint_start':'fully_interacting','endpoint_end':'decoupled',
                    'electrostatics_schedule':[0,0.5,1], 'sterics_schedule':[0,0.5,1],
                    'softcore_model':'beutler','sampling_method':'HREX','replica_seed':i,
                    'restraint_protocol_id':'none' if leg=='solvent' else 'boresch-anchors-sha',
                    'system_sha256':f'{i+1:064x}'} for i in range(3)]
    m={'ligand_chemical_id':sh['ligand_chemical_id'],'temperature_k':300.,
       'solvent_replicas':['s0','s1','s2'],'complex_replicas':['c0','c1','c2'],
       'corrections':[{'correction_id':'boresch-net','accounting_stage':'separate_cycle_term'}],
       'strict_protocol_evidence':{'schema_version':1,'shared':sh,'legs':legs,
                                    'independent_replica_initializations':True}}
    p=tmp_path/'m.json';p.write_text(json.dumps(m));return p,m

def test_valid(tmp_path):
    p,m=build(tmp_path)
    assert audit_abfe_protocol(p)['status'].startswith('PROTOCOL_')

def test_duplicated_correction(tmp_path):
    p,m=build(tmp_path);m['corrections']*=2;p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Duplicate'):audit_abfe_protocol(p)

def test_charge_review(tmp_path):
    p,m=build(tmp_path);m['strict_protocol_evidence']['shared']['ligand_formal_charge']=1;p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Charged'):audit_abfe_protocol(p)

def test_wrong_endpoint(tmp_path):
    p,m=build(tmp_path);m['strict_protocol_evidence']['legs']['complex'][1]['endpoint_start']='decoupled';p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='endpoints'):audit_abfe_protocol(p)

def test_missing_restraint(tmp_path):
    p,m=build(tmp_path);m['strict_protocol_evidence']['legs']['complex'][0]['restraint_protocol_id']='none';p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='restraint'):audit_abfe_protocol(p)

def test_duplicate_seed(tmp_path):
    p,m=build(tmp_path);m['strict_protocol_evidence']['legs']['solvent'][1]['replica_seed']=0;p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Duplicate replica'):audit_abfe_protocol(p)
