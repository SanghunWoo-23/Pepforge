"""Real torsion-sampled MMFF94s ensemble; use SDF output with RUN_ENSEMBLE_DOCKING.py."""
import argparse,json
from peptiforg_core.v6_flexible_refinement import sample_flexible_conformers
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('input_sdf');p.add_argument('output_sdf');p.add_argument('--samples',type=int,default=24);p.add_argument('--seed',type=int,default=2026)
a=p.parse_args();print(json.dumps(sample_flexible_conformers(a.input_sdf,a.output_sdf,samples=a.samples,seed=a.seed),indent=2))
