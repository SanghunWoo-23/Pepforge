"""Optional, strictly fail-closed GAFF/OpenMM preparation for noncovalent complexes.

Peptide is treated as a SINGLE covalently complete molecule in SDF, not as
individual protein residues.  This module does not invent GAFF templates.
"""
from pathlib import Path
import hashlib
import json
import math


def prepare_gaff_complex(receptor_pdb, peptide_sdf, output_dir, *, gaff_version='gaff-2.2.20', platform='CPU', minimize_steps=250):
    if type(minimize_steps) is not int or not 0 <= minimize_steps <= 100000:
        raise ValueError('minimize_steps must be an integer between 0 and 100000')
    try:
        from openff.toolkit import Molecule
        from openmmforcefields.generators import GAFFTemplateGenerator
        import openmm as mm
        from openmm import app, unit
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError('GAFF/OpenMM backend unavailable: install openmm, openff-toolkit, openmmforcefields and AmberTools') from exc
    if platform not in ('CPU','Reference'):
        raise ValueError('Only validated CPU/Reference platform selection is supported here')
    rec, pep = Path(receptor_pdb), Path(peptide_sdf)
    if not rec.is_file() or not pep.is_file(): raise FileNotFoundError('Receptor PDB and peptide SDF required')
    supplier = Chem.SDMolSupplier(str(pep), removeHs=False)
    if len(supplier) != 1 or supplier[0] is None: raise ValueError('Exactly one chemically valid molecule is required')
    ligand = supplier[0]
    if ligand.GetNumConformers() != 1 or not ligand.GetConformer().Is3D():
        raise ValueError('A single explicit 3D conformer is required')
    off = Molecule.from_rdkit(ligand, allow_undefined_stereo=False, hydrogens_are_explicit=True)
    pdb=app.PDBFile(str(rec))
    # The covalent peptide is a single independent molecule, connected internally.
    ligand_top=off.to_topology().to_openmm()
    topology=app.Topology()
    atom_map={}
    for chain in pdb.topology.chains():
        nc=topology.addChain(chain.id)
        for res in chain.residues():
            nr=topology.addResidue(res.name,nc,id=res.id)
            for atom in res.atoms():
                atom_map[atom]=topology.addAtom(atom.name,atom.element,nr)
    for a,b in pdb.topology.bonds(): topology.addBond(atom_map[a],atom_map[b])
    # Ligand coordinates and topology must originate from the same RDKit molecule.
    chain=topology.addChain('L')
    ligand_atom_map={}
    for residue in ligand_top.residues():
        nr=topology.addResidue(residue.name,chain)
        for atom in residue.atoms():
            ligand_atom_map[atom]=topology.addAtom(atom.name,atom.element,nr)
    for a,b in ligand_top.bonds(): topology.addBond(ligand_atom_map[a],ligand_atom_map[b])
    conf=ligand.GetConformer()
    coords=[mm.Vec3(*[float(x) for x in conf.GetAtomPosition(i)])*unit.angstrom for i in range(ligand.GetNumAtoms())]
    positions=list(pdb.positions)+coords
    ff=app.ForceField('amber14-all.xml','amber14/tip3pfb.xml')
    generator=GAFFTemplateGenerator(molecules=off,forcefield=gaff_version)
    ff.registerTemplateGenerator(generator.generator)
    system=ff.createSystem(topology,nonbondedMethod=app.NoCutoff,constraints=app.HBonds)
    if system.getNumParticles()!=topology.getNumAtoms(): raise RuntimeError('Atom count mismatch')
    context=mm.Context(system,mm.VerletIntegrator(0.001*unit.picoseconds),mm.Platform.getPlatformByName(platform))
    context.setPositions(positions)
    state=context.getState(getEnergy=True)
    energy=state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    if not math.isfinite(energy): raise RuntimeError('Non-finite initial complex energy')
    # Vacuum relaxation is a preparatory sanity check, NOT solvated production MD.
    # A zero-step request preserves the original configuration for comparisons.
    minimized_positions = positions
    minimized_energy = energy
    if minimize_steps:
        mm.LocalEnergyMinimizer.minimize(context, maxIterations=minimize_steps)
        minimized_state = context.getState(getEnergy=True, getPositions=True)
        minimized_energy = minimized_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        if not math.isfinite(minimized_energy):
            raise RuntimeError('Non-finite minimized complex energy')
        minimized_positions = minimized_state.getPositions()
        if len(minimized_positions) != topology.getNumAtoms():
            raise RuntimeError('Minimized coordinate count mismatch')
    # Drop native resources before serializing outputs.
    del context
    out=Path(output_dir)
    if out.exists() and (not out.is_dir() or any(out.iterdir())): raise FileExistsError('Require empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    (out/'system.xml').write_text(mm.XmlSerializer.serialize(system),encoding='utf-8')
    with (out/'complex_initial.pdb').open('w') as f: app.PDBFile.writeFile(topology,positions,f,keepIds=True)
    with (out/'complex_minimized.pdb').open('w') as f: app.PDBFile.writeFile(topology,minimized_positions,f,keepIds=True)
    record={'status':'PARAMETERIZED_NOT_EQUILIBRATED','method':'GAFF + AMBER14, noncovalent ligand','gaff_version':gaff_version,'platform':platform,'initial_energy_kj_mol':energy,'minimized_energy_kj_mol':minimized_energy,'minimization_iterations_max':minimize_steps,'particle_count':system.getNumParticles(), 'receptor_sha256':hashlib.sha256(rec.read_bytes()).hexdigest(),'peptide_sha256':hashlib.sha256(pep.read_bytes()).hexdigest(),'limitations':['Vacuum/no-cutoff minimization only; no solvation/equilibration/production MD performed','Does not support covalent receptor-peptide coupling','Force field assignment is not independent validation']}
    record['artifacts_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'system.xml',out/'complex_initial.pdb',out/'complex_minimized.pdb')}
    (out/'parameterization.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record
