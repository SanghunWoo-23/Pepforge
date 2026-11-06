"""Run actual multi-conformer native docking using an explicit modified-peptide SDF."""
import argparse
import json
from peptiforg_core.v6_ensemble_docking import run_ensemble_docking

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('receptor',help='PDB or mmCIF receptor structure')
    p.add_argument('peptide_sdf',help='Explicit 3D/2D SDF with correct molecular graph and stereo')
    p.add_argument('output',help='New/empty output directory')
    p.add_argument('--conformers',type=int,default=12)
    p.add_argument('--max-structures',type=int,default=8)
    p.add_argument('--seed',type=int,default=2026)
    p.add_argument('--poses',type=int,default=3)
    p.add_argument('--max-candidates',type=int,default=250)
    p.add_argument('--mode',choices=['blind','manual','hotspot'],default='blind')
    p.add_argument('--binding-residue',action='append',default=[])
    args=p.parse_args()
    result=run_ensemble_docking(args.receptor,args.peptide_sdf,args.output,conformers=args.conformers,
        max_structures=args.max_structures,seed=args.seed,poses=args.poses,max_candidates=args.max_candidates,
        mode=args.mode,binding_residues=args.binding_residue)
    print(json.dumps({'status':result['status'],'runs':len(result['runs'])},ensure_ascii=False))
    if result['status']!='COMPLETED':
        raise SystemExit(2)

if __name__=='__main__':main()
