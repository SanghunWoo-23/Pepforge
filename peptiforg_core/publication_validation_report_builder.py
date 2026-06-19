from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import csv, json, re
from datetime import datetime
from peptiforg_core.external_md_result_import_bridge import export_external_md_result_import_bridge
PUBLICATION_REPORT_BUILDER_VERSION = "2.5.0"

def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "modified_peptide")).strip("_") or "modified_peptide"
def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8"); return str(path)
def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"); return str(path)
def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None: fieldnames = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore"); w.writeheader(); [w.writerow(r) for r in rows]
    return str(path)
def _load_json_if_exists(path):
    if not path: return {}
    p=Path(path)
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception: return {}
def _read_csv_if_exists(path):
    if not path: return []
    p=Path(path)
    if not p.exists(): return []
    try:
        with p.open("r", encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
    except Exception: return []

def build_claim_guard_table() -> list[dict[str,str]]:
    return [
        {"claim_type":"true_nM_binder","unsafe_claim":"This peptide is a true nM binder.","status":"blocked","safe_expression":"This peptide is a predicted nM-range candidate by a computational screening workflow and requires experimental validation.","required_evidence":"calibrated model plus external docking/MD and experimental binding assay"},
        {"claim_type":"final_Kd","unsafe_claim":"Pepforge provides the final Kd.","status":"blocked","safe_expression":"Pepforge reports screening-level or imported evidence; final Kd requires experimental measurement or rigorous validated workflow.","required_evidence":"SPR/ITC/MST/ELISA or comparable validated assay, or clearly stated external computational protocol"},
        {"claim_type":"full_MD","unsafe_claim":"Pepforge performed full publication-grade MD.","status":"blocked","safe_expression":"Pepforge generated preparation/import/report packages; full MD must be performed by external engines and documented separately.","required_evidence":"OpenMM/GROMACS/AMBER/NAMD protocol, force field, runtime, convergence, and trajectory analysis"},
        {"claim_type":"external_engine_replacement","unsafe_claim":"Pepforge replaces AutoDock Vina, GROMACS, AMBER, or OpenMM.","status":"blocked","safe_expression":"Pepforge is a low-spec preparation, screening, validation-bridge, and reporting workbench.","required_evidence":"not applicable; do not claim replacement"},
        {"claim_type":"screening_candidate","unsafe_claim":"This is a validated binder.","status":"allowed_with_qualification","safe_expression":"This is a computationally prioritized peptide candidate based on contact, clash, conformer, and optional external evidence summaries.","required_evidence":"Pepforge evidence report and optional external/imported validation summaries"},
    ]
def compute_publication_readiness(evidence_report, md_summary, docking_rows):
    warnings=[]; score=0
    if evidence_report: score+=1
    else: warnings.append("Pepforge evidence report not detected.")
    md_grade=str(md_summary.get("validation_grade","")).upper()
    if md_grade in {"A","B"}: score+=2
    elif md_grade=="C": score+=1; warnings.append("External MD evidence is partial/minimization-level.")
    else: warnings.append("External MD evidence is absent, weak, or not imported.")
    if docking_rows: score+=1
    else: warnings.append("External docking score import not detected.")
    if score>=4:
        grade="B"; status="publication_support_package_ready"; interp="The package is organized enough to support a Methods/Supporting Information style computational screening report, but final binding claims still require validation."
    elif score>=2:
        grade="C"; status="screening_report_ready"; interp="The package is suitable for screening and triage reporting, but not for final quantitative claims."
    else:
        grade="D"; status="preparation_only"; interp="The package is mainly a preparation/bridge artifact and should not be used for strong claims."
    return {"publication_readiness_grade":grade,"publication_readiness_status":status,"interpretation":interp,"score":score,"warnings":warnings,"claim_boundary":"This report organizes evidence and claim guards. It does not prove experimental binding or replace external docking/MD engines."}
def export_publication_validation_report(sequence: str, output_dir: str|Path, name: str="modified_peptide", external_md_csv=None, external_docking_scores_csv=None, receptor_path=None, center=(0.0,0.0,0.0), size=(22.0,22.0,22.0)) -> Dict[str,str]:
    out=Path(output_dir); safe=_safe_name(name); out.mkdir(parents=True, exist_ok=True)
    upstream=export_external_md_result_import_bridge(sequence=sequence, output_dir=out, name=safe, external_md_csv=external_md_csv, receptor_path=receptor_path, center=center, size=size)
    pub=out/"publication_validation_report_builder"; pub.mkdir(parents=True, exist_ok=True)
    evidence=_load_json_if_exists(upstream.get("evidence_report_json") or upstream.get("modified_peptide_evidence_report"))
    md_summary=_load_json_if_exists(upstream.get("external_md_validation_summary_json"))
    docking_rows=_read_csv_if_exists(external_docking_scores_csv)
    readiness=compute_publication_readiness(evidence, md_summary, docking_rows)
    claim_guard=pub/"claim_guard_table.csv"; _write_csv(claim_guard, build_claim_guard_table())
    docking_import=pub/"external_docking_scores_imported.csv"
    _write_csv(docking_import, docking_rows if docking_rows else [{"note":"No external docking score CSV was imported. Fill this file or rerun with external_docking_scores_csv for Vina/Smina/Gnina results."}])
    report={"pepforge_version":PUBLICATION_REPORT_BUILDER_VERSION,"created_utc":datetime.utcnow().isoformat(timespec="seconds")+"Z","sequence":sequence,"name":safe,"evidence_report_present":bool(evidence),"external_md_summary_present":bool(md_summary),"external_docking_scores_present":bool(docking_rows),"publication_readiness":readiness,"safe_claims":["computationally prioritized peptide candidate","predicted nM-range candidate only when calibration/evidence supports that wording","external validation required","Pepforge validation bridge package prepared"],"blocked_claims":["true nM binder proven by Pepforge","final Kd measured by Pepforge","full publication-grade MD performed internally by Pepforge","AutoDock Vina/GROMACS/AMBER/OpenMM replacement"],"upstream_bridge_files":upstream}
    report_json=pub/"publication_validation_report.json"; _write_json(report_json, report)
    warnings_md="\n".join(f"- {w}" for w in readiness.get("warnings",[])) or "- none"
    report_md=pub/"publication_validation_report.md"
    _write_text(report_md, f"""# Pepforge Publication Validation Report\n\n**Pepforge version:** {PUBLICATION_REPORT_BUILDER_VERSION}  \n**Peptide input:** `{sequence}`  \n**Report status:** {readiness.get('publication_readiness_status')}  \n**Readiness grade:** {readiness.get('publication_readiness_grade')}\n\n## Interpretation\n\n{readiness.get('interpretation')}\n\n## Evidence included\n\n- Pepforge evidence report present: `{bool(evidence)}`\n- External MD summary present: `{bool(md_summary)}`\n- External docking scores present: `{bool(docking_rows)}`\n\n## Warnings\n\n{warnings_md}\n\n## Safe claims\n\n- Computationally prioritized peptide candidate.\n- Screening-level candidate for further validation.\n- Predicted nM-range candidate only when calibration and imported/external evidence support that wording.\n- External validation required for final quantitative claims.\n\n## Blocked claims\n\n- Pepforge proves this peptide is a true nM binder.\n- Pepforge provides a final experimental Kd.\n- Pepforge internally performed full publication-grade all-atom MD.\n- Pepforge replaces AutoDock Vina, GROMACS, AMBER, OpenMM, NAMD, or experimental assays.\n\n## Methods-style sentence\n\nPeptide structure generation, low-spec conformer screening, validation-bridge preparation, and evidence report organization were performed using Pepforge Public Research Release {PUBLICATION_REPORT_BUILDER_VERSION}. External docking, all-atom MD, and experimental validation are required for final quantitative binding claims.\n\n## Claim boundary\n\n{readiness.get('claim_boundary')}\n""")
    methods=pub/"methods_sentence_template.txt"
    _write_text(methods, f"""Suggested methods wording\n=========================\n\nPeptide notation parsing, modified-peptide structure generation, low-spec conformer screening, contact-oriented evidence organization, and validation-bridge package generation were performed using Pepforge Public Research Release {PUBLICATION_REPORT_BUILDER_VERSION}. Externally generated docking or molecular-dynamics results, when used, were imported only as supporting validation evidence. Pepforge outputs were interpreted as screening and triage results rather than final experimental Kd or proof of binding.\n\nSuggested limitation wording\n============================\n\nPepforge does not replace AutoDock Vina, GROMACS, AMBER, OpenMM, NAMD, or experimental binding assays. Modified peptide residues, linkers, labels, and lipid-like moieties may require external force-field parameterization for publication-grade all-atom simulation.\n""")
    manifest=pub/"pepforge_v2_5_publication_bridge_manifest.json"; _write_json(manifest, {"pepforge_version":PUBLICATION_REPORT_BUILDER_VERSION,"sequence":sequence,"name":safe,"publication_report":str(report_json),"publication_report_markdown":str(report_md),"claim_guard_table":str(claim_guard),"methods_sentence_template":str(methods),"external_docking_scores_imported":str(docking_import),"upstream":upstream})
    paths=dict(upstream); paths.update({"publication_validation_report_json":str(report_json),"publication_validation_report_md":str(report_md),"claim_guard_table":str(claim_guard),"methods_sentence_template":str(methods),"external_docking_scores_imported":str(docking_import),"publication_bridge_manifest":str(manifest)})
    return paths
__all__=["PUBLICATION_REPORT_BUILDER_VERSION","build_claim_guard_table","compute_publication_readiness","export_publication_validation_report"]
