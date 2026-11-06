"""Compute an explicitly defined 1 M Boresch restraint release term from JSON."""
import argparse, json
from pathlib import Path
from peptiforg_core.v6_boresch_correction import BoreschRestraint, numerical_boresch_release

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('parameters_json',help='JSON with all BoreschRestraint fields and temperature_k')
    ap.add_argument('output_json')
    a=ap.parse_args()
    data=json.loads(Path(a.parameters_json).read_text(encoding='utf-8'))
    T=data.pop('temperature_k',298.15)
    data['phi_rad']=tuple(data['phi_rad']); data['k_phi_kcal_mol_rad2']=tuple(data['k_phi_kcal_mol_rad2'])
    out=numerical_boresch_release(BoreschRestraint(**data),temperature_k=T)
    dest=Path(a.output_json)
    if dest.exists(): raise FileExistsError('Output already exists')
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
