from __future__ import annotations

"""Optional receptor-structure predictor adapters for Pepforge V5.

These adapters are deliberately separate from docking and MD.  They either call
an actually installed model/backend or report an unavailable state; they never
fabricate receptor coordinates.
"""

from pathlib import Path
from typing import Any
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

PREDICTOR_BACKENDS_VERSION = "5.0.0-rc2"
ESMFOLD_MODEL = "facebook/esmfold_v1"
CANONICAL_AA = set("ARNDCQEGHILKMFPSTWYV")


def _plain_protein_sequence(sequence: str) -> str:
    seq = re.sub(r"\s+", "", str(sequence or "").upper())
    if not seq:
        raise ValueError("Protein sequence is empty.")
    invalid = sorted(set(seq) - CANONICAL_AA)
    if invalid:
        raise ValueError(f"Protein predictor input must use canonical one-letter amino acids; unsupported: {invalid}")
    return seq


def detect_esmfold(model_name: str = ESMFOLD_MODEL) -> dict[str, Any]:
    torch_ok = importlib.util.find_spec("torch") is not None
    transformers_ok = importlib.util.find_spec("transformers") is not None
    return {
        "backend": "esmfold", "adapter_version": PREDICTOR_BACKENDS_VERSION,
        "model_name": model_name, "available": bool(torch_ok and transformers_ok),
        "status": "READY" if torch_ok and transformers_ok else "OPTIONAL_DEPENDENCY_MISSING",
        "torch_available": torch_ok, "transformers_available": transformers_ok,
        "claim_guard": "ESMFold output is a predicted receptor structure, not experimental validation or MD.",
    }


def run_esmfold_prediction(
    sequence: str,
    output_dir: str | Path,
    *,
    model_name: str = ESMFOLD_MODEL,
    device: str = "auto",
    local_files_only: bool = False,
    chunk_size: int | None = 128,
) -> dict[str, Any]:
    ready = detect_esmfold(model_name)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    seq = _plain_protein_sequence(sequence)
    preflight = {**ready, "sequence_length": len(seq), "device_request": device, "local_files_only": bool(local_files_only)}
    (out / "esmfold_preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not ready["available"]:
        payload = {**preflight, "status": "BACKEND_UNAVAILABLE", "pdb": None}
        (out / "esmfold_prediction_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    import torch
    from transformers import EsmForProteinFolding

    selected_device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else str(device)
    started = time.time()
    try:
        model = EsmForProteinFolding.from_pretrained(model_name, local_files_only=bool(local_files_only))
        model = model.to(selected_device)
        model.eval()
        if chunk_size and hasattr(getattr(model, "trunk", None), "set_chunk_size"):
            model.trunk.set_chunk_size(int(chunk_size))
        with torch.no_grad():
            if hasattr(model, "infer_pdb"):
                pdb_text = model.infer_pdb(seq)
            else:
                output = model.infer(seq)
                pdb_text = model.output_to_pdb(output)[0]
        if not isinstance(pdb_text, str) or "ATOM" not in pdb_text:
            raise RuntimeError("ESMFold did not return a readable PDB string.")
        pdb_path = out / "esmfold_receptor.pdb"
        pdb_path.write_text(pdb_text.rstrip() + "\n", encoding="utf-8")
        bfactors = []
        for line in pdb_text.splitlines():
            if line.startswith("ATOM"):
                try: bfactors.append(float(line[60:66].strip()))
                except Exception: pass
        payload = {
            **preflight, "status": "COMPLETED", "selected_device": selected_device,
            "pdb": str(pdb_path), "elapsed_seconds": round(time.time() - started, 3),
            "mean_plddt_from_bfactor": (sum(bfactors) / len(bfactors) if bfactors else None),
            "claim_guard": "Predicted receptor coordinates and pLDDT are model outputs; they are not experimental structure validation, affinity, or dynamics evidence.",
        }
    except Exception as exc:
        payload = {**preflight, "status": "FAILED", "pdb": None, "error": f"{type(exc).__name__}: {exc}", "elapsed_seconds": round(time.time() - started, 3)}
    (out / "esmfold_prediction_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def detect_alphafold3(
    run_script: str | Path | None = None,
    *,
    python_executable: str | None = None,
    model_dir: str | Path | None = None,
    db_dir: str | Path | None = None,
) -> dict[str, Any]:
    py = str(python_executable or sys.executable)
    candidate = Path(run_script).expanduser().resolve() if run_script else None
    script_ok = bool(candidate and candidate.exists() and candidate.is_file())
    model_ok = bool(model_dir and Path(model_dir).expanduser().exists())
    db_ok = bool(db_dir and Path(db_dir).expanduser().exists())
    return {
        "backend": "alphafold3", "adapter_version": PREDICTOR_BACKENDS_VERSION,
        "available": bool(script_ok and model_ok and db_ok),
        "status": "READY" if script_ok and model_ok and db_ok else "CONFIGURATION_REQUIRED",
        "python_executable": py, "run_script": str(candidate) if candidate else None,
        "run_script_exists": script_ok, "model_dir_exists": model_ok, "db_dir_exists": db_ok,
        "model_dir": str(Path(model_dir).expanduser().resolve()) if model_dir else None,
        "db_dir": str(Path(db_dir).expanduser().resolve()) if db_dir else None,
        "claim_guard": "AlphaFold 3 is an optional external structure predictor; model parameters remain subject to their own terms and Pepforge does not redistribute them.",
    }


def write_alphafold3_protein_input(
    sequence: str,
    output_json: str | Path,
    *,
    name: str = "Pepforge_receptor",
    chain_id: str = "A",
    model_seeds: tuple[int, ...] = (20260928,),
) -> str:
    seq = _plain_protein_sequence(sequence)
    seeds = [int(x) for x in model_seeds]
    if not seeds:
        raise ValueError("AlphaFold 3 input requires at least one model seed.")
    payload = {
        "name": str(name or "Pepforge_receptor"),
        "modelSeeds": seeds,
        "sequences": [{"protein": {"id": str(chain_id or "A"), "sequence": seq}}],
        "dialect": "alphafold3",
        "version": 4,
    }
    path = Path(output_json).expanduser().resolve(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _find_af3_structure(output_dir: Path) -> Path | None:
    # Prefer the top-level best-ranked model written by AF3, then a sample mmCIF.
    cif = sorted([p for p in output_dir.rglob("*.cif") if p.is_file() and p.stat().st_size > 0], key=lambda p: (len(p.parts), p.name))
    return cif[0] if cif else None


def convert_mmcif_to_pdb(mmcif_path: str | Path, pdb_path: str | Path) -> str:
    """Convert a protein mmCIF to PDB using installed Biopython or gemmi."""
    source = Path(mmcif_path).expanduser().resolve(); dest = Path(pdb_path).expanduser().resolve()
    if not source.exists(): raise FileNotFoundError(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from Bio.PDB import MMCIFParser, PDBIO
        structure = MMCIFParser(QUIET=True).get_structure("pepforge", str(source))
        io = PDBIO(); io.set_structure(structure); io.save(str(dest))
    except Exception as first:
        try:
            import gemmi
            st = gemmi.read_structure(str(source)); st.write_pdb(str(dest))
        except Exception as second:
            raise RuntimeError(f"mmCIF->PDB conversion failed: Biopython={first}; gemmi={second}") from second
    if not dest.exists() or dest.stat().st_size <= 0:
        raise RuntimeError("mmCIF conversion produced no PDB artifact.")
    return str(dest)


def run_alphafold3_prediction(
    sequence: str,
    output_dir: str | Path,
    *,
    run_script: str | Path,
    model_dir: str | Path,
    db_dir: str | Path,
    python_executable: str | None = None,
    name: str = "Pepforge_receptor",
    model_seeds: tuple[int, ...] = (20260928,),
    timeout_seconds: int | None = None,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    ready = detect_alphafold3(run_script, python_executable=python_executable, model_dir=model_dir, db_dir=db_dir)
    input_json = write_alphafold3_protein_input(sequence, out / "alphafold3_input.json", name=name, model_seeds=model_seeds)
    if not ready["available"]:
        payload = {**ready, "status": "BACKEND_UNAVAILABLE", "input_json": input_json, "structure_mmcif": None, "pdb": None}
        (out / "alphafold3_prediction_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    command = [
        ready["python_executable"], ready["run_script"],
        f"--json_path={input_json}", f"--output_dir={out / 'prediction'}",
        f"--model_dir={ready['model_dir']}", f"--db_dir={ready['db_dir']}",
    ] + list(extra_args or [])
    started = time.time()
    try:
        cp = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", timeout=timeout_seconds, check=False)
        (out / "alphafold3_stdout.log").write_text(cp.stdout or "", encoding="utf-8")
        (out / "alphafold3_stderr.log").write_text(cp.stderr or "", encoding="utf-8")
        if cp.returncode != 0:
            payload = {**ready, "status": "FAILED", "input_json": input_json, "returncode": cp.returncode, "command": command, "structure_mmcif": None, "pdb": None, "elapsed_seconds": round(time.time()-started,3)}
        else:
            structure = _find_af3_structure(out / "prediction")
            if structure is None:
                payload = {**ready, "status": "COMPLETED_NO_STRUCTURE_FOUND", "input_json": input_json, "returncode": 0, "command": command, "structure_mmcif": None, "pdb": None, "elapsed_seconds": round(time.time()-started,3)}
            else:
                pdb = convert_mmcif_to_pdb(structure, out / "alphafold3_receptor.pdb")
                payload = {**ready, "status": "COMPLETED", "input_json": input_json, "returncode": 0, "command": command, "structure_mmcif": str(structure), "pdb": pdb, "elapsed_seconds": round(time.time()-started,3), "claim_guard": "AlphaFold 3 coordinates are predictions, not experimental validation or MD."}
    except subprocess.TimeoutExpired as exc:
        payload = {**ready, "status": "TIMEOUT", "input_json": input_json, "command": command, "structure_mmcif": None, "pdb": None, "error": str(exc), "elapsed_seconds": round(time.time()-started,3)}
    (out / "alphafold3_prediction_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def predictor_status() -> dict[str, Any]:
    return {"version": PREDICTOR_BACKENDS_VERSION, "esmfold": detect_esmfold(), "alphafold3": detect_alphafold3()}


__all__ = [
    "PREDICTOR_BACKENDS_VERSION", "ESMFOLD_MODEL", "detect_esmfold", "run_esmfold_prediction",
    "detect_alphafold3", "write_alphafold3_protein_input", "run_alphafold3_prediction",
    "convert_mmcif_to_pdb", "predictor_status",
]
