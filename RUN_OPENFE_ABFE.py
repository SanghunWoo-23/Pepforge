"""Prepare an official OpenFE ABFE simulation for actual execution (no synthetic data)."""
import argparse, json
from peptiforg_core.v6_openfe_abfe_bridge import prepare

def main():
    p=argparse.ArgumentParser(description='Prepare OpenFE ABFE; generated JSON must be run with openfe quickrun')
    p.add_argument('receptor_pdb');p.add_argument('modified_peptide_sdf');p.add_argument('output_json')
    p.add_argument('--platform',choices=('CPU','CUDA','OpenCL'),default='CPU')
    p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args()
    print(json.dumps(prepare(a.receptor_pdb,a.modified_peptide_sdf,a.output_json,platform=a.platform,repeats=a.repeats),indent=2))
if __name__=='__main__': main()
