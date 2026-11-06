"""Non-mutating runtime capability and optional OpenMM platform probe.

Only advertises observed imports/devices; never claims verified docking/MD.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def probe(*, check_openmm=True, check_torch=True):
    result = {'schema': 'pepforge.v6.runtime_capabilities.v1',
              'time_utc': datetime.now(timezone.utc).isoformat(),
              'os': platform.platform(), 'python': sys.version.split()[0],
              'cpu_logical_count': os.cpu_count(), 'engines': {},
              'scientific_validation': 'NOT_PERFORMED'}
    for engine in ('vina', 'smina', 'obabel', 'nvidia-smi'):
        result['engines'][engine] = {'executable': shutil.which(engine), 'detected': shutil.which(engine) is not None}
    result['engines']['haddock3'] = {'executable': shutil.which('haddock3'), 'detected': shutil.which('haddock3') is not None}
    mm = {'installed': importlib.util.find_spec('openmm') is not None, 'platforms': [], 'errors': []}
    if mm['installed'] and check_openmm:
        try:
            import openmm
            mm['version'] = str(openmm.version.version)
            mm['platforms'] = [openmm.Platform.getPlatform(i).getName() for i in range(openmm.Platform.getNumPlatforms())]
        except (ImportError, RuntimeError, OSError, AttributeError) as exc:
            mm['errors'].append(str(exc))
    result['engines']['openmm'] = mm
    torch = {'installed': importlib.util.find_spec('torch') is not None, 'cuda_available': False}
    if torch['installed'] and check_torch:
        try:
            import torch as t
            torch['version'] = str(t.__version__)
            torch['cuda_available'] = bool(t.cuda.is_available())
            if torch['cuda_available']:
                torch['gpu_names'] = [t.cuda.get_device_name(i) for i in range(t.cuda.device_count())]
        except (ImportError, RuntimeError, OSError) as exc:
            torch['error'] = str(exc)
    result['engines']['torch'] = torch
    result['ready_for_real_docking'] = False
    result['ready_for_validated_production_md'] = False
    result['notice'] = 'Installed engines/devices are not proof of accuracy, stable performance, or validated parameters.'
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--skip-openmm-import', action='store_true')
    p.add_argument('--skip-torch-import', action='store_true')
    args = p.parse_args(argv)
    data = probe(check_openmm=not args.skip_openmm_import, check_torch=not args.skip_torch_import)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Capability report: {args.output} (scientific validation NOT performed)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
