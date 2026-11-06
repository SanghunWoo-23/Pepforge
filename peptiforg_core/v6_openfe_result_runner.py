"""Run an authentic OpenFE ABFE Transformation and audit returned results.

This adapter never interprets an individual alchemical leg as binding free energy.
It does not certify molecular convergence from a scalar estimate alone.
"""
from __future__ import annotations
import json, hashlib, math, os, shutil, subprocess, tempfile
from pathlib import Path

class OpenFERunError(RuntimeError): pass

def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def _atomic_json(path, obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False,suffix='.json') as f:
        tmp=Path(f.name)
        json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)
    os.replace(tmp,path)

def inspect_openfe_result(result_file):
    """Read official quickrun output, not arbitrary leg-level values."""
    p=Path(result_file)
    data=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(data,dict): raise OpenFERunError('OpenFE result must be an object')
    # OpenFE quickrun tutorial specifies keys estimate, uncertainty and protocol_result.
    if any(key not in data for key in ('estimate','uncertainty','protocol_result')):
        raise OpenFERunError('Not a complete OpenFE ABFE result (estimate/uncertainty/protocol_result missing)')
    if not isinstance(data['protocol_result'],dict) or not data['protocol_result']:
        raise OpenFERunError('Missing OpenFE protocol result evidence')
    def quantity(v, label):
        if isinstance(v,bool): raise OpenFERunError(f'{label}: invalid boolean')
        if isinstance(v,(int,float)): raise OpenFERunError(f'{label}: unitless result is not accepted')
        if not isinstance(v,dict): raise OpenFERunError(f'{label}: unsupported quantity serialization')
        # OpenFE tokenized quantity representation is version-dependent; preserve raw form.
        if not v: raise OpenFERunError(f'{label}: empty serialized quantity')
        return v
    estimate=quantity(data['estimate'],'estimate')
    uncertainty=quantity(data['uncertainty'],'uncertainty')
    return {'status':'COMPUTED_NOT_INDEPENDENTLY_VALIDATED',
            'source':'OpenFE AbsoluteBindingProtocol full thermodynamic cycle',
            'estimate_raw':estimate,'uncertainty_raw':uncertainty,
            'raw_result_sha256':_sha(p),
            'warnings':['Unit normalization and protocol-specific result parsing require installed OpenFE.',
                        'Check per-leg overlap, independent repeats, restraints, trajectory convergence, chemical parameters, and experimental agreement.',
                        'Do not add an external Boresch term to the OpenFE final cycle result.']}

def run(transformation, work_dir, *, openfe_executable='openfe', timeout_seconds=None):
    transformation=Path(transformation).resolve()
    work_dir=Path(work_dir).resolve()
    if not transformation.is_file(): raise FileNotFoundError(transformation)
    if work_dir.exists(): raise FileExistsError(f'Use a new, nonexisting work directory: {work_dir}')
    if shutil.which(openfe_executable) is None:
        raise OpenFERunError('OpenFE executable unavailable. Install OpenFE in supported environment.')
    manifest=transformation.with_suffix('.manifest.json')
    if not manifest.is_file(): raise OpenFERunError('Input transformation provenance manifest missing')
    provenance=json.loads(manifest.read_text(encoding='utf-8'))
    if provenance.get('transformation_sha256') != _sha(transformation):
        raise OpenFERunError('Transformation hash differs from prepared manifest')
    work_dir.mkdir(parents=True)
    result=work_dir/'openfe_results.json'
    command=[openfe_executable,'quickrun',str(transformation),'-o',str(result),'-d',str(work_dir/'simulation')]
    audit={'status':'STARTED','transformation_sha256':_sha(transformation),'command':command}
    _atomic_json(work_dir/'pepforge_execution_audit.json',audit)
    try:
        proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout_seconds,check=False)
        (work_dir/'openfe_stdout.log').write_text(proc.stdout,encoding='utf-8')
        (work_dir/'openfe_stderr.log').write_text(proc.stderr,encoding='utf-8')
        audit.update(returncode=proc.returncode,stdout_sha256=_sha(work_dir/'openfe_stdout.log'),stderr_sha256=_sha(work_dir/'openfe_stderr.log'))
        if proc.returncode != 0: raise OpenFERunError(f'OpenFE exited {proc.returncode}; inspect openfe_stderr.log')
        if not result.is_file(): raise OpenFERunError('OpenFE returned success but output JSON is missing')
        computed=inspect_openfe_result(result)
        audit.update(computed)
        return audit
    except (Exception,BaseException) as exc:
        audit.update(status='FAILED',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _atomic_json(work_dir/'pepforge_execution_audit.json',audit)
