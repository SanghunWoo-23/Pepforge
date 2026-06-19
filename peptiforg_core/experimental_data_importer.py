
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import csv, json, re, statistics

EXPERIMENTAL_IMPORT_VERSION = "3.7.0"
UNIT_TO_NM = {"pm":0.001,"nm":1.0,"um":1000.0,"µm":1000.0,"μm":1000.0,"mm":1000000.0,"m":1000000000.0}

def _float_or_none(v: Any):
    try:
        if v is None: return None
        s=str(v).strip().replace(',','')
        s=re.sub(r'^[<>=~ ]+', '', s)
        if not s or s.lower() in {'nan','none','null','na','n/a','-'}: return None
        return float(s)
    except Exception: return None

def normalize_unit_to_nm(value: Any, unit: Any='nM'):
    v=_float_or_none(value)
    if v is None: return None
    u=str(unit or 'nM').strip().lower().replace('μ','u').replace('µ','u')
    return v * UNIT_TO_NM.get(u, 1.0)

def potency_class_from_nm(nm):
    v=_float_or_none(nm)
    if v is None or v <= 0: return 'unknown'
    if v <= 10: return 'very_strong_nM'
    if v <= 100: return 'strong_nM'
    if v <= 1000: return 'sub_uM'
    if v <= 10000: return 'uM_range'
    return 'weak_or_inactive'

def _read_csv_rows(path: str|Path|None):
    if not path: return []
    p=Path(path)
    if not p.exists(): return []
    sample=p.read_text(encoding='utf-8', errors='ignore')[:4096]
    delimiter='\t' if sample.count('\t') > sample.count(',') else ','
    with p.open('r', encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f, delimiter=delimiter))

def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]]=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None: fieldnames=list(rows[0].keys()) if rows else ['note']
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    return str(path)

def _write_json(path: Path, payload: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8'); return str(path)

def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8'); return str(path)

def candidate_id(row: dict[str, Any], fallback: str):
    for k in ['candidate_id','peptide_id','id','name','sample_id','compound_id']:
        if row.get(k): return str(row.get(k))
    if row.get('sequence'): return str(row.get('sequence'))[:48]
    return fallback

def import_experimental_rows(path: str|Path):
    rows=_read_csv_rows(path); out=[]
    for i,r in enumerate(rows, start=1):
        lower={str(k).lower().strip():v for k,v in r.items() if k is not None}
        cid=candidate_id(lower, f'EXP_{i:04d}')
        target=lower.get('target') or lower.get('protein') or lower.get('receptor') or ''
        assay=lower.get('assay_type') or lower.get('assay') or lower.get('method') or ''
        value_type=lower.get('value_type') or lower.get('affinity_type') or lower.get('metric') or 'Kd'
        value=lower.get('value') or lower.get('affinity_value') or lower.get('kd') or lower.get('ic50') or lower.get('ec50')
        unit=lower.get('unit') or lower.get('affinity_unit') or 'nM'
        nm=normalize_unit_to_nm(value, unit)
        out.append({'candidate_id':cid,'sequence':lower.get('sequence') or lower.get('peptide') or '', 'target':target,'assay_type':assay,'value_type':value_type,'value':value or '', 'unit':unit,'value_nM':nm,'potency_class':potency_class_from_nm(nm),'replicate_id':lower.get('replicate_id') or lower.get('replicate') or '', 'condition':lower.get('condition') or lower.get('buffer') or lower.get('notes') or '', 'source':lower.get('source') or lower.get('reference') or '', 'raw_row':i})
    return out

def summarize_experimental_data(rows):
    by_candidate={}; by_target={}; assay_types=set()
    for r in rows:
        cid=str(r.get('candidate_id')); v=_float_or_none(r.get('value_nM'))
        if v is not None: by_candidate.setdefault(cid, []).append(v)
        if r.get('target'): by_target[str(r.get('target'))]=by_target.get(str(r.get('target')),0)+1
        if r.get('assay_type'): assay_types.add(str(r.get('assay_type')))
    cand=[]
    for cid, vals in by_candidate.items():
        med=statistics.median(vals)
        cand.append({'candidate_id':cid,'n':len(vals),'median_nM':med,'min_nM':min(vals),'max_nM':max(vals),'potency_class':potency_class_from_nm(med)})
    cand.sort(key=lambda r: _float_or_none(r.get('median_nM')) or 1e99)
    warnings=[]
    if len(assay_types)>1: warnings.append('mixed_assay_types_review_before_direct_comparison')
    if not rows: warnings.append('no_experimental_rows_imported')
    return {'pepforge_version':EXPERIMENTAL_IMPORT_VERSION,'record_count':len(rows),'candidate_count':len(by_candidate),'target_counts':by_target,'assay_types':sorted(assay_types),'warnings':warnings,'candidate_summary':cand,'claim_boundary':'Experimental importer organizes user-provided assay data. Assay quality and method context still determine claim strength.'}

def make_experimental_template(output_dir: str|Path):
    out=Path(output_dir); out.mkdir(parents=True, exist_ok=True); path=out/'experimental_data_import_template.csv'
    _write_csv(path, [{'candidate_id':'PDE_0001','sequence':'Ac-AAAA-NH2','target':'example_target','assay_type':'SPR','value_type':'Kd','value':'85','unit':'nM','replicate_id':'R1','condition':'example condition','source':'internal_or_reference_id','notes':'replace this row'}])
    return str(path)

def export_experimental_import_package(input_csv: str|Path, output_dir: str|Path):
    out=Path(output_dir)/'experimental_data_import'; out.mkdir(parents=True, exist_ok=True)
    rows=import_experimental_rows(input_csv); summary=summarize_experimental_data(rows)
    normalized=out/'experimental_data_normalized.csv'
    _write_csv(normalized, rows, ['candidate_id','sequence','target','assay_type','value_type','value','unit','value_nM','potency_class','replicate_id','condition','source','raw_row'])
    cand_csv=out/'experimental_candidate_summary.csv'
    _write_csv(cand_csv, summary.get('candidate_summary', []), ['candidate_id','n','median_nM','min_nM','max_nM','potency_class'])
    summary_json=out/'experimental_import_summary.json'; _write_json(summary_json, summary)
    claim_guard=out/'experimental_claim_guard_table.csv'
    _write_csv(claim_guard, [
        {'claim':'assay value can be cited','status':'allowed_with_method_context','safe_expression':'cite assay type, condition, unit, and source'},
        {'claim':'mixed assay values are directly interchangeable','status':'blocked','safe_expression':'separate by assay type/condition before direct comparison'},
        {'claim':'single imported row proves universal binding','status':'blocked','safe_expression':'single assay row supports limited evidence only'},
    ])
    report=out/'experimental_import_report.md'
    top=summary.get('candidate_summary', [])[:10]
    lines='\n'.join([f"| {r['candidate_id']} | {r['median_nM']} | {r['potency_class']} | {r['n']} |" for r in top]) or '| - | - | - | - |'
    warn='\n'.join('- '+w for w in summary.get('warnings', [])) or '- none'
    _write_text(report, f"""# Pepforge Experimental Data Import Report\n\n## Summary\n\n- Records: {summary.get('record_count')}\n- Candidates: {summary.get('candidate_count')}\n- Assay types: {', '.join(summary.get('assay_types', [])) or 'none'}\n\n## Top imported assay records by median value\n\n| Candidate | Median nM | Class | n |\n|---|---:|---|---:|\n{lines}\n\n## Warnings\n\n{warn}\n\n## Claim boundary\n\n{summary.get('claim_boundary')}\n""")
    manifest=out/'experimental_import_manifest.json'
    _write_json(manifest, {'pepforge_version':EXPERIMENTAL_IMPORT_VERSION,'input_csv':str(input_csv),'files':{'normalized':str(normalized),'candidate_summary':str(cand_csv),'summary':str(summary_json),'claim_guard':str(claim_guard),'report':str(report)}})
    return {'experimental_data_normalized':str(normalized),'experimental_candidate_summary':str(cand_csv),'experimental_import_summary':str(summary_json),'experimental_claim_guard_table':str(claim_guard),'experimental_import_report':str(report),'experimental_import_manifest':str(manifest)}

__all__=['EXPERIMENTAL_IMPORT_VERSION','normalize_unit_to_nm','potency_class_from_nm','make_experimental_template','import_experimental_rows','summarize_experimental_data','export_experimental_import_package']
