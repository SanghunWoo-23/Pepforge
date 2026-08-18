from __future__ import annotations

"""Evidence-linked SPPS and peptide-design guidance.

The rules in this module are decision support, not universal synthetic SOPs.
They deliberately separate a sequence trigger from an operator action and from
the experiment/analytical check needed to accept that action.
"""

from typing import Any
import re
import pandas as pd

from .parser import parse_sequence


REFERENCES = {
    "FMOC_REVIEW": "Behrendt et al., J Pept Sci 2016, DOI:10.1002/psc.2836",
    "COUPLING": "El-Faham & Albericio, Chem Rev 2011, DOI:10.1021/cr100048w",
    "PROTECTING_GROUPS": "Isidro-Llobet et al., Chem Rev 2009, DOI:10.1021/cr800323s",
    "CYS_PG": "Spears et al., Chem Soc Rev 2021, DOI:10.1039/D0CS01125F",
    "MILD_CLEAVAGE": "Gongora-Benitez et al., ACS Comb Sci 2013, DOI:10.1021/co300153c",
    "CTC": "Barlos et al., Int J Pept Protein Res 1991, DOI:10.1111/j.1399-3011.1991.tb00769.x",
    "CLEAVAGE": "King et al., Int J Pept Protein Res 1990, PMID:2258264",
    "MET": "Huang & Rabenstein, J Pept Res 1999, DOI:10.1034/j.1399-3011.1999.00059.x",
    "DIFFICULT": "Coin et al., Nat Protoc 2007, DOI:10.1038/nprot.2007.454",
    "PSEUDOPROLINE": "Wohr et al., JACS 1996, DOI:10.1021/ja961509q",
    "ASPARTIMIDE": "Kong et al., ChemBioChem 2025, DOI:10.1002/cbic.202500490",
    "DISULFIDE": "White & Yudin, Nat Chem 2011, DOI:10.1038/nchem.1062",
    "CD": "Greenfield, Nat Protoc 2006, DOI:10.1038/nprot.2006.202",
    "PEPFOLD": "Lamiable et al., NAR 2016, DOI:10.1093/nar/gkw329",
    "SUSTAINABILITY": "Isidro-Llobet et al., J Org Chem 2019, DOI:10.1021/acs.joc.8b03001",
}


def _canonical_tokens(sequence: str) -> tuple[list[str], list[str]]:
    parsed = parse_sequence(sequence)
    raw = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
    canonical = []
    unsupported = []
    for token in raw:
        text = str(token)
        base = text[1:] if text.startswith("d") and len(text) == 2 else text
        if len(base) == 1 and base.upper() in set("ARNDCQEGHILKMFPSTWYV"):
            canonical.append(base.upper())
        else:
            unsupported.append(text)
    return canonical, unsupported


def _runs(sequence: str, accepted: set[str], minimum: int) -> list[str]:
    return [m.group(0) for m in re.finditer("[" + "".join(sorted(accepted)) + "]{" + str(minimum) + ",}", sequence)]


def _motifs(sequence: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if pattern in sequence]


def generate_literature_guidance(inp: Any) -> pd.DataFrame:
    sequence_text = str(getattr(inp, "sequence", "") or "")
    resin = str(getattr(inp, "resin", "") or "")
    tokens, unsupported = _canonical_tokens(sequence_text)
    sequence = "".join(tokens)
    counts = {aa: sequence.count(aa) for aa in set(sequence)}
    explicit_groups = re.findall(r"[A-Za-z](?:\((Trt|Acm|StBu|Mob|Mtt|Dde|Boc|Pbf|OtBu|tBu)\))", sequence_text, flags=re.I)
    rows: list[dict[str, Any]] = []

    def add(category: str, trigger: str, priority: str, recommendation: str,
            verification: str, evidence: str, limitation: str = "Apply only after local SOP and reagent/resin compatibility review."):
        rows.append({
            "category": category, "trigger": trigger, "priority": priority,
            "recommendation": recommendation, "verification_required": verification,
            "evidence": evidence, "limitation": limitation,
        })

    add("workflow", "all Fmoc-SPPS plans", "INFO",
        "Use iterative loading/coupling/Fmoc-deprotection/wash operations; use excess reagent only as specified by the active plan.",
        "Kaiser/chloranil or another validated completion test; crude HPLC and MS.", REFERENCES["FMOC_REVIEW"])
    add("coupling", "selected coupling system", "REVIEW",
        "Check that activator, additive, base and solvent are a chemically coherent system; evaluate racemization-sensitive residues and heating separately.",
        "Small-scale coupling/deletion-impurity comparison before scale-up.", REFERENCES["COUPLING"])

    pg_map = {
        "R": "Arg(Pbf) is the common Fmoc/tBu-compatible default.",
        "K": "Use Lys(Boc) for global TFA removal; use orthogonal Lys(Mtt/Dde) only when selective side-chain access is intended.",
        "D": "Asp(OtBu) is common, but Asp-X still requires aspartimide control.",
        "E": "Glu(OtBu) is the common acid-labile side-chain protection.",
        "S": "Ser(tBu) is common; pseudoproline may be considered in aggregation-prone segments.",
        "T": "Thr(tBu) is common; pseudoproline may be considered in aggregation-prone segments.",
        "Y": "Tyr(tBu) is common and needs cation-scavenging review during cleavage.",
        "W": "Trp(Boc) or unprotected indole choice is sequence/SOP dependent; cleavage scavenging must be reviewed.",
        "C": "Cys(Trt) suits global thiol release; Acm/StBu/Mob-type choices require an explicit orthogonal disulfide plan.",
        "N": "Asn(Trt) is commonly used to suppress side-chain reactions.",
        "Q": "Gln(Trt) is commonly used to suppress side-chain reactions.",
        "H": "His(Trt) is common; coupling/base/heating conditions require racemization review.",
    }
    for aa, message in pg_map.items():
        if counts.get(aa, 0):
            add("protecting_group", f"{aa} x{counts[aa]}", "REVIEW", message,
                "Confirm exact purchased protected form and orthogonality against every planned selective step.", REFERENCES["PROTECTING_GROUPS"] if aa != "C" else REFERENCES["CYS_PG"])
    if explicit_groups:
        add("protecting_group", "explicit groups=" + ",".join(explicit_groups), "HIGH",
            "Preserve the explicitly entered protecting groups in the material plan and check every group against coupling, Fmoc removal, selective deprotection and final cleavage.",
            "Review an orthogonality matrix and confirm each purchased reagent identity before synthesis.", REFERENCES["PROTECTING_GROUPS"])

    resin_key = re.sub(r"[^a-z0-9]+", "", resin.lower())
    if "2ctc" in resin_key or "chlorotrityl" in resin_key:
        add("resin_linker", resin, "HIGH",
            "Distinguish mild protected-fragment cleavage from final global deprotection. AcOH/TFE/DCM or very dilute TFA routes are mild-cleavage options, not interchangeable universal recipes.",
            "Check loading, C-terminal identity and side-chain protection retention by analytical cleavage/HPLC/MS.", REFERENCES["CTC"])
    elif "sieber" in resin_key or "xal" in resin_key:
        add("resin_linker", resin, "HIGH",
            "Treat as a mild-cleavage amide-handle workflow when a side-chain-protected peptide amide is intended.",
            "Confirm linker-specific cleavage conditions and retained protection analytically.", REFERENCES["MILD_CLEAVAGE"])
    elif "rink" in resin_key or "amide" in resin_key or "pal" in resin_key:
        add("resin_linker", resin or "amide-family resin", "REVIEW",
            "Plan for a C-terminal amide. Rink/PAL-family release is normally an acid-labile global-cleavage workflow unless the exact handle specification states otherwise.",
            "Verify product C-terminal amide by MS and confirm the supplier's linker/protection compatibility.", REFERENCES["MILD_CLEAVAGE"])
    else:
        add("resin_linker", resin or "amide-family resin", "REVIEW",
            "Confirm whether the selected resin yields C-terminal amide or acid and whether cleavage is global or protected-fragment release.",
            "Verify product C terminus by MS and selected resin specification.", REFERENCES["MILD_CLEAVAGE"])

    sensitive = [aa for aa in "CMWY" if counts.get(aa, 0)]
    if sensitive:
        add("cleavage", ",".join(f"{aa}x{counts[aa]}" for aa in sensitive), "HIGH",
            "Use the sequence-aware cleavage preset as a starting point and review scavengers for sulfur-, indole- and phenol-sensitive residues.",
            "Compare crude HPLC/MS for oxidation, alkylation and incomplete deprotection products.", REFERENCES["CLEAVAGE"])
    if counts.get("M", 0):
        add("cleavage", "Met present", "HIGH",
            "Evaluate Reagent H or another validated reducing/scavenging protocol; do not treat Met oxidation and acid-promoted S-alkylation as the same impurity.",
            "Monitor Met(O) and sulfonium/alkylation masses by LC-MS.", REFERENCES["MET"])
    if counts.get("C", 0):
        add("cleavage", "Cys present", "HIGH",
            "Monitor cleavage-derived Cys alkylation, including S-tert-butylated products where relevant; scavenger choice must follow the actual Cys protecting group and linker system.",
            "Search the crude LC-MS for protected, alkylated, overoxidized and disulfide-linked products; Cys(S-tBu) gives a characteristic +56.0626 Da shift.", "Org Process Res Dev 2025, DOI:10.1021/acs.oprd.4c00443")

    asp = _motifs(sequence, ("DG", "DN", "DS", "DA"))
    if asp:
        add("aspartimide", ",".join(asp), "HIGH",
            "Minimize cumulative base exposure and heat; evaluate the reported 1 M Oxyma in 20% piperidine/DMF deprotection approach, backbone protection or a sequence-appropriate protected building block. Treat this as an intervention to validate, not a universal default.",
            "Quantify aspartimide and alpha/beta-piperidide-related impurities by HPLC/MS in a small-scale test.", REFERENCES["ASPARTIMIDE"])
    hydro = _runs(sequence, set("LIVMFYW"), 4)
    branched = _runs(sequence, set("VIT"), 3)
    if hydro or branched or len(sequence) >= 18:
        add("difficult_sequence", f"hydrophobic_runs={hydro}; VIT_runs={branched}; length={len(sequence)}", "HIGH",
            "Increase monitoring and consider lower-loading/PEG-type resin, double coupling only where needed, pseudoproline, depsipeptide or backbone-protection strategies.",
            "Track resin swelling, coupling/deprotection completion and deletion impurities; compare a small-scale intervention arm.", REFERENCES["DIFFICULT"])
    if any(word in resin_key for word in ("chemmatrix", "tentagel", "peg")):
        add("resin_solvatation", resin, "INFO",
            "PEG-rich resin can improve solvation for some hydrophobic/polycationic difficult sequences, but loading and swelling still require optimization.",
            "Measure swelling and compare conversion/crude purity at the intended loading.", "Garcia-Martin et al., J Comb Chem 2006, DOI:10.1021/cc0600019")
    pseudo_sites = [sequence[i:i + 2] for i in range(max(0, len(sequence) - 1)) if sequence[i + 1] in "ST"]
    if pseudo_sites and (hydro or branched or len(sequence) >= 18):
        add("pseudoproline", ",".join(sorted(set(pseudo_sites))), "REVIEW",
            "Evaluate a commercially/chemically valid Xaa-Ser/Thr pseudoproline dipeptide near the difficult segment; do not substitute one without checking sequence and reagent availability.",
            "Compare crude purity and deletion profile against the unmodified route.", REFERENCES["PSEUDOPROLINE"])

    cys = counts.get("C", 0)
    if cys:
        if cys == 1:
            strategy = "One free Cys cannot form a defined intramolecular disulfide alone; cap, conjugate, pair with another designed Cys, or control intermolecular oxidation."
        elif cys == 2:
            strategy = "A single intramolecular disulfide is possible; define whether oxidation is on-resin or in solution and preserve both thiols until that step."
        else:
            strategy = "Multiple disulfide connectivities are possible; define the intended pairing and use orthogonal Cys protection or a validated folding protocol."
        add("disulfide_cyclization", f"Cys x{cys}", "HIGH", strategy,
            "Confirm monomer/oligomer state and connectivity by LC-MS plus mapping or orthogonal analytical evidence.", REFERENCES["CYS_PG"])
        add("oxidation_options", "disulfide intended", "REVIEW",
            "Air, DMSO, glutathione redox, iodine or ferricyanide are distinct oxidation routes; choose by protecting group, sequence and side-reaction compatibility.",
            "Optimize concentration, pH and time on small scale; monitor intermolecular dimer and overoxidation.", REFERENCES["DISULFIDE"])

    if sequence.startswith("Q"):
        add("chemical_liability", "N-terminal Gln", "REVIEW", "Evaluate pyroglutamate formation during processing/storage.",
            "LC-MS time-course under intended formulation conditions.", REFERENCES["FMOC_REVIEW"])
    if counts.get("N", 0):
        add("chemical_liability", f"Asn x{counts['N']}", "REVIEW", "Evaluate sequence- and pH-dependent deamidation during processing/storage.",
            "Stability-indicating LC-MS/HPLC under intended conditions.", REFERENCES["FMOC_REVIEW"])

    add("workup_counterion", "TFA cleavage/workup", "REVIEW",
        "Record the isolated counterion. Ether precipitation removes bulk cleavage reagents but does not prove quantitative TFA removal or a defined salt stoichiometry.",
        "Use ion analysis or a validated counterion assay when salt identity/stoichiometry matters.", REFERENCES["FMOC_REVIEW"])
    add("workup_counterion", "acetate salt requested", "REVIEW",
        "Use a validated repeated dissolve/lyophilize or ion-exchange workflow with dilute acetic acid; do not label material acetate solely because AcOH was contacted.",
        "Confirm residual TFA and acetate by an appropriate ion method.", REFERENCES["MILD_CLEAVAGE"])

    add("structure_validation", "sequence-derived structure candidates", "INFO",
        "Use Top-5 conformer families for screening; use CD for global secondary-structure tendency and NMR or another high-resolution method for residue-level claims.",
        "Compare conditions because pH, salt, solvent, membrane and binding partner can change the ensemble.", REFERENCES["CD"] + "; " + REFERENCES["PEPFOLD"])
    add("external_validation", "docking/MD", "INFO",
        "Treat docking and MD as external validation. Modified and mixed-backbone residues require explicit parameters; Pepforge does not fabricate them.",
        "Document force field, protonation, solvent, sampling and convergence; compare with experiment.", REFERENCES["PEPFOLD"])
    add("sustainability", "process review", "INFO",
        "Reduce excess, solvent volume and repeated operations only after maintaining reaction completion; greener solvent substitution requires resin/reagent compatibility validation.",
        "Compare conversion, impurity profile, solvent use and waste against the established process.", REFERENCES["SUSTAINABILITY"])

    if unsupported:
        add("noncanonical_backbone", ",".join(unsupported), "HIGH",
            "Use explicit building-block identity, stereochemistry, protecting groups, coupling method and analytical standard. Do not inherit canonical-alpha residue parameters.",
            "Confirm incorporation and structure experimentally; dedicated beta/gamma/foldamer parameters are required for modeling.", "Shin & Gellman, JACS 2018, DOI:10.1021/jacs.7b10868")

    return pd.DataFrame(rows, columns=[
        "category", "trigger", "priority", "recommendation",
        "verification_required", "evidence", "limitation",
    ])


__all__ = ["REFERENCES", "generate_literature_guidance"]
