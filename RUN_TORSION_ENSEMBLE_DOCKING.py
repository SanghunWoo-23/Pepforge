"""CPU torsion-ensemble workflow, with actual native docking of each candidate.

This is conformationally flexible ensemble docking, not receptor-coupled
fully flexible physics-based docking or an affinity estimator.
"""
import argparse, hashlib, json
from pathlib import Path
from rdkit import Chem
from peptiforg_core.v6_flexible_refinement import sample_flexible_conformers
from peptiforg_core.v6_ensemble_docking import run_ensemble_docking

def run(receptor,peptide_sdf,output,*,samples=12,max_structures=5,poses=3,max_candidates=150,seed=2026):
    root=Path(output)
    if root.exists():raise FileExistsError('Output must not exist')
    if not Path(receptor).is_file() or not Path(peptide_sdf).is_file(): raise FileNotFoundError('Inputs missing')
    root.mkdir(parents=True)
    report={'status':'RUNNING','method':'MMFF94s torsion-sampled ensemble + independent native rigid pose docking','not_full_flexible_physics':True,'cases':[]}
    manifest=root/'torsion_docking_report.json'
    def save():
        tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(manifest)
    save()
    try:
        diverse=root/'torsion_conformers.sdf'
        ff=sample_flexible_conformers(peptide_sdf,diverse,samples=samples,seed=seed)
        report['torsion_search']=ff; save()
        molecules=[m for m in Chem.SDMolSupplier(str(diverse),removeHs=False) if m is not None]
        if not molecules:raise ValueError('No conformers')
        for i,mol in enumerate(molecules[:max_structures]):
            target=root/f'candidate_{i+1:03d}'; s=root/f'candidate_{i+1:03d}.sdf'
            w=Chem.SDWriter(str(s));w.write(mol);w.close()
            item={'candidate':i+1,'sdf_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'status':'RUNNING'}
            report['cases'].append(item);save()
            try:
                result=run_ensemble_docking(receptor,s,target,conformers=1,max_structures=1,seed=seed+i+1,poses=poses,max_candidates=max_candidates)
                item['status']=result['status']; item['output']=str(target)
            except Exception as e:item['status']='FAILED';item['error']=f'{type(e).__name__}: {e}'
            save()
        good=sum(i['status']=='COMPLETED' for i in report['cases'])
        report['successful_cases']=good
        report['status']='COMPLETED' if good==len(report['cases']) and good else 'PARTIAL_OR_FAILED'
    except Exception as e:
        report['status']='FAILED';report['error']=f'{type(e).__name__}: {e}';save();raise
    save();return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('receptor');p.add_argument('peptide_sdf');p.add_argument('output')
    p.add_argument('--samples',type=int,default=12);p.add_argument('--max-structures',type=int,default=5)
    p.add_argument('--poses',type=int,default=3);p.add_argument('--max-candidates',type=int,default=150)
    a=p.parse_args();r=run(a.receptor,a.peptide_sdf,a.output,samples=a.samples,max_structures=a.max_structures,poses=a.poses,max_candidates=a.max_candidates)
    print(json.dumps({'status':r['status'],'successful_cases':r.get('successful_cases',0)},indent=2))
    if r['status']!='COMPLETED':raise SystemExit(2)
