from __future__ import annotations
from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

FEATURE_NAMES = [
    'length','hydrophobic_ratio','aromatic_ratio','positive_ratio','negative_ratio','charge_norm',
    'anchor_ratio','gly_ratio','pro_ratio','cys_ratio','acidic_basic_balance',
    'motif_RGD','motif_KLV','motif_EEMQR','motif_PXXP_like','motif_LXXLL_like',
    'dipeptide_DE','dipeptide_KK_RR','aromatic_cluster'
]

HERE = Path(__file__).resolve().parent
csv_path = HERE / 'peptide_ml_prior_training_data.csv'
out_path = HERE / 'pepforge_ml_prior_baseline.joblib'

df = pd.read_csv(csv_path)
X = df[FEATURE_NAMES].values
y = df['ml_prior_target'].values
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestRegressor(n_estimators=160, max_depth=9, min_samples_leaf=2, random_state=42, n_jobs=-1)
model.fit(Xtr, ytr)
pred = model.predict(Xte)
print('R2 =', round(r2_score(yte, pred), 4))
print('MAE =', round(mean_absolute_error(yte, pred), 4))
joblib.dump({'model': model, 'feature_names': FEATURE_NAMES, 'version': 'pretrained-lite-v0.1'}, out_path)
print('Saved:', out_path)
