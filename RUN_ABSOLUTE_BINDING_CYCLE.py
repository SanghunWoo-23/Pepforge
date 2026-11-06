"""Combine two independently sampled alchemical legs with documented corrections."""
import argparse, json
from pathlib import Path
from peptiforg_core.v6_binding_cycle import assemble_binding_cycle
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('cycle_manifest_json'); p.add_argument('output_json')
a=p.parse_args(); dst=Path(a.output_json)
if dst.exists() or dst.is_symlink(): p.error('Output exists')
result=assemble_binding_cycle(a.cycle_manifest_json)
dst.parent.mkdir(parents=True,exist_ok=True)
with dst.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False)
print(result['status'])
