"""CPU-capable, chemistry-preserving receptor-conditioned pose relaxation."""
import argparse
import json
from peptiforg_core.v6_interface_physics import refine_interface_pose


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('receptor_pdb')
    p.add_argument('ligand_sdf', help='Single 3D molecule, positioned in receptor coordinates')
    p.add_argument('output_sdf')
    p.add_argument('--iterations', type=int, default=1000)
    args = p.parse_args()
    print(json.dumps(refine_interface_pose(args.receptor_pdb, args.ligand_sdf,
                                           args.output_sdf, max_iterations=args.iterations), indent=2))


if __name__ == '__main__':
    main()
