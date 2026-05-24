from __future__ import annotations
from pathlib import Path
from collections import Counter
import re
import joblib
import numpy as np

AA=set('ACDEFGHIKLMNPQRSTVWY')
HYDRO=set('AVILMFWY'); AROMATIC=set('FWYH'); POS=set('KRH'); NEG=set('DE'); ANCHOR=set('FWYHILV')
FEATURE_NAMES=[
    'length','hydrophobic_ratio','aromatic_ratio','positive_ratio','negative_ratio','charge_norm',
    'anchor_ratio','gly_ratio','pro_ratio','cys_ratio','acidic_basic_balance','motif_RGD','motif_KLV','motif_EEMQR',
    'motif_PXXP_like','motif_LXXLL_like','dipeptide_DE','dipeptide_KK_RR','aromatic_cluster'
]

def feature_dict(seq:str):
    c=[x for x in seq.upper() if x in AA]; n=max(1,len(c)); s=''.join(c)
    pos=sum(x in POS for x in c); neg=sum(x in NEG for x in c)
    return {
        'length':len(c)/30.0,
        'hydrophobic_ratio':sum(x in HYDRO for x in c)/n,
        'aromatic_ratio':sum(x in AROMATIC for x in c)/n,
        'positive_ratio':pos/n,
        'negative_ratio':neg/n,
        'charge_norm':(pos-neg)/n,
        'anchor_ratio':sum(x in ANCHOR for x in c)/n,
        'gly_ratio':c.count('G')/n,
        'pro_ratio':c.count('P')/n,
        'cys_ratio':c.count('C')/n,
        'acidic_basic_balance':1.0-min(1.0,abs(pos-neg)/max(1,pos+neg)),
        'motif_RGD':float('RGD' in s),
        'motif_KLV':float('KLV' in s),
        'motif_EEMQR':float('EEMQR' in s),
        'motif_PXXP_like':float(re.search(r'P..P',s) is not None),
        'motif_LXXLL_like':float(re.search(r'L..LL',s) is not None),
        'dipeptide_DE':float('DE' in s or 'ED' in s),
        'dipeptide_KK_RR':float('KK' in s or 'RR' in s),
        'aromatic_cluster':float(re.search(r'[FWYH].{0,2}[FWYH]',s) is not None),
    }

def predict(seq:str):
    here=Path(__file__).resolve().parent
    payload=joblib.load(here/'pepforge_ml_prior_baseline.joblib')
    model=payload['model']; names=payload.get('feature_names',FEATURE_NAMES)
    f=feature_dict(seq)
    X=np.array([[f[n] for n in names]])
    return float(np.tanh(model.predict(X)[0]))

if __name__=='__main__':
    import sys
    seq=sys.argv[1] if len(sys.argv)>1 else 'RGDEEMQRKLVF'
    print(seq, predict(seq))
