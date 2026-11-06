"""Standalone CPU-friendly modified-peptide conformer refinement."""
import argparse
from peptiforg_core.v6_ff_ensemble import refine_sdf_ensemble


def main():
    parser=argparse.ArgumentParser(description='Refine explicit molecular graph SDF conformers using RDKit MMFF94s; NOT binding energy')
    parser.add_argument('input_sdf')
    parser.add_argument('output_directory')
    parser.add_argument('--conformers',type=int,default=12)
    parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--max-iterations',type=int,default=500)
    parser.add_argument('--diversity-rmsd', type=float, default=1.0)
    parser.add_argument('--energy-window', type=float, default=15.0)
    args=parser.parse_args()
    report=refine_sdf_ensemble(args.input_sdf,args.output_directory,conformers=args.conformers,seed=args.seed,max_iterations=args.max_iterations, diversity_rmsd=args.diversity_rmsd, energy_window_kcal_mol=args.energy_window)
    for entry in report['results']:
        print('Molecule',entry['molecule_index'],entry['status'],'generated=',entry['generated_count'])
    print('Audit:',args.output_directory+'/mmff94s_ensemble_report.json')

if __name__=='__main__':main()
