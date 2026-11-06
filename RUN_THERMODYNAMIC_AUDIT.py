"""Post-process real alchemical data or independent MD observables; never simulate fake data."""
import argparse,json
from pathlib import Path
from peptiforg_core.v6_thermodynamics import analyze_alchemical_samples, analyze_replica_observables

p=argparse.ArgumentParser()
s=p.add_subparsers(dest='mode',required=True)
a=s.add_parser('alchemical-leg');a.add_argument('samples_npz');a.add_argument('output_json');a.add_argument('--temperature-k',type=float,required=True)
r=s.add_parser('replicas');r.add_argument('output_json');r.add_argument('observable_csv',nargs='+')
args=p.parse_args(); out=Path(args.output_json)
if out.exists() or out.is_symlink(): p.error('Output exists; refusing to overwrite')
if args.mode=='alchemical-leg': result=analyze_alchemical_samples(args.samples_npz,temperature_k=args.temperature_k)
else: result=analyze_replica_observables(args.observable_csv)
out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False)
print(result['status'])
