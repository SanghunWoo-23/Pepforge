"""Explicit-water GAFF/AMBER14 MD for a noncovalent receptor + modified-peptide SDF.

Requires independently installed OpenMM, OpenFF Toolkit, openmmforcefields,
AmberTools, and RDKit. No simulated results or fallback parameters are used.
"""
from pathlib import Path
import hashlib
import json
import math
import os


def run_solvated_gaff_md(receptor_pdb, peptide_sdf, output_dir, *,
                         gaff_version='gaff-2.2.20', platform='auto',
                         padding_nm=1.0, ionic_strength_molar=0.15,
                         temperature_k=300.0, equilibration_steps=1000,
                         production_steps=5000, report_interval=500,
                         seed=2026):
    for name, n in [('padding_nm',padding_nm),('ionic_strength_molar',ionic_strength_molar),('temperature_k',temperature_k)]:
        if isinstance(n, bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n <= 0:
            raise ValueError(f'{name} must be finite and positive')
    for name, n in [('equilibration_steps',equilibration_steps),('production_steps',production_steps),('report_interval',report_interval),('seed',seed)]:
        if type(n) is not int or n <= 0 or n > 100000000:
            raise ValueError(f'{name} must be a positive bounded integer')
    if report_interval > production_steps:
        raise ValueError('report_interval must be <= production_steps')
    if padding_nm > 10 or ionic_strength_molar > 2 or not 200 <= temperature_k <= 450:
        raise ValueError('Solvation protocol outside guarded bounds')
    out=Path(output_dir)
    if out.is_symlink() or (out.exists() and (not out.is_dir() or any(out.iterdir()))):
        raise FileExistsError('MD output directory must be new or empty, not a symlink')
    out.parent.mkdir(parents=True,exist_ok=True)
    rec,pep=Path(receptor_pdb),Path(peptide_sdf)
    if not rec.is_file() or not pep.is_file():
        raise FileNotFoundError('Receptor PDB and peptide SDF must exist')
    try:
        from rdkit import Chem
        from openff.toolkit import Molecule
        from openmmforcefields.generators import GAFFTemplateGenerator
        import openmm as mm
        from openmm import app,unit
    except ImportError as exc:
        raise RuntimeError('Real solvated MD requires openmm, openff-toolkit, openmmforcefields, AmberTools and rdkit') from exc
    from .v6_physics_bridge import prepare_gaff_complex
    # Reuse no prepared positions without provenance; the preparation is run into
    # a separate temporary sibling directory and never interpreted as MD.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='pepforge_gaff_',dir=str(out.parent.resolve())) as tmp:
        prepare_gaff_complex(rec,pep,Path(tmp)/'prepared',gaff_version=gaff_version,platform='CPU',minimize_steps=0)
        pdb=app.PDBFile(str(Path(tmp)/'prepared'/'complex_initial.pdb'))
        sup=Chem.SDMolSupplier(str(pep),removeHs=False)
        if len(sup)!=1 or sup[0] is None:
            raise ValueError('Peptide SDF must have exactly one valid molecule')
        off=Molecule.from_rdkit(sup[0],allow_undefined_stereo=False,hydrogens_are_explicit=True)
        ff=app.ForceField('amber14-all.xml','amber14/tip3pfb.xml')
        gen=GAFFTemplateGenerator(molecules=off,forcefield=gaff_version)
        ff.registerTemplateGenerator(gen.generator)
        modeller=app.Modeller(pdb.topology,pdb.positions)
        modeller.addSolvent(ff,model='tip3p',padding=float(padding_nm)*unit.nanometer,
                           ionicStrength=float(ionic_strength_molar)*unit.molar,neutralize=True)
        system=ff.createSystem(modeller.topology,nonbondedMethod=app.PME,
                               nonbondedCutoff=1.0*unit.nanometer,constraints=app.HBonds)
        system.addForce(mm.MonteCarloBarostat(1.0*unit.bar,float(temperature_k)*unit.kelvin,25))
        available=[mm.Platform.getPlatform(i).getName() for i in range(mm.Platform.getNumPlatforms())]
        if platform=='auto':
            chosen=next((p for p in ('CUDA','OpenCL','CPU','Reference') if p in available),'Reference')
        elif platform in available:
            chosen=platform
        else:
            raise RuntimeError(f'OpenMM platform {platform} unavailable; detected {available}')
        integrator=mm.LangevinMiddleIntegrator(float(temperature_k)*unit.kelvin,1.0/unit.picosecond,0.002*unit.picoseconds)
        integrator.setRandomNumberSeed(seed)
        sim=app.Simulation(modeller.topology,system,integrator,mm.Platform.getPlatformByName(chosen))
        sim.context.setPositions(modeller.positions)
        sim.minimizeEnergy(maxIterations=500)
        sim.context.setVelocitiesToTemperature(float(temperature_k)*unit.kelvin,seed)
        sim.step(equilibration_steps)
        out.mkdir(parents=True,exist_ok=True)
        with (out/'equilibrated.pdb').open('w') as f:
            app.PDBFile.writeFile(modeller.topology,sim.context.getState(getPositions=True).getPositions(),f,keepIds=True)
        with (out/'system.xml').open('w') as f: f.write(mm.XmlSerializer.serialize(system))
        sim.reporters.append(app.DCDReporter(str(out/'production.dcd'),report_interval))
        sim.reporters.append(app.StateDataReporter(str(out/'production.csv'),report_interval,
                      step=True,potentialEnergy=True,temperature=True,volume=True,separator=','))
        sim.step(production_steps)
        state=sim.context.getState(getPositions=True,getEnergy=True)
        energy=float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
        if not math.isfinite(energy): raise RuntimeError('Production MD yielded nonfinite energy')
        with (out/'final.pdb').open('w') as f: app.PDBFile.writeFile(modeller.topology,state.getPositions(),f,keepIds=True)
        sim.saveCheckpoint(str(out/'final.chk'))
        required=('equilibrated.pdb','system.xml','production.dcd','production.csv','final.pdb','final.chk')
        if any(not (out/n).is_file() or (out/n).stat().st_size==0 for n in required):
            raise RuntimeError('Missing or empty real MD output')
        from .v6_md_quality import write_md_quality_report
        quality=write_md_quality_report(out/'production.csv',out/'md_quality.json',
                        target_temperature_k=float(temperature_k))
        required=required+('md_quality.json',)
        record={'quality_diagnostics':quality,'status':'PRODUCTION_COMPLETED_NOT_VALIDATED','method':'GAFF/AMBER14 TIP3P explicit solvent PME',
                'platform_used':chosen,'available_platforms':available,'equilibration_steps':equilibration_steps,
                'production_steps':production_steps,'timestep_ps':0.002,'temperature_k':temperature_k,
                'ionic_strength_molar':ionic_strength_molar,'padding_nm':padding_nm,
                'seed':seed,'potential_energy_kj_mol_final':energy,
                'receptor_sha256':hashlib.sha256(rec.read_bytes()).hexdigest(),
                'peptide_sha256':hashlib.sha256(pep.read_bytes()).hexdigest(),
                'limitations':['Trajectory completion does not demonstrate convergence',
                               'GAFF assignment is not proof of parameter validity for this chemistry',
                               'No independent experimental validation performed'],
                'artifacts_sha256':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in required}}
        (out/'md_manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        return record
