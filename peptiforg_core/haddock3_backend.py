from __future__ import annotations

"""Real HADDOCK3 protein-peptide backend for Pepforge V5.

The adapter never fabricates docking results.  It can prepare a reproducible
HADDOCK3 workflow on any machine, detect an installed ``haddock3`` executable,
run it through a real subprocess, capture stdout/stderr, and harvest only PDB
poses that are referenced by an actual HADDOCK score table.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

HADDOCK3_BACKEND_VERSION = "5.0.0-rc2"

PRESETS: dict[str, dict[str, int]] = {
    "fast": {"sampling": 200, "select": 50, "ncores": 2},
    "standard": {"sampling": 1000, "select": 200, "ncores": 4},
    "deep": {"sampling": 3000, "select": 400, "ncores": 8},
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_capture(command: list[str], *, cwd: Path | None = None, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )


def detect_haddock3(executable: str = "haddock3") -> dict[str, Any]:
    resolved = shutil.which(executable)
    if not resolved:
        return {
            "backend": "haddock3",
            "backend_version": HADDOCK3_BACKEND_VERSION,
            "available": False,
            "status": "BACKEND_UNAVAILABLE",
            "executable": None,
            "engine_version": None,
            "reason": "haddock3 executable was not found on PATH.",
        }
    version = "unknown"
    probes = ([resolved, "--version"], [resolved, "-h"])
    for cmd in probes:
        try:
            cp = _run_capture(list(cmd), timeout=15)
            text = (cp.stdout or "") + "\n" + (cp.stderr or "")
            m = re.search(r"(?:haddock3|version)\s*[:= ]\s*([0-9][0-9A-Za-z_.+-]*)", text, flags=re.I)
            if m:
                version = m.group(1)
                break
            if cp.returncode == 0 and text.strip():
                first = next((x.strip() for x in text.splitlines() if x.strip()), "")
                if first:
                    version = first[:160]
                    break
        except Exception:
            continue
    return {
        "backend": "haddock3",
        "backend_version": HADDOCK3_BACKEND_VERSION,
        "available": True,
        "status": "READY",
        "executable": resolved,
        "engine_version": version,
        "reason": "",
    }


def _pdb_residues(path: Path) -> list[tuple[str, int, str]]:
    seen: set[tuple[str, int, str]] = set()
    rows: list[tuple[str, int, str]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        chain = (line[21:22].strip() or "A")
        try:
            resid = int(line[22:26].strip())
        except Exception:
            continue
        resn = line[17:20].strip().upper()
        key = (chain, resid, resn)
        if key not in seen:
            seen.add(key)
            rows.append(key)
    return rows


def _rewrite_single_chain_pdb(src: Path, dst: Path, chain: str) -> Path:
    chain = str(chain or "B")[:1]
    out: list[str] = []
    for raw in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith(("ATOM  ", "HETATM", "TER   ")):
            line = raw.ljust(80)
            line = line[:21] + chain + line[22:]
            out.append(line.rstrip())
        elif raw.startswith(("MODEL ", "ENDMDL", "REMARK", "TITLE", "SEQRES")):
            out.append(raw)
    if not out or not any(x.startswith(("ATOM  ", "HETATM")) for x in out):
        raise ValueError(f"No coordinate atoms found in peptide PDB: {src}")
    out.append("END")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dst


def _receptor_chain_residue(token: str, default_chain: str) -> tuple[str, int]:
    text = str(token or "").strip()
    if not text:
        raise ValueError("Empty binding-site residue token.")
    for sep in (":", "/", "-"):
        if sep in text:
            left, right = text.split(sep, 1)
            if left.strip() and re.fullmatch(r"-?\d+", right.strip()):
                return left.strip()[:1], int(right.strip())
    if re.fullmatch(r"-?\d+", text):
        return default_chain, int(text)
    m = re.fullmatch(r"([A-Za-z])\s*(\d+)", text)
    if m:
        return m.group(1), int(m.group(2))
    raise ValueError(f"Unsupported binding-site residue notation: {token!r}. Use 123 or A:123.")


def write_haddock_air(
    receptor_pdb: str | Path,
    peptide_pdb: str | Path,
    active_receptor_residues: Iterable[str],
    output_path: str | Path,
    *,
    peptide_chain: str = "B",
) -> str:
    receptor = Path(receptor_pdb)
    peptide = Path(peptide_pdb)
    receptor_res = _pdb_residues(receptor)
    if not receptor_res:
        raise ValueError("Receptor PDB has no residues.")
    default_chain = receptor_res[0][0]
    active = [_receptor_chain_residue(x, default_chain) for x in active_receptor_residues]
    pep_res = [(chain, resid) for chain, resid, _ in _pdb_residues(peptide)]
    pep_res = [(peptide_chain, resid) for _chain, resid in pep_res]
    if not pep_res:
        raise ValueError("Peptide PDB has no residues.")
    lines = ["! Pepforge V5 HADDOCK3 AIR restraints", "! receptor active residues -> all peptide residues", "!"]
    for chain, resid in active:
        lines.append(f"assign ( resid {resid} and segid {chain})")
        lines.append("(")
        for i, (_pchain, presi) in enumerate(pep_res):
            suffix = " or" if i < len(pep_res) - 1 else ""
            lines.append(f"( resid {presi} and segid {peptide_chain}){suffix}")
        lines.append(") 2.0 2.0 0.0")
        lines.append("!")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


@dataclass(frozen=True)
class HaddockPreparedJob:
    job_dir: str
    receptor_pdb: str
    peptide_pdb: str
    workflow_cfg: str
    restraint_tbl: str | None
    requested_pose_limit: int
    preset: str
    sampling: int
    select: int
    ncores: int
    peptide_chain: str
    peptide_residue_start: int
    peptide_residue_end: int


def prepare_haddock3_job(
    receptor_pdb: str | Path,
    peptide_pdb: str | Path,
    output_dir: str | Path,
    *,
    pose_limit: int = 5,
    binding_site_mode: str = "blind",
    binding_site_residues: Iterable[str] = (),
    preset: str = "standard",
    ncores: int | None = None,
) -> dict[str, Any]:
    receptor = Path(receptor_pdb).expanduser().resolve()
    peptide = Path(peptide_pdb).expanduser().resolve()
    if not receptor.exists() or not peptide.exists():
        raise FileNotFoundError("Receptor or peptide PDB does not exist.")
    settings = dict(PRESETS.get(str(preset).lower(), PRESETS["standard"]))
    if ncores is not None:
        settings["ncores"] = max(1, int(ncores))
    job_dir = Path(output_dir).expanduser().resolve()
    data_dir = job_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    receptor_copy = data_dir / "receptor.pdb"
    if receptor.suffix.lower() in {".cif", ".mmcif"}:
        # HADDOCK3 topology preparation expects a coordinate PDB here.  Keep
        # mmCIF as a supported Pepforge input but convert it explicitly rather
        # than copying mmCIF text into a .pdb filename.
        from peptiforg_core.structure_predictor_backends import convert_mmcif_to_pdb
        convert_mmcif_to_pdb(receptor, receptor_copy)
    else:
        shutil.copy2(receptor, receptor_copy)
    peptide_copy = _rewrite_single_chain_pdb(peptide, data_dir / "peptide.pdb", "B")
    pep_res = _pdb_residues(peptide_copy)
    if not pep_res:
        raise ValueError("Prepared peptide has no residues.")
    pep_start = min(x[1] for x in pep_res)
    pep_end = max(x[1] for x in pep_res)

    site_mode = str(binding_site_mode or "blind").lower()
    restraint: str | None = None
    if site_mode in {"manual", "hotspot"}:
        residues = [str(x).strip() for x in binding_site_residues if str(x).strip()]
        if not residues:
            raise ValueError(f"{site_mode} docking requires binding-site residues.")
        restraint = write_haddock_air(receptor_copy, peptide_copy, residues, data_dir / "ambig.tbl")
    elif site_mode != "blind":
        raise ValueError("binding_site_mode must be blind, hotspot, or manual")

    run_dir = job_dir / "haddock3_run"
    config = job_dir / "haddock3_workflow.cfg"
    ambig_line = 'ambig_fname = "data/ambig.tbl"\n' if restraint else ""
    # Protein-peptide workflow follows HADDOCK3's documented ordering while
    # retaining the PSB conformer as the explicit peptide starting structure.
    cfg = f'''# Pepforge V5 protein-peptide HADDOCK3 workflow\nrun_dir = "{run_dir.as_posix()}"\nmode = "local"\nncores = {settings['ncores']}\ndebug = true\nmolecules = [\n  "{receptor_copy.as_posix()}",\n  "{peptide_copy.as_posix()}"\n]\n\n[topoaa]\nautohis = true\n\n[rigidbody]\ntolerance = 5\nsampling = {settings['sampling']}\n{ambig_line}\n[seletop]\nselect = {settings['select']}\n\n[flexref]\ntolerance = 5\n{ambig_line}fle_sta_1 = {pep_start}\nfle_end_1 = {pep_end}\nfle_seg_1 = "B"\nssdihed = "alphabeta"\n\n[emref]\ntolerance = 5\n{ambig_line}fle_sta_1 = {pep_start}\nfle_end_1 = {pep_end}\nfle_seg_1 = "B"\nssdihed = "alphabeta"\n\n[clustfcc]\n\n[seletopclusts]\ntop_models = {max(1, int(pose_limit))}\n\n[caprieval]\nallatoms = true\n'''
    config.write_text(cfg, encoding="utf-8")
    prepared = HaddockPreparedJob(
        job_dir=str(job_dir), receptor_pdb=str(receptor_copy), peptide_pdb=str(peptide_copy),
        workflow_cfg=str(config), restraint_tbl=restraint,
        requested_pose_limit=max(1, int(pose_limit)), preset=str(preset).lower(),
        sampling=settings["sampling"], select=settings["select"], ncores=settings["ncores"],
        peptide_chain="B", peptide_residue_start=pep_start, peptide_residue_end=pep_end,
    )
    manifest = {
        "backend_version": HADDOCK3_BACKEND_VERSION,
        "prepared": asdict(prepared),
        "input_sha256": {"receptor": _sha256(receptor_copy), "peptide": _sha256(peptide_copy)},
        "claim_guard": "This manifest is preparation metadata only. A docking result exists only after a real HADDOCK3 process succeeds and scored pose artifacts are validated.",
    }
    (job_dir / "haddock3_job_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _read_score_rows(tsv: Path) -> list[dict[str, Any]]:
    try:
        with tsv.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            rows = []
            for row in reader:
                lower = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
                if "structure" not in lower or "score" not in lower:
                    continue
                try:
                    score = float(str(lower["score"]).strip())
                except Exception:
                    continue
                rows.append({"structure": str(lower["structure"]).strip(), "score": score, "source_score_table": str(tsv)})
            return rows
    except Exception:
        return []


def _stage_number(path: Path) -> int:
    best = -1
    for part in path.parts:
        m = re.match(r"(\d+)_", part)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _resolve_structure(run_dir: Path, score_table: Path, structure: str) -> Path | None:
    name = Path(structure).name
    candidates = [score_table.parent / structure, score_table.parent / name]
    for parent in score_table.parents:
        if parent == run_dir.parent:
            break
        candidates.append(parent / name)
    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()
    hits = list(run_dir.rglob(name))
    return hits[0].resolve() if hits else None


def harvest_haddock3_poses(run_dir: str | Path, output_dir: str | Path, pose_limit: int = 5) -> dict[str, Any]:
    run = Path(run_dir).expanduser().resolve()
    if not run.exists():
        raise FileNotFoundError(run)
    scored_tables: list[tuple[int, Path, list[dict[str, Any]]]] = []
    for tsv in run.rglob("*.tsv"):
        rows = _read_score_rows(tsv)
        if rows:
            scored_tables.append((_stage_number(tsv), tsv, rows))
    if not scored_tables:
        return {"status": "NO_SCORED_POSES", "pose_count": 0, "score_table": None, "poses": []}
    # Prefer the latest stage; within a stage prefer caprieval-like output and
    # then the largest scored table.
    scored_tables.sort(key=lambda x: (x[0], "capri" in x[1].name.lower(), len(x[2])), reverse=True)
    _stage, chosen, rows = scored_tables[0]
    rows = sorted(rows, key=lambda r: r["score"])
    out = Path(output_dir).expanduser().resolve()
    pose_dir = out / "poses"
    pose_dir.mkdir(parents=True, exist_ok=True)
    harvested: list[dict[str, Any]] = []
    for row in rows:
        source = _resolve_structure(run, chosen, row["structure"])
        if source is None or not source.exists() or source.stat().st_size <= 0:
            continue
        rank = len(harvested) + 1
        dest = pose_dir / f"pose_{rank:02d}.pdb"
        shutil.copy2(source, dest)
        harvested.append({
            "rank": rank,
            "score": row["score"],
            "score_type": "HADDOCK_score_lower_better",
            "source_structure": str(source),
            "pose_pdb": str(dest),
            "pose_sha256": _sha256(dest),
            "source_score_table": str(chosen),
        })
        if len(harvested) >= max(1, int(pose_limit)):
            break
    if not harvested:
        return {"status": "SCORES_PRESENT_BUT_POSES_MISSING", "pose_count": 0, "score_table": str(chosen), "poses": []}
    csv_path = out / "haddock3_top_poses.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(harvested[0].keys()))
        writer.writeheader(); writer.writerows(harvested)
    payload = {
        "status": "COMPLETED_SCORED_POSES",
        "pose_count": len(harvested),
        "score_table": str(chosen),
        "poses": harvested,
        "claim_guard": "HADDOCK score ranks generated models within this workflow; it is not experimental affinity or Kd.",
    }
    (out / "haddock3_pose_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def run_haddock3_job(
    prepared_job_dir: str | Path,
    *,
    executable: str = "haddock3",
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    job_dir = Path(prepared_job_dir).expanduser().resolve()
    manifest_path = job_dir / "haddock3_job_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing HADDOCK3 job manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg = Path(manifest["prepared"]["workflow_cfg"])
    run_dir = Path(str(manifest["prepared"]["job_dir"])) / "haddock3_run"
    readiness = detect_haddock3(executable)
    status_path = job_dir / "haddock3_execution.json"
    if not readiness["available"]:
        payload = {"status": "BACKEND_UNAVAILABLE", "readiness": readiness, "poses": []}
        status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    started = time.time()
    command = [str(readiness["executable"]), str(cfg)]
    try:
        cp = subprocess.run(
            command, cwd=str(job_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=timeout_seconds, check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        cp = None
        timed_out = True
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    else:
        stdout, stderr = cp.stdout or "", cp.stderr or ""
    (job_dir / "haddock3_stdout.log").write_text(stdout, encoding="utf-8")
    (job_dir / "haddock3_stderr.log").write_text(stderr, encoding="utf-8")
    if timed_out:
        status = "TIMEOUT"
        returncode = None
        poses = []
    else:
        returncode = int(cp.returncode)
        if returncode != 0:
            status = "FAILED"
            poses = []
        else:
            harvested = harvest_haddock3_poses(run_dir, job_dir / "results", manifest["prepared"]["requested_pose_limit"])
            status = harvested["status"]
            poses = harvested.get("poses", [])
    payload = {
        "status": status,
        "readiness": readiness,
        "command": command,
        "returncode": returncode,
        "elapsed_seconds": round(time.time() - started, 3),
        "stdout_log": str(job_dir / "haddock3_stdout.log"),
        "stderr_log": str(job_dir / "haddock3_stderr.log"),
        "run_dir": str(run_dir),
        "poses": poses,
        "claim_guard": "Only verified PDB files tied to an actual HADDOCK score table are returned as poses.",
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "HADDOCK3_BACKEND_VERSION", "PRESETS", "detect_haddock3", "write_haddock_air",
    "prepare_haddock3_job", "harvest_haddock3_poses", "run_haddock3_job",
]
