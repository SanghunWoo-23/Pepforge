from __future__ import annotations

"""Optional real OpenMM production-MD backend for Pepforge V5.

OpenMM is not a core Pepforge dependency. When installed this module builds a
standard solvated canonical protein/peptide system, minimizes, equilibrates and
runs independent production replicates. Unsupported chemistry is hard-blocked.
Preparation artifacts and checkpoints are persisted so interrupted canonical
runs can be resumed without silently rebuilding a different solvated system.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import importlib.util
import json
import math
import time

OPENMM_BACKEND_VERSION = "5.0.0-rc2"
STANDARD_PROTEIN_RESNAMES = {
    "ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","HID","HIE","HIP",
    "ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL",
    "ACE","NME","NHE","NH2",
}
SOLVENT_ION_RESNAMES = {"HOH","WAT","TIP3","NA","CL","K","MG","CA"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_openmm() -> dict[str, Any]:
    if importlib.util.find_spec("openmm") is None:
        return {
            "backend": "openmm", "backend_version": OPENMM_BACKEND_VERSION,
            "available": False, "status": "BACKEND_UNAVAILABLE", "engine_version": None,
            "reason": "Python package 'openmm' is not installed.",
        }
    try:
        import openmm
        version = getattr(getattr(openmm, "version", None), "version", None) or getattr(openmm, "__version__", "unknown")
        return {
            "backend": "openmm", "backend_version": OPENMM_BACKEND_VERSION,
            "available": True, "status": "READY", "engine_version": str(version), "reason": "",
        }
    except Exception as exc:
        return {
            "backend": "openmm", "backend_version": OPENMM_BACKEND_VERSION,
            "available": False, "status": "IMPORT_FAILED", "engine_version": None, "reason": str(exc),
        }


def residue_parameterization_gate(pdb_path: str | Path) -> dict[str, Any]:
    path = Path(pdb_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    residues: set[str] = set()
    het_residues: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("ATOM  "):
            residues.add(line[17:20].strip().upper())
        elif line.startswith("HETATM"):
            het_residues.add(line[17:20].strip().upper())
    unknown_atom = sorted(x for x in residues if x and x not in STANDARD_PROTEIN_RESNAMES)
    unknown_het = sorted(x for x in het_residues if x and x not in STANDARD_PROTEIN_RESNAMES | SOLVENT_ION_RESNAMES)
    unsupported = sorted(set(unknown_atom + unknown_het))
    return {
        "status": "READY_CANONICAL_STANDARD_CHEMISTRY" if not unsupported else "PARAMETERIZATION_REQUIRED",
        "supported": not unsupported,
        "standard_residues": sorted(residues & STANDARD_PROTEIN_RESNAMES),
        "unsupported_residue_names": unsupported,
        "claim_guard": "Unknown/non-natural residues require explicit validated topology/parameters; Pepforge does not fabricate them.",
    }


@dataclass(frozen=True)
class OpenMMProtocol:
    temperature_k: float = 300.0
    pressure_atm: float = 1.0
    ionic_strength_molar: float = 0.15
    solvent_padding_nm: float = 1.0
    timestep_fs: float = 2.0
    friction_per_ps: float = 1.0
    equilibration_ps: float = 100.0
    production_ns: float = 1.0
    report_frames: int = 500
    replicates: int = 3
    base_seed: int = 20260928
    forcefield_protein: str = "amber14-all.xml"
    forcefield_water: str = "amber14/tip3pfb.xml"
    resume_existing: bool = True


def validate_protocol(protocol: OpenMMProtocol) -> None:
    positive = {
        "temperature_k": protocol.temperature_k, "pressure_atm": protocol.pressure_atm,
        "solvent_padding_nm": protocol.solvent_padding_nm, "timestep_fs": protocol.timestep_fs,
        "friction_per_ps": protocol.friction_per_ps, "production_ns": protocol.production_ns,
    }
    for name, value in positive.items():
        if float(value) <= 0:
            raise ValueError(f"{name} must be > 0; got {value}")
    if float(protocol.ionic_strength_molar) < 0:
        raise ValueError("ionic_strength_molar must be >= 0")
    if float(protocol.equilibration_ps) < 0:
        raise ValueError("equilibration_ps must be >= 0")
    if int(protocol.report_frames) < 1 or int(protocol.replicates) < 1:
        raise ValueError("report_frames and replicates must be >= 1")


def _steps_for_ps(duration_ps: float, timestep_fs: float) -> int:
    return max(1, int(round(float(duration_ps) * 1000.0 / float(timestep_fs))))


def _protocol_fingerprint(protocol: OpenMMProtocol) -> dict[str, Any]:
    data = asdict(protocol).copy()
    data.pop("resume_existing", None)
    return data


def _preparation_matches(path: Path, input_sha: str, protocol: OpenMMProtocol) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("input_sha256") == input_sha and data.get("protocol_fingerprint") == _protocol_fingerprint(protocol)


def run_openmm_replicates(
    complex_pdb: str | Path,
    output_dir: str | Path,
    *,
    protocol: OpenMMProtocol | None = None,
) -> dict[str, Any]:
    protocol = protocol or OpenMMProtocol()
    validate_protocol(protocol)
    source = Path(complex_pdb).expanduser().resolve()
    if not source.exists() or source.stat().st_size <= 0:
        raise FileNotFoundError(source)
    gate = residue_parameterization_gate(source)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    readiness = detect_openmm()
    input_sha = _sha256(source)
    preflight = {
        "version": OPENMM_BACKEND_VERSION,
        "input_pdb": str(source), "input_sha256": input_sha,
        "readiness": readiness, "parameterization_gate": gate, "protocol": asdict(protocol),
    }
    (out / "openmm_preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not gate["supported"]:
        payload = {**preflight, "status": "PARAMETERIZATION_REQUIRED", "replicate_results": []}
        (out / "openmm_run_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    if not readiness["available"]:
        payload = {**preflight, "status": "BACKEND_UNAVAILABLE", "replicate_results": []}
        (out / "openmm_run_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    from openmm import LangevinMiddleIntegrator, MonteCarloBarostat, XmlSerializer, unit
    from openmm.app import (
        PDBFile, ForceField, Modeller, Simulation, PME, HBonds,
        DCDReporter, StateDataReporter, CheckpointReporter,
    )

    prep_manifest = out / "openmm_preparation_manifest.json"
    solvated = out / "solvated_system.pdb"
    system_xml = out / "system.xml"
    reuse_preparation = bool(protocol.resume_existing and solvated.exists() and system_xml.exists() and _preparation_matches(prep_manifest, input_sha, protocol))

    if reuse_preparation:
        pdb = PDBFile(str(solvated))
        topology = pdb.topology
        positions = pdb.positions
        system = XmlSerializer.deserialize(system_xml.read_text(encoding="utf-8"))
        preparation_status = "REUSED_VALIDATED_PREPARATION"
    else:
        pdb = PDBFile(str(source))
        forcefield = ForceField(protocol.forcefield_protein, protocol.forcefield_water)
        modeller = Modeller(pdb.topology, pdb.positions)
        modeller.addHydrogens(forcefield)
        modeller.addSolvent(
            forcefield,
            padding=float(protocol.solvent_padding_nm) * unit.nanometer,
            ionicStrength=float(protocol.ionic_strength_molar) * unit.molar,
            neutralize=True,
        )
        system = forcefield.createSystem(
            modeller.topology,
            nonbondedMethod=PME,
            nonbondedCutoff=1.0 * unit.nanometer,
            constraints=HBonds,
        )
        system.addForce(MonteCarloBarostat(float(protocol.pressure_atm) * unit.atmosphere, float(protocol.temperature_k) * unit.kelvin, 25))
        with solvated.open("w", encoding="utf-8") as fh:
            PDBFile.writeFile(modeller.topology, modeller.positions, fh, keepIds=True)
        system_xml.write_text(XmlSerializer.serialize(system), encoding="utf-8")
        topology, positions = modeller.topology, modeller.positions
        prep_manifest.write_text(json.dumps({
            "version": OPENMM_BACKEND_VERSION, "input_sha256": input_sha,
            "protocol_fingerprint": _protocol_fingerprint(protocol),
            "solvated_system_pdb": str(solvated), "system_xml": str(system_xml),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        preparation_status = "CREATED_NEW_PREPARATION"

    eq_steps = _steps_for_ps(protocol.equilibration_ps, protocol.timestep_fs) if protocol.equilibration_ps > 0 else 0
    prod_steps = _steps_for_ps(protocol.production_ns * 1000.0, protocol.timestep_fs)
    target_total_step = eq_steps + prod_steps
    report_interval = max(1, int(math.ceil(prod_steps / max(1, int(protocol.report_frames)))))
    results: list[dict[str, Any]] = []

    for rep in range(1, max(1, int(protocol.replicates)) + 1):
        rep_dir = out / f"replicate_{rep:02d}"; rep_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = rep_dir / "replicate_manifest.json"
        if protocol.resume_existing and manifest_path.exists():
            try:
                old = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                old = {}
            if old.get("status") == "COMPLETED" and Path(str(old.get("trajectory", ""))).exists() and Path(str(old.get("final_pdb", ""))).exists():
                reused = dict(old); reused["resume_status"] = "REUSED_COMPLETED_REPLICATE"
                results.append(reused)
                continue

        seed = int(protocol.base_seed) + rep
        integrator = LangevinMiddleIntegrator(
            float(protocol.temperature_k) * unit.kelvin,
            float(protocol.friction_per_ps) / unit.picosecond,
            float(protocol.timestep_fs) * unit.femtoseconds,
        )
        integrator.setRandomNumberSeed(seed)
        simulation = Simulation(topology, system, integrator)
        started = time.time()
        checkpoint = rep_dir / "checkpoint.chk"
        trajectory = rep_dir / "trajectory.dcd"
        prod_log = rep_dir / "production.log"
        eq_log = rep_dir / "equilibration.log"
        min_pdb = rep_dir / "minimized.pdb"
        final_pdb = rep_dir / "final.pdb"
        state_xml = rep_dir / "state.xml"
        resumed_from_checkpoint = False
        try:
            # Resume only against the exact persisted solvated system/system.xml.
            if protocol.resume_existing and checkpoint.exists() and trajectory.exists():
                simulation.loadCheckpoint(str(checkpoint))
                resumed_from_checkpoint = True
            else:
                simulation.context.setPositions(positions)
                simulation.minimizeEnergy()
                minimized_state = simulation.context.getState(getPositions=True, getEnergy=True)
                with min_pdb.open("w", encoding="utf-8") as fh:
                    PDBFile.writeFile(topology, minimized_state.getPositions(), fh, keepIds=True)
                simulation.context.setVelocitiesToTemperature(float(protocol.temperature_k) * unit.kelvin, seed)
                if eq_steps:
                    simulation.reporters.append(StateDataReporter(str(eq_log), max(1, eq_steps // 20), step=True, potentialEnergy=True, temperature=True, density=True, progress=True, remainingTime=True, totalSteps=eq_steps))
                    simulation.step(eq_steps)
                    simulation.reporters.clear()

            remaining_steps = max(0, int(target_total_step - simulation.currentStep))
            if remaining_steps:
                simulation.reporters.append(DCDReporter(str(trajectory), report_interval, append=bool(resumed_from_checkpoint)))
                simulation.reporters.append(CheckpointReporter(str(checkpoint), report_interval))
                log_handle = prod_log.open("a" if resumed_from_checkpoint else "w", encoding="utf-8")
                try:
                    simulation.reporters.append(StateDataReporter(log_handle, report_interval, step=True, time=True, potentialEnergy=True, kineticEnergy=True, totalEnergy=True, temperature=True, volume=True, density=True, speed=True, progress=False))
                    simulation.step(remaining_steps)
                finally:
                    log_handle.close()
            final_state = simulation.context.getState(getPositions=True, getVelocities=True, getEnergy=True)
            with final_pdb.open("w", encoding="utf-8") as fh:
                PDBFile.writeFile(topology, final_state.getPositions(), fh, keepIds=True)
            simulation.saveState(str(state_xml))
            result = {
                "replicate": rep, "seed": seed, "status": "COMPLETED",
                "resume_status": "RESUMED_FROM_CHECKPOINT" if resumed_from_checkpoint else "FRESH_RUN",
                "trajectory": str(trajectory), "topology_pdb": str(solvated),
                "minimized_pdb": str(min_pdb) if min_pdb.exists() else None, "final_pdb": str(final_pdb),
                "checkpoint": str(checkpoint), "state_xml": str(state_xml),
                "equilibration_log": str(eq_log) if eq_log.exists() else None, "production_log": str(prod_log),
                "equilibration_steps": eq_steps, "production_steps": prod_steps,
                "target_total_step": target_total_step, "final_step": int(simulation.currentStep),
                "production_ns": float(protocol.production_ns),
                "elapsed_seconds": round(time.time() - started, 3),
            }
        except Exception as exc:
            result = {
                "replicate": rep, "seed": seed, "status": "FAILED",
                "resume_status": "RESUME_FAILED" if resumed_from_checkpoint else "FRESH_RUN_FAILED",
                "checkpoint": str(checkpoint) if checkpoint.exists() else None,
                "trajectory": str(trajectory) if trajectory.exists() else None,
                "error": f"{type(exc).__name__}: {exc}", "elapsed_seconds": round(time.time() - started, 3),
            }
        results.append(result)
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    completed = [x for x in results if x.get("status") == "COMPLETED"]
    payload = {
        **preflight,
        "preparation_status": preparation_status,
        "status": "COMPLETED" if len(completed) == len(results) else ("PARTIAL_FAILURE" if completed else "FAILED"),
        "solvated_system_pdb": str(solvated), "system_xml": str(system_xml),
        "replicate_results": results,
        "claim_guard": "Independent finite MD trajectories are computational samples; duration alone does not prove equilibrium, convergence, affinity, or biological function.",
    }
    (out / "openmm_run_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "OPENMM_BACKEND_VERSION", "OpenMMProtocol", "detect_openmm", "validate_protocol",
    "residue_parameterization_gate", "run_openmm_replicates",
]
