from __future__ import annotations

import math
import re
from dataclasses import asdict
from typing import Any

import pandas as pd

LIQUID_ALIASES = {
    'diea','dipea','n,n-diisopropylethylamine','diisopropylethylamine',
    'dic','n,n-diisopropylcarbodiimide','diisopropylcarbodiimide',
    'dmf','dcm','mc','mc/dcm','methylene chloride','dichloromethane',
    'nmp','tfa','tis','edt','acoh','acetic acid','tfe','tee',
    'piperidine','water','dw','dw / water','h2o','meoh','methanol',
    'acn','mecn','thioanisole','ethanedithiol','triisopropylsilane',
}
LIQUID_HINTS = ('solvent','solution','liquid','cleavage acid','cation scavenger','base')
SOLID_EXCEPTIONS = {'hobt','hbtu','hatu','hctu','tbtu','tstu','tntu','comu','resin','phenol'}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        s = str(v).strip()
        if not s or s.lower() in {'nan','none','n/a'}:
            return default
        s = re.sub(r'[^0-9eE+\-.]', '', s)
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def _fmt(v: Any, digits: int = 3) -> str:
    x = _num(v, math.nan)
    if math.isnan(x) or abs(x) < 1e-12:
        return ''
    s = f'{x:.{digits}f}'.rstrip('0').rstrip('.')
    return s or '0'


def _base(text: Any) -> str:
    s = str(text or '').strip().lower()
    s = s.replace('／','/').replace('–','-').replace('—','-')
    s = re.sub(r'\s+', ' ', s)
    return s


def is_liquid(name: Any = '', cls: Any = '', state: Any = '', unit: Any = '', reagent: Any = '') -> bool:
    names = [_base(name), _base(reagent)]
    cls_s = _base(cls)
    state_s = _base(state)
    unit_s = _base(unit)
    for n in names:
        if not n:
            continue
        # Strip component suffix but keep chemical identity.
        n0 = n.replace(' - cleavage cocktail component','').strip()
        if n0 in SOLID_EXCEPTIONS:
            return False
        if n0 in LIQUID_ALIASES:
            return True
        if any(alias in n0 for alias in ('dw / water','mc/dcm')):
            return True
    if unit_s == 'ml':
        return True
    if state_s in {'liquid','solution','solvent'}:
        return True
    if any(h in cls_s for h in LIQUID_HINTS):
        # But HOBt/HBTU/etc must stay solid.
        if any(_base(x) in SOLID_EXCEPTIONS for x in names):
            return False
        return True
    return False


def resin_label(value: Any) -> str:
    """Return the exact user-facing resin label, while rejecting removed legacy alias."""
    text = str(value or '').strip()
    if not text:
        return 'Rink Amide AM'
    if text == 'CTC(합성용)':
        # Deleted old label: migrate saved projects to the surviving synthesizer profile.
        return 'CTC(합성기)'
    return text


def normalize_operator_amounts(df: pd.DataFrame | None, user_resin: str | None = None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy().astype(object).where(pd.notna(df), '')
    if out.empty:
        return out
    if user_resin and 'step' in out.columns and 'material' in out.columns:
        mask = out['step'].astype(str).str.strip().str.lower().eq('resin')
        if mask.any():
            out.loc[mask, 'material'] = resin_label(user_resin)
            if 'reagent' in out.columns:
                out.loc[mask, 'reagent'] = resin_label(user_resin)
    for idx, r in out.iterrows():
        mat = r.get('material', r.get('component',''))
        cls = r.get('class', r.get('role',''))
        state = r.get('physical_state','')
        unit = r.get('unit','')
        reagent = r.get('reagent','')
        if not is_liquid(mat, cls, state, unit, reagent):
            continue
        density = _num(r.get('density_g_mL', r.get('Density(g/mL)', '')), 0.0)
        g = _num(r.get('planned_g', r.get('total_g', r.get('approx_g',''))), 0.0)
        ml = _num(r.get('planned_mL', r.get('total_mL', r.get('volume_mL',''))), 0.0)
        if ml <= 0 and g > 0 and density > 0:
            ml = g / density
            for c in ('planned_mL','total_mL','volume_mL'):
                if c in out.columns:
                    out.at[idx, c] = ml
        for c in ('planned_g','planned_mg','approx_g','total_g'):
            if c in out.columns:
                out.at[idx, c] = ''
        if 'unit' in out.columns:
            out.at[idx, 'unit'] = 'mL'
    return out


def ordered_step_materials(df: pd.DataFrame | None, user_resin: str | None = None) -> pd.DataFrame:
    if df is None or getattr(df, 'empty', True):
        return pd.DataFrame() if df is None else df.copy()
    out = normalize_operator_amounts(df, user_resin).copy()
    def step_rank(v: Any) -> int:
        s = str(v or '').strip().lower()
        if s == 'resin': return -100000
        if s == 'cleavage': return 100000
        try: return int(float(s)) * 100
        except Exception: return 90000
    def phase_rank(r: pd.Series) -> int:
        step = str(r.get('step','')).strip().lower()
        phase = str(r.get('phase','')).strip().lower()
        src = str(r.get('source','')).strip().lower()
        cls = str(r.get('class','')).strip().lower()
        mat = str(r.get('material','')).strip().lower()
        if step == 'resin': return 0
        if 'swell' in phase: return 1
        if 'loading' in phase and ('aa' in cls or 'unit' in src): return 10
        if 'loading' in phase and ('base' in cls or 'aux' in src): return 11
        if 'deprotection' in phase and 'piperidine' in mat: return 20
        if 'deprotection' in phase: return 21
        if 'dmf wash' in phase and 'post' not in phase: return 30
        if 'regular aa' in phase or 'coupling' in phase:
            if 'aa' in cls or 'unit' in src: return 40
            if 'coupling reagent' in cls: return 41
            if 'catalyst' in cls: return 42
            if 'base' in cls: return 43
            if 'solvent' in cls: return 44
            return 45
        if 'synthesis' in phase or 'reaction' in phase: return 46
        if 'post' in phase: return 50
        if 'final' in phase: return 60
        if 'cleavage' in phase: return 1000
        return 100
    out['_sort_key'] = out.apply(lambda r: step_rank(r.get('step','')) + phase_rank(r), axis=1)
    out['_orig_key'] = range(len(out))
    out = out.sort_values(['_sort_key','_orig_key'], kind='mergesort').drop(columns=['_sort_key','_orig_key'])
    preferred = ['step','material','class','MW','density_g_mL','planned_mmol','planned_g','planned_mL','unit','use_count','repeat','phase','note','source']
    cols = [c for c in preferred if c in out.columns] + [c for c in out.columns if c not in preferred]
    return out[cols].reset_index(drop=True)


def total_materials_display(df: pd.DataFrame | None, user_resin: str | None = None) -> pd.DataFrame:
    if df is None or getattr(df, 'empty', True):
        return pd.DataFrame(columns=['material','class','MW','Density(g/mL)','total mmol','total amount','unit','note'])
    d = normalize_operator_amounts(df, user_resin)
    rows = []
    for _, r in d.iterrows():
        mat = str(r.get('material','')).strip()
        if not mat:
            continue
        cls = r.get('class','')
        liq = is_liquid(mat, cls, r.get('physical_state',''), r.get('unit',''), r.get('reagent',''))
        ml = _num(r.get('planned_mL', r.get('total_mL','')), 0.0)
        g = _num(r.get('planned_g', r.get('total_g','')), 0.0)
        amount = f'{_fmt(ml,3)} mL' if liq and ml > 0 else (f'{_fmt(g,4)} g' if g > 0 else '')
        rows.append({
            'material': mat,
            'class': cls,
            'MW': r.get('MW',''),
            'Density(g/mL)': r.get('density_g_mL', r.get('Density(g/mL)','')),
            'total mmol': r.get('planned_mmol', r.get('total_mmol','')),
            'total amount': amount,
            'unit': 'mL' if liq else r.get('unit',''),
            'note': r.get('warning','') or r.get('source','') or r.get('note',''),
        })
    return pd.DataFrame(rows, columns=['material','class','MW','Density(g/mL)','total mmol','total amount','unit','note'])


def concise_plan(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy().astype(object).where(pd.notna(df), '')
    # Keep plan as synthesis steps, not metadata dump.
    drop_cols = [c for c in out.columns if c in {'app_version','project','peptide','sequence','lot_no','scale_mmol','resin_text','resin_loading_mmol_g','loading_aa_eq','loading_diea_eq'}]
    if drop_cols:
        out = out.drop(columns=drop_cols, errors='ignore')
    return out
