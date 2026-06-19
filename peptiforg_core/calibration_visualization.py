
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import csv, json, re, statistics

CALIBRATION_VISUALIZATION_VERSION = "3.4.0"

def _read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p=Path(path)
    if not p.exists(): return []
    with p.open('r', encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]]=None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None: fieldnames=list(rows[0].keys()) if rows else ['note']
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore'); w.writeheader(); [w.writerow(r) for r in rows]
    return str(path)

def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8'); return str(path)

def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8'); return str(path)

def _float_or_none(x: Any):
    try:
        if x is None: return None
        s=str(x).strip().replace(',','')
        if not s or s.lower() in {'nan','none','null','na','n/a'}: return None
        return float(s)
    except Exception: return None

def _safe_target_name(v: str) -> str:
    s=re.sub(r'[^A-Za-z0-9_.-]+','_',str(v or 'unknown_target')).strip('_')
    return s or 'unknown_target'

def group_calibration_by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups={}
    for r in rows:
        target=str(r.get('target') or r.get('Target') or 'unknown_target').strip() or 'unknown_target'
        groups.setdefault(target,[]).append(r)
    return groups

def _potency_order(cls: str) -> int:
    return {'very_strong_nM':5,'strong_nM':4,'moderate_uM_edge':3,'weak_uM':2,'very_weak_or_inactive':1,'unknown':0}.get(str(cls),0)

def summarize_target_calibration(target: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable=[]
    for r in rows:
        score=_float_or_none(r.get('calibration_score') or r.get('pepforge_score') or r.get('score'))
        aff=_float_or_none(r.get('affinity_nM') or r.get('affinity_value'))
        cls=str(r.get('potency_class') or 'unknown')
        if score is not None: usable.append({**r,'_score':score,'_affinity':aff,'_class':cls})
    scores=[r['_score'] for r in usable]
    classes=sorted({r['_class'] for r in usable}, key=_potency_order, reverse=True)
    counts={c:sum(1 for r in usable if r['_class']==c) for c in classes}
    conf='high' if len(usable)>=20 and len(classes)>=3 else ('medium' if len(usable)>=8 and len(classes)>=2 else 'low')
    warnings=[]
    if len(usable)<5: warnings.append('fewer_than_5_usable_records')
    if len(classes)<2: warnings.append('fewer_than_2_potency_classes')
    assays={str(r.get('assay_type') or '') for r in usable if r.get('assay_type')}
    if len(assays)>1: warnings.append('mixed_assay_types_review_before_comparing')
    return {'target':target,'total_records':len(rows),'usable_records':len(usable),'class_count':len(classes),'classes':classes,'class_counts':counts,'score_min':min(scores) if scores else None,'score_max':max(scores) if scores else None,'score_median':statistics.median(scores) if scores else None,'confidence':conf,'warnings':warnings,'claim_boundary':'Target model card supports target-specific calibration review only. It does not prove final Kd or true binding.'}

def _svg_escape(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def make_class_count_svg(summary: dict[str,Any], output_path: str|Path) -> str:
    counts=summary.get('class_counts') or {}; items=list(counts.items()) or [('no_data',0)]
    width=720; row_h=34; margin=180; height=70+row_h*len(items); max_count=max([int(v) for _,v in items]+[1])
    bars=[]
    for i,(cls,cnt) in enumerate(items):
        y=40+i*row_h; bw=int((width-margin-60)*(int(cnt)/max_count)) if max_count else 0
        bars += [f'<text x="10" y="{y+16}" font-size="13">{_svg_escape(cls)}</text>', f'<rect x="{margin}" y="{y}" width="{bw}" height="20" fill="#7aa6c2" />', f'<text x="{margin+bw+8}" y="{y+16}" font-size="12">{int(cnt)}</text>']
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><text x="10" y="24" font-size="17" font-weight="bold">Pepforge calibration class counts: {_svg_escape(summary.get('target','unknown'))}</text>{''.join(bars)}<text x="10" y="{height-12}" font-size="11">Screening calibration only; external validation required.</text></svg>'''
    return _write_text(Path(output_path), svg)

def target_model_card_markdown(summary: dict[str,Any], rows: list[dict[str,Any]], svg_name: str) -> str:
    warns='\n'.join(f'- {w}' for w in (summary.get('warnings') or [])) or '- none'
    counts='\n'.join(f'- {k}: {v}' for k,v in (summary.get('class_counts') or {}).items()) or '- no class data'
    ex=[]
    for r in rows[:12]: ex.append(f"| {r.get('sequence','')} | {r.get('affinity_nM','')} | {r.get('potency_class','')} | {r.get('calibration_score','')} | {r.get('source','')} |")
    table='\n'.join(ex) or '| - | - | - | - | - |'
    return f'''# Pepforge Target-specific Calibration Model Card\n\n## Target\n\n`{summary.get('target')}`\n\n## Dataset coverage\n\n- Total records: {summary.get('total_records')}\n- Usable records: {summary.get('usable_records')}\n- Potency classes: {summary.get('class_count')}\n- Calibration confidence: **{summary.get('confidence')}**\n\n## Potency class counts\n\n{counts}\n\n![Class count chart]({svg_name})\n\n## Score range\n\n- Score min: {summary.get('score_min')}\n- Score median: {summary.get('score_median')}\n- Score max: {summary.get('score_max')}\n\n## Warnings\n\n{warns}\n\n## Example records\n\n| Sequence | Affinity nM | Potency class | Pepforge score | Source |\n|---|---:|---|---:|---|\n{table}\n\n## Allowed interpretation\n\n- target-specific screening calibration\n- within-target candidate prioritization\n- predicted class wording only with external validation boundary\n\n## Blocked interpretation\n\n- final Kd proof\n- true nM binder proof\n- universal model across unrelated targets\n- assay-independent potency claim\n\n## Claim boundary\n\n{summary.get('claim_boundary')}\n'''

def export_calibration_visualization_package(calibration_normalized_csv: str|Path, output_dir: str|Path) -> dict[str,str]:
    rows=_read_csv_rows(calibration_normalized_csv)
    out=Path(output_dir)/'calibration_visualization_model_cards'; out.mkdir(parents=True, exist_ok=True)
    groups=group_calibration_by_target(rows)
    index=[]; cards=[]
    for target,trows in sorted(groups.items()):
        safe=_safe_target_name(target); tdir=out/safe; tdir.mkdir(parents=True, exist_ok=True)
        summary=summarize_target_calibration(target,trows)
        summary_json=tdir/'target_model_card_summary.json'; _write_json(summary_json, summary)
        rows_csv=tdir/'target_calibration_records.csv'; _write_csv(rows_csv, trows)
        svg=tdir/'target_class_count_chart.svg'; make_class_count_svg(summary, svg)
        card=tdir/'target_model_card.md'; _write_text(card, target_model_card_markdown(summary, trows, svg.name))
        cards.append(str(card)); index.append({'target':target,'total_records':summary['total_records'],'usable_records':summary['usable_records'],'class_count':summary['class_count'],'confidence':summary['confidence'],'warnings':';'.join(summary['warnings']) if summary['warnings'] else 'none','model_card':str(card),'chart':str(svg)})
    index_csv=out/'target_model_card_index.csv'; _write_csv(index_csv,index,['target','total_records','usable_records','class_count','confidence','warnings','model_card','chart'])
    index_md=out/'target_model_card_index.md'
    lines=['# Pepforge Calibration Target Model Card Index','']+[f"- **{r['target']}**: confidence `{r['confidence']}`, usable records `{r['usable_records']}`, card `{Path(r['model_card']).name}`" for r in index]
    if not index: lines.append('- no target model cards generated')
    lines += ['', 'Claim boundary: target model cards support calibration review and prioritization, not final Kd proof.']
    _write_text(index_md, '\n'.join(lines)+'\n')
    manifest=out/'calibration_visualization_manifest.json'; _write_json(manifest, {'pepforge_version':CALIBRATION_VISUALIZATION_VERSION,'input':str(calibration_normalized_csv),'target_count':len(index),'files':{'index_csv':str(index_csv),'index_md':str(index_md),'cards':cards},'claim_boundary':'Calibration visualization supports target-specific review only; external validation remains required.'})
    return {'target_model_card_index_csv':str(index_csv),'target_model_card_index_md':str(index_md),'calibration_visualization_manifest':str(manifest)}

__all__=['CALIBRATION_VISUALIZATION_VERSION','group_calibration_by_target','summarize_target_calibration','make_class_count_svg','export_calibration_visualization_package']
