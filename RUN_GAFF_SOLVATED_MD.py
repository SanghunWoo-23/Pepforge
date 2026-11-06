"""Execute real explicit-solvent GAFF/OpenMM molecular dynamics; never simulate success."""
import argparse
import json
from peptiforg_core.v6_solvated_gaff_md import run_solvated_gaff_md

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('receptor_pdb');p.add_argument('peptide_sdf');p.add_argument('output_dir')
    p.add_argument('--platform',default='auto',choices=['auto','CPU','CUDA','OpenCL','Reference'])
    p.add_argument('--equilibration-steps',type=int,default=1000)
    p.add_argument('--production-steps',type=int,default=5000)
    p.add_argument('--report-interval',type=int,default=500)
    p.add_argument('--seed',type=int,default=2026)
    a=p.parse_args()
    result=run_solvated_gaff_md(a.receptor_pdb,a.peptide_sdf,a.output_dir,platform=a.platform,
                  equilibration_steps=a.equilibration_steps,production_steps=a.production_steps,
                  report_interval=a.report_interval,seed=a.seed)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
