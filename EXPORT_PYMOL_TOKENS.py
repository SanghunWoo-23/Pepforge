import argparse,json
from peptiforg_core.v6_pymol_tokens import export_pymol_token_view
p=argparse.ArgumentParser();p.add_argument('peptide_pdb');p.add_argument('token_csv',help='CSV with resi,token columns');p.add_argument('output_prefix');a=p.parse_args()
print(json.dumps(export_pymol_token_view(a.peptide_pdb,a.token_csv,a.output_prefix),indent=2))
