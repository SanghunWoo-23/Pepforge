"""Extract real structural MD observables from topology and trajectories.

Receptor-aligned peptide heavy-atom RMSD and interfacial heavy-atom contacts.
Explicit selections required; periodic unwrap/alignment must be validated upstream.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np

def extract(topology,trajectory,receptor_selection,peptide_selection,output_csv,contact_cutoff_angstrom=4.5):
    import MDAnalysis as mda
    from MDAnalysis.analysis import align
    if not 0<contact_cutoff_angstrom<25: raise ValueError('Invalid cutoff')
    output=Path(output_csv)
    if output.exists() or output.is_symlink():raise FileExistsError(output)
    u=mda.Universe(str(topology),str(trajectory))
    receptor=u.select_atoms(receptor_selection)
    peptide=u.select_atoms(peptide_selection)
    if len(receptor)<3 or len(peptide)<1:raise ValueError('Selections must include receptor alignment atoms and peptide atoms')
    if set(receptor.indices).intersection(peptide.indices):raise ValueError('Receptor and peptide selections overlap')
    u.trajectory[0]
    ref_rec=receptor.positions.copy().astype(float)
    ref_pep=peptide.positions.copy().astype(float)
    from scipy.spatial.distance import cdist
    output.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    for ts in u.trajectory:
        x=np.asarray(receptor.positions,float);y=np.asarray(peptide.positions,float)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError('Nonfinite trajectory coordinates')
        # Kabsch alignment to frame zero receptor coordinates: x @ rotation + shift
        xc=x.mean(axis=0);rc=ref_rec.mean(axis=0)
        q=x-xc;target=ref_rec-rc
        a,_,b=np.linalg.svd(q.T@target)
        d=np.linalg.det(a@b)
        rot=a@np.diag([1,1,np.sign(d)])@b
        yp=(y-xc)@rot+rc
        rmsd=np.sqrt(np.mean(np.sum((yp-ref_pep)**2,axis=1)))
        contacts=int(np.count_nonzero(cdist(x,y)<contact_cutoff_angstrom))
        records.append((int(ts.frame),float(rmsd),contacts))
    if len(records)<2:raise ValueError('Too few trajectory frames')
    with output.open('x',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['frame','peptide_receptor_aligned_rmsd_angstrom','interface_atom_pair_contacts']);w.writerows(records)
    return {'frames':len(records),'topology_sha256':hashlib.sha256(Path(topology).read_bytes()).hexdigest(),
            'trajectory_sha256':hashlib.sha256(Path(trajectory).read_bytes()).hexdigest(),
            'selection_receptor':receptor_selection,'selection_peptide':peptide_selection,
            'limitations':['PBC wrapping must be corrected before this analysis',
                           'Atom-pair contact counts depend on selection and cutoff',
                           'Observable stability alone does not establish binding free energy or equilibrium']}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('topology');p.add_argument('trajectory');p.add_argument('output_csv')
    p.add_argument('--receptor',required=True,help='MDAnalysis atom selection')
    p.add_argument('--peptide',required=True,help='MDAnalysis atom selection')
    p.add_argument('--cutoff-angstrom',type=float,default=4.5)
    a=p.parse_args()
    print(json.dumps(extract(a.topology,a.trajectory,a.receptor,a.peptide,a.output_csv,a.cutoff_angstrom),indent=2))
