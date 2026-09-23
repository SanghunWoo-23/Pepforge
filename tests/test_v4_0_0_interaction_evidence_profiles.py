from __future__ import annotations
import math
import pandas as pd

from peptiforg_core.interaction_evidence import profile, analyze_interaction_evidence, interaction_summary


def _df(rows):
    return pd.DataFrame(rows, columns=['atom','resn','chain','resi','x','y','z','element','aa'])


def test_profiles_keep_manual_and_tool_cutoffs_distinct():
    manual=profile('CONSERVATIVE_MANUAL'); tool=profile('TOOL_COMPATIBLE')
    assert manual.hbond_da_max_A == 3.5
    assert tool.hbond_da_max_A == 4.1
    assert manual.salt_bridge_max_A == 4.0
    assert tool.salt_bridge_max_A == 5.5
    assert manual.pi_pi_centroid_max_A == 5.0
    assert tool.cation_pi_max_A == 6.0


def test_salt_bridge_represents_same_pair_over_hbond():
    target=_df([
        ['OD1','ASP','A','10',0,0,0,'O','D'],
        ['OD2','ASP','A','10',0.4,0,0,'O','D'],
    ])
    peptide=_df([
        ['NZ','LYS','B','2',3.2,0,0,'N','K'],
    ])
    ev=analyze_interaction_evidence(target, peptide, representative_only=True)
    assert 'salt_bridge' in set(ev.interaction)
    pair=ev[(ev.target_residue.str.contains('10ASP')) & (ev.peptide_residue.str.contains('2LYS'))]
    assert list(pair[pair.interaction!='clash'].interaction) == ['salt_bridge']


def test_hbond_without_hydrogen_stays_distance_candidate():
    target=_df([['OD1','ASN','A','4',0,0,0,'O','N']])
    peptide=_df([['ND2','ASN','B','8',3.0,0,0,'N','N']])
    ev=analyze_interaction_evidence(target, peptide)
    hb=ev[ev.interaction=='hydrogen_bond'].iloc[0]
    assert hb.evidence_level == 'candidate'
    assert hb.geometry_status == 'distance_candidate_H_not_available'


def test_serious_vdw_overlap_is_structure_warning_not_favorable_contact():
    target=_df([['CB','ALA','A','1',0,0,0,'C','A']])
    peptide=_df([['CB','ALA','B','1',2.8,0,0,'C','A']])
    ev=analyze_interaction_evidence(target, peptide)
    clash=ev[ev.interaction=='clash'].iloc[0]
    assert clash.vdw_overlap_A >= 0.4
    assert clash.evidence_level == 'structure_warning'
    assert interaction_summary(ev)['structure_warning_count'] >= 1


def _ring(chain, resi, z=0.0, shift_x=0.0):
    names=['CG','CD1','CE1','CZ','CE2','CD2']
    pts=[]
    for i,name in enumerate(names):
        ang=2*math.pi*i/6
        pts.append([name,'PHE',chain,str(resi),shift_x+1.4*math.cos(ang),1.4*math.sin(ang),z,'C','F'])
    return pts


def test_pi_pi_requires_centroid_and_orientation_geometry():
    target=_df(_ring('A',1,0.0))
    peptide=_df(_ring('B',2,4.0))
    ev=analyze_interaction_evidence(target, peptide)
    pi=ev[ev.interaction=='pi_pi'].iloc[0]
    assert pi.evidence_level == 'geometry_supported'
    assert pi.distance_A <= 5.0
    assert pi.plane_angle_deg <= 30.0
    assert pi.offset_A <= 2.0
