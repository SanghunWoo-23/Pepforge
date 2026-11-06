"""Evidence-based runtime readiness diagnostics; never substitutes for validation."""
from __future__ import annotations
import argparse
import importlib.util
import json
import platform
import sys
from pathlib import Path


def _present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def collect_readiness() -> dict:
    deps = {k: _present(v) for k,v in {
        'rdkit':'rdkit', 'openmm':'openmm', 'openff_toolkit':'openff.toolkit',
        'openmmforcefields':'openmmforcefields', 'torch':'torch',
        'transformers':'transformers', 'BioPython':'Bio', 'pytest':'pytest'
    }.items()}
    devices = {'cpu': 'available', 'cuda': 'not_checked', 'openmm_platforms': []}
    if deps['torch']:
        try:
            import torch
            devices['cuda'] = 'available' if torch.cuda.is_available() else 'unavailable'
            if torch.cuda.is_available():
                devices['cuda_device'] = torch.cuda.get_device_name(0)
        except Exception as exc:
            devices['cuda'] = f'probe_failed:{type(exc).__name__}'
    if deps['openmm']:
        try:
            import openmm
            devices['openmm_platforms'] = [openmm.Platform.getPlatform(i).getName() for i in range(openmm.Platform.getNumPlatforms())]
        except Exception as exc:
            devices['openmm_platform_error'] = type(exc).__name__
    capabilities = {
        'modified_peptide_mmff': {
            'ready': deps['rdkit'],
            'scope': 'intramolecular MMFF only; chemical coverage requires per-molecule checks'},
        'native_ensemble_docking': {
            'ready': deps['rdkit'],
            'scope': 'geometry search, not flexible physics-based affinity prediction'},
        'openmm_canonical_md': {
            'ready': deps['openmm'],
            'scope': 'installation gate only; no energy conservation/convergence verification performed'},
        'gaff_openff_modified_complex_md': {
            'ready': False,
            'scope': 'NOT VERIFIED: requires chemical graph/bonded-interface, charge, template and dynamics verification'},
        'arbitrary_sequence_structure_prediction_without_model': {
            'ready': False,
            'scope': 'not scientifically supported: requires template/experimental structure or pretrained predictor'},
        'pymol_arbitrary_length_sequence_tokens': {
            'ready': False,
            'scope': 'built-in PyMOL sequence panel supports restricted representations; token mapping is separate'},
        'windows_exe_installed_test': {
            'ready': False,
            'scope': 'requires actual Windows EXE build, launch, UI and persistence measurements'},
    }
    return {
        'schema':'pepforge.v6.runtime_readiness.v1',
        'environment':{'python':sys.version.split()[0], 'os':platform.system(), 'machine':platform.machine()},
        'dependencies':deps, 'devices':devices, 'capabilities':capabilities,
        'claim_guard':'Package presence is not validation of a scientific result or hardware performance.'
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description='Honest runtime and scientific capability checks for Pepforge')
    parser.add_argument('--output', type=Path, help='Write the JSON diagnostic report')
    args=parser.parse_args(argv)
    report=collect_readiness()
    payload=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(payload,encoding='utf-8')
    else:
        print(payload,end='')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
