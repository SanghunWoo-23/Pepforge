"""Fail-closed optional OpenMM+GAFF receptor/modified peptide preparation."""
import argparse,json
from peptiforg_core.v6_physics_bridge import prepare_gaff_complex
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('receptor_pdb');p.add_argument('peptide_sdf');p.add_argument('output_dir')
p.add_argument('--gaff-version',default='gaff-2.2.20');p.add_argument('--platform',choices=['CPU','Reference'],default='CPU')
p.add_argument('--minimize-steps',type=int,default=250,help='vacuum minimization iteration cap; 0 disables')
a=p.parse_args()
print(json.dumps(prepare_gaff_complex(a.receptor_pdb,a.peptide_sdf,a.output_dir,gaff_version=a.gaff_version,platform=a.platform,minimize_steps=a.minimize_steps),indent=2))
