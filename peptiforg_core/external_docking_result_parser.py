from __future__ import annotations

"""External Docking Result Parser Expansion for Pepforge v3.3.0.

Imports and normalizes common external docking outputs into a Pepforge-compatible
screening evidence table. Supported lightweight targets include Vina/Smina logs,
Gnina CNNscore logs, PRODIGY-like text, generic CSV/TSV score tables, and folder
batch scans. Imported scores do not prove final Kd or true binding.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import csv, json, re

EXTERNAL_DOCKING_PARSER_VERSION = "3.3.0"

def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["source_file","tool","candidate_id","rank","score","score_unit","score_type","note"]
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore'); w.writeheader(); [w.writerow(r) for r in rows]
    return str(path)

def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8'); return str(path)

def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8'); return str(path)

def _candidate_id_from_path(path: str | Path) -> str:
    p=Path(path); stem=p.stem
    stem=re.sub(r'(_|-)?(vina|smina|gnina|prodigy|dock|score|log|out)$', '', stem, flags=re.I)
    return stem or p.stem

def _float_or_none(value: Any):
    if value is None: return None
    s=str(value).strip().replace(',', '')
    s=re.sub(r'^[<>=~ ]+', '', s)
    try: return float(s)
    except Exception: return None

def parse_vina_smina_text(text: str, source_file: str = '') -> list[dict[str, Any]]:
    rows=[]; candidate=_candidate_id_from_path(source_file or 'vina_result')
    for line in str(text or '').splitlines():
        m=re.match(r'^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)?\s+(-?\d+(?:\.\d+)?)?', line)
        if m:
            rows.append({'source_file':source_file,'tool':'vina_or_smina','candidate_id':candidate,'rank':int(m.group(1)),'score':float(m.group(2)),'score_unit':'kcal/mol','score_type':'binding_energy_lower_better','rmsd_lb':m.group(3) or '','rmsd_ub':m.group(4) or '','note':'parsed from Vina/Smina-like score table'})
    if not rows:
        for i,m in enumerate(re.finditer(r'(?:affinity|score|binding energy)\s*[:=]\s*(-?\d+(?:\.\d+)?)', text or '', flags=re.I), start=1):
            rows.append({'source_file':source_file,'tool':'vina_or_smina','candidate_id':candidate,'rank':i,'score':float(m.group(1)),'score_unit':'kcal/mol','score_type':'binding_energy_lower_better','rmsd_lb':'','rmsd_ub':'','note':'parsed from affinity/score line'})
    return rows

def parse_gnina_text(text: str, source_file: str = '') -> list[dict[str, Any]]:
    candidate=_candidate_id_from_path(source_file or 'gnina_result')
    scores=re.findall(r'(?:CNNscore|CNN_score|cnnscore)\s*[:=]\s*(-?\d+(?:\.\d+)?)', text or '', flags=re.I)
    affs=re.findall(r'(?:CNNaffinity|CNN_affinity|cnnaffinity)\s*[:=]\s*(-?\d+(?:\.\d+)?)', text or '', flags=re.I)
    rows=[]
    for i,s in enumerate(scores, start=1):
        rows.append({'source_file':source_file,'tool':'gnina','candidate_id':candidate,'rank':i,'score':float(s),'score_unit':'unitless','score_type':'cnn_score_higher_better','rmsd_lb':'','rmsd_ub':'','cnn_affinity':affs[i-1] if i-1 < len(affs) else '', 'note':'parsed GNINA CNNscore/CNNaffinity'})
    return rows

def parse_prodigy_text(text: str, source_file: str = '') -> list[dict[str, Any]]:
    candidate=_candidate_id_from_path(source_file or 'prodigy_result'); dg=None; kd=''
    m=re.search(r'(?:predicted\s+binding\s+affinity|binding\s+affinity|delta\s*g|ΔG).*?(-?\d+(?:\.\d+)?)\s*kcal', text or '', flags=re.I)
    if m: dg=float(m.group(1))
    k=re.search(r'(?:predicted\s+Kd|Kd).*?([<>=~ ]*-?\d+(?:\.\d+)?)\s*([munp]?M)', text or '', flags=re.I)
    if k: kd=f'{k.group(1).strip()} {k.group(2)}'
    if dg is None: return []
    return [{'source_file':source_file,'tool':'prodigy','candidate_id':candidate,'rank':1,'score':dg,'score_unit':'kcal/mol','score_type':'binding_affinity_delta_g_lower_better','rmsd_lb':'','rmsd_ub':'','predicted_kd':kd,'note':'parsed PRODIGY-like text'}]

def parse_generic_score_csv(path: str | Path) -> list[dict[str, Any]]:
    p=Path(path); rows=[]
    if not p.exists(): return rows
    sample=p.read_text(encoding='utf-8', errors='ignore')[:4096]
    delim='\t' if sample.count('\t') > sample.count(',') else ','
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f, delimiter=delim)
        for i,r in enumerate(reader, start=1):
            lower={str(k).lower().strip():v for k,v in r.items() if k is not None}
            score=None; col=''
            for key in ['score','affinity','binding_energy','delta_g','docking_score','cnnscore','cnn_score']:
                if key in lower:
                    score=_float_or_none(lower.get(key)); col=key
                    if score is not None: break
            if score is None: continue
            candidate=lower.get('candidate_id') or lower.get('ligand') or lower.get('peptide') or lower.get('sequence') or _candidate_id_from_path(p)
            tool=lower.get('tool') or ('gnina' if 'cnn' in col else 'generic_csv')
            rows.append({'source_file':str(p),'tool':tool,'candidate_id':str(candidate),'rank':lower.get('rank') or i,'score':score,'score_unit':lower.get('unit') or ('unitless' if 'cnn' in col else 'kcal/mol'),'score_type':'cnn_score_higher_better' if 'cnn' in col else 'binding_energy_lower_better','rmsd_lb':lower.get('rmsd_lb') or '','rmsd_ub':lower.get('rmsd_ub') or '', 'note':f'parsed generic CSV column {col}'})
    return rows

def parse_external_docking_file(path: str | Path) -> list[dict[str, Any]]:
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    if p.suffix.lower() in {'.csv','.tsv'}:
        rows=parse_generic_score_csv(p)
        if rows: return rows
    text=p.read_text(encoding='utf-8', errors='ignore')
    rows=[]
    for parser in (parse_gnina_text, parse_vina_smina_text, parse_prodigy_text):
        try: rows.extend(parser(text, str(p)))
        except Exception: pass
    return rows

def scan_external_docking_folder(folder: str | Path) -> list[dict[str, Any]]:
    base=Path(folder)
    if not base.exists(): raise FileNotFoundError(f'Folder not found: {base}')
    rows=[]
    for p in base.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.txt','.log','.out','.csv','.tsv'}:
            rows.extend(parse_external_docking_file(p))
    return rows

def normalize_external_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    norm=[]
    for r in rows:
        row=dict(r); score=_float_or_none(row.get('score')); st=str(row.get('score_type','')).lower()
        if score is None:
            row['normalized_rank_group']='unscored'; row['direction']='unknown'
        elif 'higher_better' in st:
            row['normalized_rank_group']=f"{row.get('tool','unknown')}:higher_better"; row['direction']='higher_better'
        else:
            row['normalized_rank_group']=f"{row.get('tool','unknown')}:lower_better"; row['direction']='lower_better'
        norm.append(row)
    groups={}
    for r in norm: groups.setdefault(str(r.get('normalized_rank_group','unknown')), []).append(r)
    for vals in groups.values():
        reverse=vals and vals[0].get('direction')=='higher_better'
        vals.sort(key=lambda x: _float_or_none(x.get('score')) if _float_or_none(x.get('score')) is not None else 1e9, reverse=reverse)
        for i,r in enumerate(vals, start=1): r['normalized_group_rank']=i
    return norm

def summarize_external_docking(rows: list[dict[str, Any]]) -> dict[str, Any]:
    norm=normalize_external_scores(rows); tools=sorted({str(r.get('tool','unknown')) for r in norm})
    best=[]
    for group in sorted({str(r.get('normalized_rank_group','unknown')) for r in norm}):
        gr=[r for r in norm if str(r.get('normalized_rank_group','unknown'))==group]
        if gr: best.append(gr[0])
    return {'pepforge_version':EXTERNAL_DOCKING_PARSER_VERSION,'record_count':len(norm),'tool_count':len(tools),'tools':tools,'best_by_score_group':best,'claim_boundary':'External docking parser normalizes imported scores for traceability. It does not prove final Kd or true binding.'}

def export_external_docking_import_package(input_path: str | Path, output_dir: str | Path) -> dict[str, str]:
    src=Path(input_path); out=Path(output_dir)/'external_docking_result_import'; out.mkdir(parents=True, exist_ok=True)
    rows=scan_external_docking_folder(src) if src.is_dir() else parse_external_docking_file(src)
    norm=normalize_external_scores(rows); summary=summarize_external_docking(rows)
    fields=['source_file','tool','candidate_id','rank','score','score_unit','score_type','direction','normalized_rank_group','normalized_group_rank','rmsd_lb','rmsd_ub','cnn_affinity','predicted_kd','note']
    normalized_csv=out/'external_docking_scores_normalized.csv'; _write_csv(normalized_csv, norm, fields)
    summary_json=out/'external_docking_import_summary.json'; _write_json(summary_json, summary)
    best_csv=out/'external_docking_best_by_group.csv'; _write_csv(best_csv, summary.get('best_by_score_group', []), fields)
    claim_guard=out/'external_docking_claim_guard_table.csv'; _write_csv(claim_guard, [
        {'claim':'external docking score proves final Kd','status':'blocked','safe_expression':'external docking score supports screening-level prioritization'},
        {'claim':'Vina/Smina/Gnina scores are directly interchangeable','status':'blocked','safe_expression':'scores are ranked within tool/score-type groups'},
        {'claim':'top imported docking score can be validated computational evidence','status':'allowed_with_qualification','safe_expression':'external docking evidence, method and limitations stated'},
    ])
    report=out/'external_docking_import_report.md'; _write_text(report, f"""# Pepforge External Docking Import Report\n\n**Pepforge version:** {EXTERNAL_DOCKING_PARSER_VERSION}\n\n- Imported records: {summary.get('record_count')}\n- Tools detected: {', '.join(summary.get('tools', [])) or 'none'}\n\nScores are normalized by tool/score-type group. Lower-better binding-energy values and higher-better CNN scores are not merged into one false universal score.\n\n## Claim boundary\n\n{summary.get('claim_boundary')}\n""")
    manifest=out/'external_docking_import_manifest.json'; _write_json(manifest, {'pepforge_version':EXTERNAL_DOCKING_PARSER_VERSION,'input_path':str(input_path),'files':{'normalized_scores':str(normalized_csv),'summary':str(summary_json),'best_by_group':str(best_csv),'claim_guard':str(claim_guard),'report':str(report)}})
    return {'external_docking_scores_normalized':str(normalized_csv),'external_docking_import_summary':str(summary_json),'external_docking_best_by_group':str(best_csv),'external_docking_claim_guard_table':str(claim_guard),'external_docking_import_report':str(report),'external_docking_import_manifest':str(manifest)}

__all__ = ['EXTERNAL_DOCKING_PARSER_VERSION','parse_vina_smina_text','parse_gnina_text','parse_prodigy_text','parse_external_docking_file','scan_external_docking_folder','normalize_external_scores','export_external_docking_import_package']
