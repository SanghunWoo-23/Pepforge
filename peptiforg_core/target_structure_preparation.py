from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv, json, re
TARGET_PREP_VERSION="2.7.0"
WATER={"HOH","WAT","H2O","DOD"}
IONS={"NA","K","CL","CA","MG","MN","ZN","FE","CU","CO","NI","CD","HG","SR","BA","BR","F","LI","CS","RB"}
BUFFER={"SO4","PO4","ACT","ACE","FMT","GOL","EDO","PEG","DMS","DMSO","TRS","MES","HEP","BME","MPD","IPA","EOH"}

def _csv(path,rows,fields=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or (list(rows[0].keys()) if rows else ["note"])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    return str(path)
def _txt(path,s): path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(s,encoding='utf-8'); return str(path)
def _json(path,obj): path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8'); return str(path)

def classify_hetatm(resn:str)->str:
    r=str(resn or '').upper()
    if r in WATER: return 'water'
    if r in IONS: return 'ion'
    if r in BUFFER: return 'buffer_or_crystallization_agent'
    return 'ligand_or_cofactor'

def parse_pdb_records(path):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f'Target structure file not found: {p}')
    rows=[]
    for line in p.read_text(encoding='utf-8',errors='ignore').splitlines():
        rec=line[:6].strip()
        if rec not in {'ATOM','HETATM'}: continue
        rows.append({'record':rec,'atom':line[12:16].strip(),'altloc':line[16:17].strip(),'resn':line[17:20].strip().upper(),'chain':line[21:22].strip() or '_','resi':line[22:26].strip(),'line':line})
    return rows

def summarize_target_structure(path):
    rows=parse_pdb_records(path); het=[r for r in rows if r['record']=='HETATM']; prot=[r for r in rows if r['record']=='ATOM']
    return {'path':str(path),'atom_count':len(rows),'chain_count':len({r['chain'] for r in rows}),'chains':','.join(sorted({r['chain'] for r in rows})),'protein_residue_count':len({(r['chain'],r['resi'],r['resn']) for r in prot}),'hetatm_count':len(het),'water_count':sum(classify_hetatm(r['resn'])=='water' for r in het),'ion_count':sum(classify_hetatm(r['resn'])=='ion' for r in het),'ligand_or_cofactor_count':len({(r['chain'],r['resi'],r['resn']) for r in het if classify_hetatm(r['resn'])=='ligand_or_cofactor'}),'altloc_atom_count':sum(bool(r['altloc']) for r in rows)}

def chain_summary_rows(path):
    rows=parse_pdb_records(path); out=[]
    for ch in sorted({r['chain'] for r in rows}):
        cr=[r for r in rows if r['chain']==ch]; prot=[r for r in cr if r['record']=='ATOM']; het=[r for r in cr if r['record']=='HETATM']
        out.append({'chain':ch,'atom_count':len(cr),'protein_atom_count':len(prot),'protein_residue_count':len({(r['resi'],r['resn']) for r in prot}),'hetatm_count':len(het),'water_count':sum(classify_hetatm(r['resn'])=='water' for r in het),'ion_count':sum(classify_hetatm(r['resn'])=='ion' for r in het),'ligand_or_cofactor_count':len({(r['resi'],r['resn']) for r in het if classify_hetatm(r['resn'])=='ligand_or_cofactor'}),'suggested_role':'target_candidate' if len(prot)>=20 else 'review_or_nonprotein'})
    return out

def hetero_summary_rows(path):
    d={}
    for r in parse_pdb_records(path):
        if r['record']!='HETATM': continue
        key=(r['chain'],r['resi'],r['resn'],classify_hetatm(r['resn'])); d[key]=d.get(key,0)+1
    return [{'chain':a,'resi':b,'resn':c,'class':d0,'atom_count':n} for (a,b,c,d0),n in sorted(d.items())]

def target_quality_warnings(summary,chains=None,hetero=None):
    w=[]
    if summary.get('chain_count',0)>1: w.append({'level':'review','issue':'multiple_chains','recommendation':'Select receptor/target chain(s) before screening.'})
    if summary.get('water_count',0)>0: w.append({'level':'info','issue':'waters_present','recommendation':'Remove waters unless structural waters are intentional.'})
    if summary.get('ion_count',0)>0: w.append({'level':'info','issue':'ions_present','recommendation':'Review ions before screening.'})
    if summary.get('ligand_or_cofactor_count',0)>0: w.append({'level':'review','issue':'ligands_or_cofactors_present','recommendation':'Decide whether cofactors/ligands should be retained.'})
    if not w: w.append({'level':'ok','issue':'basic_structure_checks_passed','recommendation':'Proceed with standard scientific review.'})
    return w

def write_cleaned_pdb(input_path,output_path,selected_chains=None,keep_waters=False,keep_ions=True,keep_ligands=True,keep_altloc='A'):
    selected={str(x).strip() for x in (selected_chains or []) if str(x).strip()}; out=[]
    for line in Path(input_path).read_text(encoding='utf-8',errors='ignore').splitlines():
        rec=line[:6].strip()
        if rec not in {'ATOM','HETATM'}: continue
        ch=line[21:22].strip() or '_'
        if selected and ch not in selected: continue
        alt=line[16:17].strip()
        if alt and alt not in {'',keep_altloc}: continue
        if rec=='HETATM':
            cls=classify_hetatm(line[17:20].strip())
            if cls=='water' and not keep_waters: continue
            if cls=='ion' and not keep_ions: continue
            if cls in {'ligand_or_cofactor','buffer_or_crystallization_agent'} and not keep_ligands: continue
        out.append(line)
    out.append('END')
    p=Path(output_path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text('\n'.join(out)+'\n',encoding='utf-8'); return str(p)

def export_target_preparation_package(input_path,output_dir,selected_chains=None,keep_waters=False,keep_ions=True,keep_ligands=True,keep_altloc='A'):
    prep=Path(output_dir)/'target_structure_preparation'; prep.mkdir(parents=True,exist_ok=True)
    summary=summarize_target_structure(input_path); chains=chain_summary_rows(input_path); hetero=hetero_summary_rows(input_path); warnings=target_quality_warnings(summary,chains,hetero)
    paths={}
    paths['target_structure_summary']=_csv(prep/'target_structure_summary.csv',[{'metric':k,'value':v} for k,v in summary.items()],['metric','value'])
    paths['target_chain_summary']=_csv(prep/'target_chain_summary.csv',chains)
    paths['target_heteroatom_summary']=_csv(prep/'target_heteroatom_summary.csv',hetero)
    paths['target_quality_warnings']=_csv(prep/'target_quality_warnings.csv',warnings)
    paths['target_cleaned_pdb']=write_cleaned_pdb(input_path,prep/'target_cleaned.pdb',selected_chains,keep_waters,keep_ions,keep_ligands,keep_altloc)
    paths['target_preparation_manifest']=_json(prep/'target_preparation_manifest.json',{'pepforge_version':TARGET_PREP_VERSION,'input_path':str(input_path),'selected_chains':list(selected_chains or []),'files':paths,'claim_boundary':'Target preparation improves traceability but does not replace external all-atom preparation.'})
    paths['target_preparation_readme']=_txt(prep/'README_TARGET_PREPARATION.txt','Pepforge Target Structure Preparation Bridge\nReview chains, waters, ions, ligands, missing residues, alternate locations, and assembly choice before interpretation.\n')
    return paths
__all__=['TARGET_PREP_VERSION','summarize_target_structure','chain_summary_rows','hetero_summary_rows','target_quality_warnings','write_cleaned_pdb','export_target_preparation_package','classify_hetatm']
