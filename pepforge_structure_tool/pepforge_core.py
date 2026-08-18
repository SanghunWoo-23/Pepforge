
"""
Pepforge PyMOL Structure Tool core
v1.3.0

Purpose
-------
Create a chemically connected 3D starting model for modified peptides and
export SDF/PDB/JSON files that can be loaded and inspected in PyMOL.

Fixed interpretation rule
-------------------------
STD AA      : A C D E F G H I K L M N P Q R S T V W Y
D-form      : dA, dK, dF, ... ; chirality-inverted canonical residue
Non-natural : Aib, Nle, Orn, Dab, Cit, Hyp, Cha, Nal, ... ; sequence monomer
Linker      : Ahx, PEG4, PEG8, AEEA, bAla, gAla ; spacer, not STD residue
Label       : Biotin, FITC(=5-FITC convention), FAM(=5-FAM convention);
              TAMRA/Cy5/NBD/DOTA remain recognized but require a curated derivative
Terminal    : Ac, Boc, NH2, OH ; terminal modifications
Side-chain  : primary-amine residues use only explicit linker/label/acyl rules;
              generic Cys/electrophile chemistry is never fabricated

Important limitation
--------------------
This is a connected 3D starting-model / conformer-ensemble generator, not a native-
structure predictor.  Only chemistry with an explicit residue/linker/attachment graph
is buildable.  Ambiguous generic label/chemical names remain parseable for project
compatibility but are blocked from 3D generation until a curated derivative is
specified.  RDKit conformer geometry is a starting ensemble, not experimental proof.
"""
from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re
import json
import csv
import os

from peptiforg_core.peptide_conformation import (
    analyze_conformer_ensemble, canonical_l_helix_evidence, EVIDENCE_REFERENCES,
    add_canonical_l_backbone_seed_conformers, sequence_conformation_evidence,
    select_top_conformers, pairwise_conformer_rmsd, evidence_guided_family_plan,
)

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
except Exception as exc:  # pragma: no cover
    Chem = None
    AllChem = None
    Descriptors = None
    rdMolDescriptors = None
    _RDKIT_IMPORT_ERROR = exc
else:
    _RDKIT_IMPORT_ERROR = None

VERSION = "1.3.0"

# -----------------------------------------------------------------------------
# Monomer/linker/label libraries
# -----------------------------------------------------------------------------
L_RESIDUE_UNITS: Dict[str, str] = {
    "G": "NCC(=O)",
    "A": "N[C@@H](C)C(=O)",
    "V": "N[C@@H](C(C)C)C(=O)",
    "L": "N[C@@H](CC(C)C)C(=O)",
    "I": "N[C@@H]([C@H](C)CC)C(=O)",
    "S": "N[C@@H](CO)C(=O)",
    "T": "N[C@@H]([C@H](O)C)C(=O)",
    "C": "N[C@@H](CS)C(=O)",
    "M": "N[C@@H](CCSC)C(=O)",
    "D": "N[C@@H](CC(=O)O)C(=O)",
    "E": "N[C@@H](CCC(=O)O)C(=O)",
    "N": "N[C@@H](CC(=O)N)C(=O)",
    "Q": "N[C@@H](CCC(=O)N)C(=O)",
    "K": "N[C@@H](CCCCN)C(=O)",
    "R": "N[C@@H](CCCNC(=N)N)C(=O)",
    "H": "N[C@@H](Cc1c[nH]cn1)C(=O)",
    "F": "N[C@@H](Cc1ccccc1)C(=O)",
    "Y": "N[C@@H](Cc1ccc(O)cc1)C(=O)",
    "W": "N[C@@H](Cc1c[nH]c2ccccc12)C(=O)",
    "P": "N1CCC[C@H]1C(=O)",
}
D_RESIDUE_UNITS: Dict[str, str] = {
    "G": "NCC(=O)",
    "A": "N[C@H](C)C(=O)",
    "V": "N[C@H](C(C)C)C(=O)",
    "L": "N[C@H](CC(C)C)C(=O)",
    "I": "N[C@H]([C@@H](C)CC)C(=O)",
    "S": "N[C@H](CO)C(=O)",
    "T": "N[C@H]([C@@H](O)C)C(=O)",
    "C": "N[C@H](CS)C(=O)",
    "M": "N[C@H](CCSC)C(=O)",
    "D": "N[C@H](CC(=O)O)C(=O)",
    "E": "N[C@H](CCC(=O)O)C(=O)",
    "N": "N[C@H](CC(=O)N)C(=O)",
    "Q": "N[C@H](CCC(=O)N)C(=O)",
    "K": "N[C@H](CCCCN)C(=O)",
    "R": "N[C@H](CCCNC(=N)N)C(=O)",
    "H": "N[C@H](Cc1c[nH]cn1)C(=O)",
    "F": "N[C@H](Cc1ccccc1)C(=O)",
    "Y": "N[C@H](Cc1ccc(O)cc1)C(=O)",
    "W": "N[C@H](Cc1c[nH]c2ccccc12)C(=O)",
    "P": "N1CCC[C@@H]1C(=O)",
}
NON_NATURAL_UNITS: Dict[str, str] = {
    "Aib": "NC(C)(C)C(=O)",
    "Nva": "N[C@@H](CCC)C(=O)", "dNva": "N[C@H](CCC)C(=O)",
    "Abu": "N[C@@H](CC)C(=O)", "dAbu": "N[C@H](CC)C(=O)",
    "Sar": "CNCC(=O)",
    "Nle": "N[C@@H](CCCC)C(=O)", "dNle": "N[C@H](CCCC)C(=O)",
    "Orn": "N[C@@H](CCCN)C(=O)", "dOrn": "N[C@H](CCCN)C(=O)",
    "Dab": "N[C@@H](CCN)C(=O)", "dDab": "N[C@H](CCN)C(=O)",
    "Dap": "N[C@@H](CN)C(=O)", "dDap": "N[C@H](CN)C(=O)",
    "Cit": "N[C@@H](CCCNC(=O)N)C(=O)", "dCit": "N[C@H](CCCNC(=O)N)C(=O)",
    "Hyp": "N1C[C@H](O)C[C@H]1C(=O)", "dHyp": "N1C[C@@H](O)C[C@@H]1C(=O)",
    "Cha": "N[C@@H](CC1CCCCC1)C(=O)", "dCha": "N[C@H](CC1CCCCC1)C(=O)",
    "Nal": "N[C@@H](Cc1cccc2ccccc12)C(=O)", "dNal": "N[C@H](Cc1cccc2ccccc12)C(=O)",
}

RECOGNIZED_NON_NATURAL_TOKENS = set(NON_NATURAL_UNITS) | {
    "Hyl", "Chg", "Tic", "Bip", "Phe4F", "Phe4Cl", "Phe4Me", "TyrMe",
    "hArg", "hLys", "MeAla", "MeGly", "MeLeu", "MePhe", "MeVal",
    "Sec", "Pen", "Pra",
}
NON_NATURAL_CHEMISTRY_METADATA: Dict[str, Dict[str, str]] = {
    "Aib": {"structure_convention": "2-aminoisobutyric acid", "source": "explicit achiral amino-acid graph"},
    "Nle": {"structure_convention": "L-norleucine", "source": "explicit alpha-amino-acid graph"},
    "dNle": {"structure_convention": "D-norleucine", "source": "mirror alpha stereochemistry"},
    "Orn": {"structure_convention": "L-ornithine", "source": "explicit alpha-amino-acid graph"},
    "dOrn": {"structure_convention": "D-ornithine", "source": "mirror alpha stereochemistry"},
    "Dab": {"structure_convention": "L-2,4-diaminobutyric acid", "source": "PubChem CID 134490 convention"},
    "dDab": {"structure_convention": "D-2,4-diaminobutyric acid", "source": "mirror alpha stereochemistry"},
    "Cit": {"structure_convention": "L-citrulline", "source": "explicit alpha-amino-acid graph"},
    "dCit": {"structure_convention": "D-citrulline", "source": "mirror alpha stereochemistry"},
    "Hyp": {"structure_convention": "trans-4-hydroxy-L-proline (2S,4R)", "source": "PubChem CID 5810"},
    "dHyp": {"structure_convention": "mirror D-trans-4-hydroxyproline", "source": "mirror stereochemistry of Hyp convention"},
    "Cha": {"structure_convention": "3-cyclohexyl-L-alanine", "source": "PubChem CID 712421"},
    "dCha": {"structure_convention": "3-cyclohexyl-D-alanine", "source": "mirror alpha stereochemistry"},
    "Nal": {"structure_convention": "1-naphthyl-L-alanine (1-Nal)", "source": "PubChem CID 2724883"},
    "dNal": {"structure_convention": "1-naphthyl-D-alanine (D-1-Nal)", "source": "mirror alpha stereochemistry"},
}
LINKER_UNITS: Dict[str, str] = {
    # Exact amino-acid/linker conventions used by Pepforge.  Each fragment is
    # written N->C so it can participate in the peptide-like linear chain.
    # Ahx = 6-aminohexanoic acid (PubChem CID 564).
    "Ahx": "NCCCCCC(=O)",
    # beta-Ala = 3-aminopropanoic acid (PubChem CID 239).
    "bAla": "NCCC(=O)",
    # gAla is Pepforge's historical token for gamma-aminobutyric acid / GABA
    # (4-aminobutanoic acid; PubChem CID 119).
    "gAla": "NCCCC(=O)",
    # AEEA = 2-[2-(2-aminoethoxy)ethoxy]acetic acid (PubChem CID 362706).
    "AEEA": "NCCOCCOCC(=O)",
    # PEG4/PEG8 are explicitly defined here as amino-PEG-propionic-acid
    # linkers, not as an arbitrary PEG repeat count.
    # PEG4: CAS 663921-15-1, C11H23NO6.
    "PEG4": "NCCOCCOCCOCCOCCC(=O)",
    # PEG8: CAS 756526-04-2, C19H39NO10.
    "PEG8": "NCCOCCOCCOCCOCCOCCOCCOCCOCCC(=O)",
}

for _peg_n in (1, 2, 3, 6, 12, 24):
    LINKER_UNITS[f"PEG{_peg_n}"] = "NCC" + ("OCC" * _peg_n) + "C(=O)"

SEQUENCE_LINKER_EXPANSIONS: Dict[str, str] = {
    "Gly": "G", "GG": "GG", "GGG": "GGG", "GS": "GS", "GSG": "GSG",
    "G4S": "GGGGS", "G4Sx2": "GGGGSGGGGS", "Pro": "P",
}
RECOGNIZED_LINKER_TOKENS = set(LINKER_UNITS) | set(SEQUENCE_LINKER_EXPANSIONS) | {
    "PipLink", "LysLink", "CysLink", "SS", "Triazole", "Click", "DSS",
    "SMCC", "SulfoSMCC", "EDC", "Hydrazone", "Oxime",
}

# Exact covalent label fragments.  These are attachment fragments for a
# peptide conjugate, NOT representations of the free labeling reagents.
# The fragment is written so the following peptide/linker N atom completes the
# experimentally conventional bond.
#
# FITC convention: Pepforge's historical `FITC` token is made deterministic as
# 5-FITC (fluorescein 5-isothiocyanate) and is reported as such in metadata.
# FAM convention: historical `FAM` is modeled as 5-FAM carboxamide and is
# likewise reported explicitly.  Users requiring another regioisomer should
# provide/use a curated derivative rather than silently receiving this model.
LABEL_UNITS: Dict[str, str] = {
    "Biotin": "[C@H]12[C@H](NC(N1)=O)[C@@H](SC2)CCCCC(=O)",
    "FITC": "c1(O)cc2Oc3c(ccc(c3)O)C3(c2cc1)c1ccc(cc1C(O3)=O)NC(=S)",
    "FAM": "c12C3(c4ccc(O)cc4Oc4cc(ccc34)O)OC(=O)c2cc(cc1)C(=O)",
}

# Recognized label names whose exact peptide-bound derivative is not determined
# by the token alone.  They remain parseable so existing projects are not
# silently reinterpreted, but 3D construction is blocked until a curated
# derivative/attachment rule is supplied.
AMBIGUOUS_LABEL_TOKENS = {
    "Desthiobiotin", "TAMRA", "ROX", "Cy3", "Cy5", "Cy5.5", "Cy7",
    "Alexa488", "Alexa555", "Alexa647", "DOTA", "NOTA", "DFO", "NBD",
    "Dansyl", "BODIPY", "EDANS", "Dabcyl", "BHQ1", "BHQ2",
}
LABEL_TOKENS = set(LABEL_UNITS) | AMBIGUOUS_LABEL_TOKENS

LABEL_CHEMISTRY_METADATA: Dict[str, Dict[str, Any]] = {
    "Biotin": {
        "evidence_status": "verified_database_structure_and_explicit_amide_rule",
        "attachment_chemistry": "biotin carboxyl -> peptide/linker primary amine; amide",
        "structure_convention": "biotin",
        "source": "PubChem CID 171548 (biotin); peptide-bound amide rule",
    },
    "FITC": {
        "evidence_status": "verified_database_structure_and_explicit_thiourea_rule",
        "attachment_chemistry": "5-FITC isothiocyanate -> peptide/linker primary amine; thiourea",
        "structure_convention": "5-FITC",
        "source": "PubChem CID 18730 (fluorescein 5-isothiocyanate)",
    },
    "FAM": {
        "evidence_status": "verified_database_structure_and_explicit_amide_rule",
        "attachment_chemistry": "5-FAM carboxyl -> peptide/linker primary amine; amide",
        "structure_convention": "5-FAM",
        "source": "PubChem CID 123755 (5-carboxyfluorescein); explicit Pepforge 5-FAM convention",
    },
    "TAMRA": {"evidence_status": "requires_curated_derivative", "attachment_chemistry": None, "structure_convention": None, "source": None},
    "NBD": {"evidence_status": "requires_curated_derivative", "attachment_chemistry": None, "structure_convention": None, "source": None},
    "DOTA": {"evidence_status": "requires_curated_derivative", "attachment_chemistry": None, "structure_convention": None, "source": None},
    "Cy5": {"evidence_status": "requires_curated_derivative", "attachment_chemistry": None, "structure_convention": None, "source": None},
}

# Substituents written immediately after an already-present primary amine N.
SIDECHAIN_AMINE_LABEL_SUBSTITUENTS: Dict[str, str] = {
    "Biotin": "C(=O)CCCC[C@@H]1SC[C@@H]2NC(=O)N[C@H]12",
    "FITC": "C(=S)Nc1ccc2c(c1)C(=O)OC21c2c(cc(O)cc2)Oc2cc(O)ccc21",
    "FAM": "C(=O)c1ccc2c(c1)C(=O)OC21c2ccc(O)cc2Oc2cc(O)ccc21",
}

# Linker fragments written from an already-present parent amine outward to the
# linker's terminal amine.  This avoids the former generic urea-like joining.
SIDECHAIN_AMINE_LINKER_FRAGMENTS: Dict[str, str] = {
    "Ahx": "C(=O)CCCCCN",
    "bAla": "C(=O)CCN",
    "gAla": "C(=O)CCCN",
    "AEEA": "C(=O)COCCOCCN",
    "PEG4": "C(=O)CCOCCOCCOCCOCCN",
    "PEG8": "C(=O)CCOCCOCCOCCOCCOCCOCCOCCOCCN",
}

# Chemical tokens are recognized independently of whether a unique covalent
# attachment is defined.  Only the explicit N-terminal/side-chain acyl rules
# below are buildable without additional derivative information.
CHEMICAL_TOKENS = {
    "Pal", "Myr", "Ste", "Lau", "Ole", "Chol", "Gal", "Caf", "Nic",
    "Bz", "Succinyl", "Maleimide", "Azide", "Alkyne", "DBCO", "TCO",
    "Tetrazine", "BiotinCap", "Mal", "Dde",
}
AMBIGUOUS_CHEMICAL_TOKENS = CHEMICAL_TOKENS - {"Pal", "Myr", "Ste", "Lau", "Gal", "Caf", "Nic"}

# Exact N-terminal acyl caps.
N_TERMINAL_ACYL_CHEM_CAPS: Dict[str, str] = {
    "Pal": "CCCCCCCCCCCCCCCC(=O)",          # palmitoyl, C16 acyl cap
    "Myr": "CCCCCCCCCCCCCC(=O)",            # myristoyl, C14 acyl cap
    "Ste": "CCCCCCCCCCCCCCCCCC(=O)",        # stearoyl, C18 acyl cap
    "Lau": "CCCCCCCCCCCC(=O)",              # lauroyl, C12 acyl cap
    "Gal": "O=C(c1cc(O)c(O)c(O)c1)",        # galloyl
    "Caf": "O=C(/C=C/c1ccc(O)c(O)c1)",      # caffeoyl
    "Nic": "O=C(c1ccncc1)",                 # nicotinoyl
}

# Tail fragments used after an already-written side-chain amide carbonyl.
SIDECHAIN_ACYL_TAILS: Dict[str, str] = {
    "Pal": "CCCCCCCCCCCCCCC",
    "Myr": "CCCCCCCCCCCCC",
    "Ste": "CCCCCCCCCCCCCCCCC",
    "Lau": "CCCCCCCCCCC",
    "Gal": "c1cc(O)c(O)c(O)c1",
    "Caf": "/C=C/c1ccc(O)c(O)c1",
    "Nic": "c1ccncc1",
}

N_TERMINAL_CAPS: Dict[str, str] = {"Ac": "CC(=O)", "Boc": "CC(C)(C)OC(=O)", "Fmoc": "O=C(OCC1c2ccccc2-c2ccccc21)"}
C_TERMINAL_CAPS = {"OH", "NH2"}
TAG_EXPANSIONS: Dict[str, str] = {
    "His6": "HHHHHH", "His8": "HHHHHHHH", "His10": "HHHHHHHHHH",
    "FLAG": "DYKDDDDK", "HA": "YPYDVPDYA", "Myc": "EQKLISEEDL",
    "Strep": "WSHPQFEK", "StrepII": "WSHPQFEK",
    "TwinStrep": "WSHPQFEKGGGSGGGSGGSAWSHPQFEK",
    "V5": "GKPIPNPLLGLDST", "T7": "MASMTGGQQMG",
    "ALFA": "SRLEEELRRRLTE", "AviTag": "GLNDIFEAQKIEWHE",
    "SpyTag": "AHIVMVDAYKPTK",
}
# User-facing aliases. STD is intentionally not changed: STD AA means the 20 canonical residues.
TOKEN_ALIASES: Dict[str, str] = {
    "amide": "NH2", "Amide": "NH2", "CtermNH2": "NH2",
    "acetyl": "Ac", "Acetyl": "Ac", "AC": "Ac",
    "biotin": "Biotin", "fitc": "FITC", "5FITC": "FITC",
    "fam": "FAM", "5FAM": "FAM", "tamra": "TAMRA", "cy5": "Cy5",
    "BIOTIN": "Biotin", "CY3": "Cy3", "CY5": "Cy5", "CY5_5": "Cy5.5", "CY7": "Cy7",
    "6Ahx": "Ahx", "Acp": "Ahx",
    "pal": "Pal", "PAL": "Pal", "palmiticacid": "Pal", "Palmiticacid": "Pal", "PalmiticAcid": "Pal", "palmitoyl": "Pal", "Palmitoyl": "Pal",
    "myr": "Myr", "MYR": "Myr", "myristicacid": "Myr", "MyristicAcid": "Myr", "myristoyl": "Myr",
    "gal": "Gal", "GAL": "Gal", "gallicacid": "Gal", "GallicAcid": "Gal", "galloyl": "Gal",
    "caf": "Caf", "CAF": "Caf", "caffeicacid": "Caf", "CaffeicAcid": "Caf", "caffeoyl": "Caf",
    "nic": "Nic", "NIC": "Nic", "nicotinicacid": "Nic", "NicotinicAcid": "Nic", "nicotinoyl": "Nic",
    "stearoyl": "Ste", "Stear": "Ste", "STEAR": "Ste",
    "cholesterol": "Chol", "Cholesterol": "Chol", "chol": "Chol",
}
STD_AA = set(L_RESIDUE_UNITS)
KNOWN_MULTI_TOKENS = sorted(
    set(N_TERMINAL_CAPS) | C_TERMINAL_CAPS | RECOGNIZED_NON_NATURAL_TOKENS |
    RECOGNIZED_LINKER_TOKENS | LABEL_TOKENS | CHEMICAL_TOKENS | set(TAG_EXPANSIONS) | set(TOKEN_ALIASES),
    key=len, reverse=True,
)
KIND_LABELS = {
    "n_terminal": "N-terminal modification",
    "c_terminal": "C-terminal modification",
    "std_aa": "STD L-amino acid",
    "d_std_aa": "STD D-amino acid",
    "non_natural_aa": "Non-natural amino acid",
    "linker": "Linker/spacer",
    "label": "Label/modification",
    "chemical": "Chemical modification",
    "tag_expansion": "Expanded affinity/epitope tag",
    "sidechain_label_aa": "Side-chain labeled amino acid",
    "c_terminal_atom": "C-terminal added atom",
}
SIDECHAIN_ACCEPTORS = {"K", "dK", "Orn", "dOrn", "Dab", "dDab", "C", "dC"}




def _infer_local_attach_points(smiles: Optional[str], category: str) -> Dict[str, Optional[int]]:
    """Infer 1-based heavy-atom ranks used as attach-site hints."""
    result: Dict[str, Optional[int]] = {"in_atom_1based": None, "out_atom_1based": None}
    if not smiles or Chem is None:
        return result
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return result
    for a in mol.GetAtoms():
        if a.GetAtomicNum() == 7:
            result["in_atom_1based"] = int(a.GetIdx()) + 1
            break
    carbonyls = []
    for a in mol.GetAtoms():
        if a.GetAtomicNum() != 6:
            continue
        for b in a.GetBonds():
            other = b.GetOtherAtom(a)
            if other.GetAtomicNum() == 8 and int(b.GetBondTypeAsDouble()) == 2:
                carbonyls.append(int(a.GetIdx()) + 1)
                break
    if category in {"std_aa", "d_std_aa", "sidechain_label_aa", "non_natural_aa", "linker", "chemical", "n_terminal"} and carbonyls:
        result["out_atom_1based"] = max(carbonyls)
    if category == "label":
        result["out_atom_1based"] = None
    return result

# Attachment-aware template registry.  A template is only advertised as
# buildable when its graph/attachment convention is explicitly defined.
TEMPLATE_ATTACHMENT_RULES: Dict[str, Dict[str, Any]] = {
    "non_natural_aa": {
        "chain_in": "backbone_N", "chain_out": "backbone_carbonyl_C",
        "expected_unit": "N...C(=O)", "usage": "sequence monomer; counted as peptide-like residue",
    },
    "linker": {
        "chain_in": "amine_N", "chain_out": "carbonyl_C",
        "expected_unit": "N...C(=O)", "usage": "explicit amino-acid/PEG-acid linker convention",
    },
    "label": {
        "chain_in": None, "chain_out": "peptide_or_linker_primary_amine",
        "expected_unit": "explicit peptide-bound label fragment",
        "usage": "N-terminal/side-chain label only when attachment chemistry is defined",
    },
    "chemical": {
        "chain_in": None, "chain_out": "peptide_primary_amine_when_acyl_rule_defined",
        "expected_unit": "explicit acyl fragment or curated derivative",
        "usage": "chemical modification; generic unknown linkage is never fabricated",
    },
}

TEMPLATE_READY_REGISTRY: Dict[str, Dict[str, Any]] = {}

def _register_template(_tok: str, _cat: str, _smiles: Optional[str], *, source: str, curation_status: str, template_available: bool = True, chemistry: Optional[Dict[str, Any]] = None) -> None:
    rec: Dict[str, Any] = {
        "token": _tok,
        "category": _cat,
        "source": source,
        "smiles": _smiles,
        "template_file": f"pepforge_structure_tool/data/templates/{_tok}.sdf" if template_available else None,
        "attach_points": TEMPLATE_ATTACHMENT_RULES[_cat],
        "local_attach_atom_hints": _infer_local_attach_points(_smiles, _cat) if _smiles else {"in_atom_1based": None, "out_atom_1based": None},
        "template_swap_rule": "A curated SDF may replace the generated attachment-fragment template only when the same explicit chemistry is preserved.",
        "curation_status": curation_status,
        "buildable": bool(_smiles) and template_available,
    }
    if chemistry:
        rec["chemistry"] = chemistry
    TEMPLATE_READY_REGISTRY[_tok] = rec

for _tok, _smiles in NON_NATURAL_UNITS.items():
    _meta = NON_NATURAL_CHEMISTRY_METADATA.get(_tok, {})
    _register_template(_tok, "non_natural_aa", _smiles, source=_meta.get("source", "explicit_residue_fragment"), curation_status="explicit_residue_graph", chemistry={"evidence_status": "explicit_residue_graph", **_meta})
for _tok, _smiles in LINKER_UNITS.items():
    _register_template(_tok, "linker", _smiles, source="database_or_explicit_linker_convention", curation_status="explicit_linear_linker_graph")
for _tok, _smiles in LABEL_UNITS.items():
    _register_template(_tok, "label", _smiles, source=LABEL_CHEMISTRY_METADATA[_tok]["source"], curation_status=LABEL_CHEMISTRY_METADATA[_tok]["evidence_status"], chemistry=LABEL_CHEMISTRY_METADATA[_tok])
for _tok in sorted(AMBIGUOUS_LABEL_TOKENS):
    _register_template(
        _tok, "label", None,
        source="token_recognized_but_derivative_unspecified",
        curation_status="requires_curated_derivative",
        template_available=False,
        chemistry=LABEL_CHEMISTRY_METADATA.get(_tok, {
            "evidence_status": "requires_curated_derivative",
            "attachment_chemistry": None,
            "structure_convention": None,
            "source": None,
        }),
    )
for _tok in sorted(CHEMICAL_TOKENS):
    if _tok in N_TERMINAL_ACYL_CHEM_CAPS:
        _register_template(_tok, "chemical", N_TERMINAL_ACYL_CHEM_CAPS[_tok], source="explicit_acyl_attachment_rule", curation_status="buildable_only_as_explicit_N_terminal_or_sidechain_acyl", chemistry={"attachment_chemistry": "acylation of primary amine", "evidence_status": "explicit_fragment_rule"})
    else:
        _register_template(_tok, "chemical", None, source="token_recognized_but_derivative_unspecified", curation_status="requires_curated_derivative", template_available=False, chemistry={"attachment_chemistry": None, "evidence_status": "requires_curated_derivative"})

def template_manifest() -> Dict[str, Any]:
    return {
        "version": VERSION,
        "template_mode": "chemistry_explicit_attachment_registry_v2",
        "important_limit": "Only tokens with explicit residue/linker/attachment chemistry are buildable. Recognized ambiguous labels/chemicals remain parseable but require a curated derivative instead of a fabricated structure.",
        "attach_point_rules": TEMPLATE_ATTACHMENT_RULES,
        "templates": TEMPLATE_READY_REGISTRY,
    }

def supported_token_table() -> Dict[str, Any]:
    """Return supported tokens grouped by Pepforge interpretation category."""
    return {
        "version": VERSION,
        "std_aa": sorted(STD_AA),
        "d_std_aa": sorted('d' + aa for aa in STD_AA),
        "non_natural_aa_buildable": sorted(NON_NATURAL_UNITS),
        "non_natural_aa_recognized_requires_curated_graph": sorted(RECOGNIZED_NON_NATURAL_TOKENS - set(NON_NATURAL_UNITS)),
        "linker_buildable": sorted(LINKER_UNITS),
        "linker_sequence_expansion": dict(sorted(SEQUENCE_LINKER_EXPANSIONS.items())),
        "linker_recognized_requires_curated_product": sorted(RECOGNIZED_LINKER_TOKENS - set(LINKER_UNITS) - set(SEQUENCE_LINKER_EXPANSIONS)),
        "label": sorted(LABEL_TOKENS),
        "chemical": sorted(CHEMICAL_TOKENS),
        "n_terminal": sorted(N_TERMINAL_CAPS),
        "c_terminal": sorted(C_TERMINAL_CAPS),
        "tag_expansion": sorted(TAG_EXPANSIONS),
        "aliases": dict(sorted(TOKEN_ALIASES.items())),
        "sidechain_acceptors": sorted(SIDECHAIN_ACCEPTORS),
        "fixed_rule": "STD remains 20 canonical residues. Only explicit residue/linker/attachment chemistry is buildable; ambiguous generic derivatives remain recognized but are not assigned fabricated 3D structures.",
        "template_registry": TEMPLATE_READY_REGISTRY,
        "template_manifest": template_manifest(),
    }

def environment_report() -> Dict[str, Any]:
    """Return a compact runtime report for PyMOL/standalone troubleshooting."""
    report: Dict[str, Any] = {
        "pepforge_version": VERSION,
        "rdkit_available": Chem is not None,
        "rdkit_import_error": str(_RDKIT_IMPORT_ERROR) if _RDKIT_IMPORT_ERROR else None,
        "supported_counts": {},
    }
    if Chem is not None:
        try:
            import rdkit
            report["rdkit_version"] = getattr(rdkit, "__version__", "unknown")
        except Exception:
            report["rdkit_version"] = "unknown"
    table = supported_token_table()
    for k in ["std_aa", "d_std_aa", "non_natural_aa", "linker", "label", "chemical", "n_terminal", "c_terminal", "tag_expansion", "aliases"]:
        report["supported_counts"][k] = len(table.get(k, {}))
    return report

def _chemistry_audit(mol, tokens: List[Token], smiles: str) -> Dict[str, Any]:
    """Lightweight sanity report for generated starting models."""
    audit: Dict[str, Any] = {
        "valid_molecule": mol is not None,
        "generated_smiles_parseable": bool(smiles),
        "connected_components": None,
        "formal_charge": None,
        "chiral_centers": [],
        "num_conformers": None,
        "sequence_like_token_count": sum(t.kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"} for t in tokens),
        "label_token_count": sum(t.kind == "label" for t in tokens),
        "linker_token_count": sum(t.kind == "linker" for t in tokens),
        "chemical_token_count": sum(t.kind == "chemical" for t in tokens),
    }
    if mol is None or Chem is None:
        return audit
    try:
        frags = Chem.GetMolFrags(mol)
        audit["connected_components"] = len(frags)
    except Exception:
        LOGGER.debug("Optional operation skipped", exc_info=True)
    try:
        audit["formal_charge"] = int(sum(a.GetFormalCharge() for a in mol.GetAtoms()))
    except Exception:
        LOGGER.debug("Optional operation skipped", exc_info=True)
    try:
        audit["chiral_centers"] = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    except Exception:
        LOGGER.debug("Optional operation skipped", exc_info=True)
    try:
        audit["num_conformers"] = int(mol.GetNumConformers())
    except Exception:
        LOGGER.debug("Optional operation skipped", exc_info=True)
    return audit

@dataclass
class Token:
    raw: str
    kind: str
    unit_smiles: Optional[str] = None
    note: str = ""
    expanded_from: Optional[str] = None
    heavy_atom_count: int = 0
    parent_residue: Optional[str] = None
    modification: Optional[str] = None

@dataclass
class AtomRange:
    token: str
    kind: str
    label: str
    heavy_start_1based: int
    heavy_end_1based: int
    note: str = ""

@dataclass
class BuildResult:
    input_text: str
    tokens: List[Token]
    smiles: str
    molblock: Optional[str]
    sdf_path: Optional[str]
    pdb_path: Optional[str]
    meta_path: Optional[str]
    report_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    exact_mw: Optional[float] = None
    heavy_atoms: Optional[int] = None
    atom_ranges: List[AtomRange] = field(default_factory=list)

class PepforgeBuildError(RuntimeError):
    """Raised when a peptide structure cannot be built safely."""

# -----------------------------------------------------------------------------
# Utility / parser
# -----------------------------------------------------------------------------
def _require_rdkit() -> None:
    if Chem is None:
        raise PepforgeBuildError(
            "RDKit is required for 3D structure generation but could not be imported. "
            f"Import error: {_RDKIT_IMPORT_ERROR}"
        )

def _heavy_count(smiles: Optional[str]) -> int:
    if not smiles or Chem is None:
        return 0
    m = Chem.MolFromSmiles(smiles)
    return m.GetNumHeavyAtoms() if m is not None else 0


def _global_attach_points_for_range(token: Token, atom_range: 'AtomRange') -> Dict[str, Any]:
    local = _infer_local_attach_points(token.unit_smiles, token.kind)
    out: Dict[str, Any] = {
        "token": token.raw,
        "kind": token.kind,
        "parent_residue": token.parent_residue,
        "modification": token.modification,
        "range_heavy_1based": [atom_range.heavy_start_1based, atom_range.heavy_end_1based],
        "local_in_atom_1based": local.get("in_atom_1based"),
        "local_out_atom_1based": local.get("out_atom_1based"),
        "global_in_atom_1based": None,
        "global_out_atom_1based": None,
        "role_note": "Attach-site hint based on token/template atom ranks. Use curated SDF + updated manifest for publication-grade geometry.",
    }
    if local.get("in_atom_1based"):
        out["global_in_atom_1based"] = atom_range.heavy_start_1based + int(local["in_atom_1based"]) - 1
    if local.get("out_atom_1based"):
        out["global_out_atom_1based"] = atom_range.heavy_start_1based + int(local["out_atom_1based"]) - 1
    return out


def _build_attach_point_map(tokens: List[Token], atom_ranges: List['AtomRange']) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for tok, ar in zip([t for t in tokens if t.kind != "c_terminal"], atom_ranges):
        if tok.kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa", "linker", "label", "chemical", "n_terminal"}:
            out.append(_global_attach_points_for_range(tok, ar))
    return out

def _strip_outer_brackets(piece: str) -> str:
    piece = piece.strip()
    if piece.startswith("[") and piece.endswith("]"):
        return piece[1:-1].strip()
    return piece

def _split_top_level(text: str) -> List[str]:
    text = text.strip().replace(" ", "")
    if not text:
        return []
    out, buf = [], ""
    bracket = 0
    paren = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "[":
            bracket += 1
            if bracket == 1:
                if buf:
                    out.append(buf); buf = ""
                i += 1; continue
        if ch == "]":
            bracket -= 1
            if bracket < 0: raise PepforgeBuildError("Unmatched ']' in sequence input.")
            if bracket == 0:
                out.append(buf); buf = ""
                i += 1; continue
        if bracket == 0:
            if ch == "(": paren += 1
            elif ch == ")":
                paren -= 1
                if paren < 0: raise PepforgeBuildError("Unmatched ')' in sequence input.")
            elif ch in "-|_" and paren == 0:
                if buf:
                    out.append(buf); buf = ""
                i += 1; continue
        buf += ch
        i += 1
    if bracket != 0: raise PepforgeBuildError("Unclosed '[' in sequence input.")
    if paren != 0: raise PepforgeBuildError("Unclosed '(' in sequence input.")
    if buf: out.append(buf)
    return [_strip_outer_brackets(x) for x in out if x]

_SIDECHAIN_RE = re.compile(r"^(d?[A-Z]|d?[A-Z][a-z]{2}|Aib|Nle|dNle|Orn|dOrn|Dab|dDab|Cit|dCit|Hyp|dHyp|Cha|dCha|Nal|dNal)\((.+)\)$")

def is_sidechain_token(piece: str) -> bool:
    return bool(_SIDECHAIN_RE.match(piece))

def _alias_key(tok: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(tok or "")).lower()

def _normalize_token(tok: str) -> str:
    if tok in TOKEN_ALIASES:
        return TOKEN_ALIASES[tok]
    key = _alias_key(tok)
    for alias, canonical in TOKEN_ALIASES.items():
        if _alias_key(alias) == key:
            return canonical
    return tok

def _normalize_sidechain_token(tok: str) -> str:
    m = _SIDECHAIN_RE.match(tok)
    if not m:
        return _normalize_token(tok)
    parent, mod = m.group(1), m.group(2)
    parts = [_normalize_token(x) for x in _split_top_level(mod.replace(",", "-"))]
    return f"{_normalize_token(parent)}({'-'.join(parts)})"

def _tokenize_piece(piece: str) -> List[str]:
    if not piece:
        return []
    if is_sidechain_token(piece):
        return [_normalize_sidechain_token(piece)]
    norm_piece = _normalize_token(piece)
    if norm_piece in SEQUENCE_LINKER_EXPANSIONS:
        return list(SEQUENCE_LINKER_EXPANSIONS[norm_piece])
    if norm_piece in KNOWN_MULTI_TOKENS or norm_piece in STD_AA:
        return [norm_piece]
    if piece.startswith("d") and len(piece) == 2 and piece[1] in STD_AA:
        return [piece]
    # A compact all-uppercase canonical sequence (e.g. ACG, EEMQRR) must be
    # split residue-by-residue before matching multi-letter chemistry tokens.
    # Otherwise prefixes such as ``Ac`` can incorrectly consume ``AC`` from ACG.
    tokens: List[str] = []
    i = 0
    while i < len(piece):
        # Side-chain modification inside a compact sequence, e.g. AK(FITC)LVFF
        m = re.match(r"(d?[A-Z]|Orn|Dab|Nle|Aib|Cit|Hyp|Cha|Nal)\(([^()]+)\)", piece[i:])
        if m:
            tokens.append(m.group(0)); i += len(m.group(0)); continue
        matched = None
        matched_len = 0
        for tok in KNOWN_MULTI_TOKENS:
            if piece[i:].lower().startswith(str(tok).lower()):
                matched = tok; matched_len = len(tok); break
        if not matched:
            compact_tail = re.sub(r"[^A-Za-z0-9]", "", piece[i:]).lower()
            for alias, canonical in sorted(TOKEN_ALIASES.items(), key=lambda kv: len(re.sub(r"[^A-Za-z0-9]", "", kv[0])), reverse=True):
                alias_key = _alias_key(alias)
                if compact_tail.startswith(alias_key):
                    matched = canonical; matched_len = len(alias_key); break
        if matched:
            tokens.append(matched); i += max(1, matched_len); continue
        if piece[i] == "d" and i + 1 < len(piece) and piece[i + 1] in STD_AA:
            tokens.append(piece[i:i+2]); i += 2; continue
        if piece[i] in STD_AA:
            tokens.append(piece[i]); i += 1; continue
        raise PepforgeBuildError(f"Unknown token near '{piece[i:]}' in '{piece}'. Use brackets for multi-letter tokens, e.g. [Aib] or K(FITC).")
    return tokens

def expand_and_tokenize(text: str) -> List[str]:
    raw_parts = _split_top_level(text)
    tokens: List[str] = []
    for part in raw_parts:
        if part in TAG_EXPANSIONS:
            for aa in TAG_EXPANSIONS[part]:
                tokens.append(aa)
        elif part in SEQUENCE_LINKER_EXPANSIONS:
            tokens.extend(SEQUENCE_LINKER_EXPANSIONS[part])
        else:
            tokens.extend(_tokenize_piece(part))
    return tokens

def _sidechain_linkage_smiles(parent: str, mods: str) -> str:
    """Build only explicitly defined side-chain covalent chemistry.

    K/Orn/Dab (and D counterparts) use the terminal primary amine.  Linear
    amino-acid linkers are attached through their carboxyl group and expose
    their terminal amine for the next defined label.  FITC uses a thiourea;
    Biotin/FAM use amides.  Acyl chemical tokens use an amide.  Cys is not
    given a generic linkage because the electrophile/linkage type is reagent
    dependent (maleimide, haloacetyl, disulfide, NBD substitution, etc.).
    """
    if parent not in SIDECHAIN_ACCEPTORS:
        raise PepforgeBuildError(f"Side-chain modification is currently recognized for {sorted(SIDECHAIN_ACCEPTORS)}, not '{parent}'.")
    parts = _split_top_level(mods.replace(",", "-"))
    if not parts:
        raise PepforgeBuildError("Empty side-chain modification.")

    is_d = parent.startswith("d")
    base = parent[1:] if is_d else parent
    chiral = "@H" if is_d else "@@H"
    if base == "C":
        raise PepforgeBuildError(
            f"'{parent}({mods})' requires an explicit Cys attachment chemistry. "
            "Pepforge will not invent a generic thioether/thiourea linkage; use a curated reagent/linkage definition."
        )
    if base not in {"K", "Orn", "Dab"}:
        raise PepforgeBuildError(f"Unsupported side-chain modification parent '{parent}'.")

    # Every intermediate part must be a linker.  The final part must be a
    # label with a defined amine reaction or an explicitly defined acyl token.
    if len(parts) > 1:
        for p in parts[:-1]:
            if p not in SIDECHAIN_AMINE_LINKER_FRAGMENTS:
                raise PepforgeBuildError(
                    f"Unsupported side-chain linker '{p}' in '{parent}({mods})'. "
                    "Only linkers with an explicit parent-amine -> linker-amine graph are buildable."
                )
    terminal = parts[-1]
    outward = "".join(SIDECHAIN_AMINE_LINKER_FRAGMENTS[p] for p in parts[:-1])
    if terminal in SIDECHAIN_AMINE_LABEL_SUBSTITUENTS:
        outward += SIDECHAIN_AMINE_LABEL_SUBSTITUENTS[terminal]
    elif terminal in AMBIGUOUS_LABEL_TOKENS:
        raise PepforgeBuildError(
            f"Label '{terminal}' does not identify one unique peptide-bound derivative. "
            "A curated derivative/attachment rule is required; no surrogate structure is generated."
        )
    elif terminal in SIDECHAIN_ACYL_TAILS:
        outward += "C(=O)" + SIDECHAIN_ACYL_TAILS[terminal]
    elif terminal in AMBIGUOUS_CHEMICAL_TOKENS:
        raise PepforgeBuildError(
            f"Chemical token '{terminal}' does not define a unique side-chain attachment. "
            "A curated derivative is required; no generic linkage is generated."
        )
    elif terminal in LINKER_UNITS:
        # A linker-only side-chain modification is allowed: it terminates in
        # the linker's free primary amine.
        outward += SIDECHAIN_AMINE_LINKER_FRAGMENTS[terminal]
    else:
        raise PepforgeBuildError(
            f"Unsupported side-chain modification '{terminal}' in '{parent}({mods})'. "
            "Use an explicitly supported linker/label/acyl chemistry."
        )

    sidechain = {"K": "CCCCN", "Orn": "CCCN", "Dab": "CCN"}[base]
    return f"N[C{chiral}]({sidechain}{outward})C(=O)"

def classify_token(tok: str) -> Token:
    sm = _SIDECHAIN_RE.match(tok)
    if sm:
        parent, mod = sm.group(1), sm.group(2)
        unit = _sidechain_linkage_smiles(parent, mod)
        return Token(tok, "sidechain_label_aa", unit, note=f"side-chain modification on {parent}; modification is not sequence residue", heavy_atom_count=_heavy_count(unit), parent_residue=parent, modification=mod)
    if tok in N_TERMINAL_CAPS:
        return Token(tok, "n_terminal", N_TERMINAL_CAPS[tok], heavy_atom_count=_heavy_count(N_TERMINAL_CAPS[tok]))
    if tok in C_TERMINAL_CAPS:
        return Token(tok, "c_terminal", None, heavy_atom_count=0)
    if tok.startswith("d") and len(tok) == 2 and tok[1] in D_RESIDUE_UNITS:
        smi = D_RESIDUE_UNITS[tok[1]]
        return Token(tok, "d_std_aa", smi, heavy_atom_count=_heavy_count(smi))
    if tok in L_RESIDUE_UNITS:
        smi = L_RESIDUE_UNITS[tok]
        return Token(tok, "std_aa", smi, heavy_atom_count=_heavy_count(smi))
    if tok in RECOGNIZED_NON_NATURAL_TOKENS:
        smi = NON_NATURAL_UNITS.get(tok)
        meta = NON_NATURAL_CHEMISTRY_METADATA.get(tok, {})
        note = f"explicit structure convention: {meta.get('structure_convention', tok)}" if smi else "recognized non-natural amino acid; curated stereochemistry/monomer graph required for 3D build"
        return Token(tok, "non_natural_aa", smi, note=note, heavy_atom_count=_heavy_count(smi))
    if tok in RECOGNIZED_LINKER_TOKENS:
        smi = LINKER_UNITS.get(tok)
        note = "explicit linker graph; not counted as STD peptide residue" if smi else "recognized linker/crosslink chemistry; exact attached-product graph required for 3D build"
        return Token(tok, "linker", smi, note=note, heavy_atom_count=_heavy_count(smi))
    if tok in LABEL_TOKENS:
        smi = LABEL_UNITS.get(tok)
        meta = LABEL_CHEMISTRY_METADATA.get(tok, {})
        convention = meta.get("structure_convention")
        note = "label/modification; not a peptide residue"
        if convention:
            note += f"; explicit structure convention: {convention}"
        else:
            note += "; exact derivative/attachment is not specified by this token"
        return Token(tok, "label", smi, note=note, heavy_atom_count=_heavy_count(smi))
    if tok in CHEMICAL_TOKENS:
        smi = N_TERMINAL_ACYL_CHEM_CAPS.get(tok)
        note = "chemical modification; explicit acyl placement required" if smi else "chemical token recognized; curated derivative/attachment required"
        return Token(tok, "chemical", smi, note=note, heavy_atom_count=_heavy_count(smi))
    raise PepforgeBuildError(f"Unsupported token: {tok}")

# -----------------------------------------------------------------------------
# Validation / building
# -----------------------------------------------------------------------------
def validate_tokens(tokens: List[Token]) -> List[str]:
    warnings: List[str] = []
    # Leading Pal/Myr/Ste/Lau are intentional N-terminal acyl caps and should
    # not be warned as free terminal labels. Other labels/chemicals still get
    # conservative linker/placement warnings.
    for i, t in enumerate(tokens[:-1]):
        # Explicit N-terminal label/acyl conventions are valid immediately
        # before a linker or peptide residue and do not need a warning merely
        # because no spacer was supplied.
        if i == 0 and t.kind == "label" and t.raw in LABEL_UNITS:
            continue
        if i == 0 and t.kind == "chemical" and t.raw in N_TERMINAL_ACYL_CHEM_CAPS:
            continue
        if t.kind == "linker" and tokens[i+1].kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"}:
            # Linear N->C linker placement is explicitly represented by the
            # linker graph, so no chemistry-warning is needed here.
            continue
        if t.kind in {"label", "chemical"} and tokens[i+1].kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"}:
            warnings.append(f"Modification '{t.raw}' appears in a non-leading position. Exact attachment chemistry is required.")
    for i, t in enumerate(tokens):
        if t.kind == "n_terminal" and any(x.kind in {"std_aa","d_std_aa","non_natural_aa","sidechain_label_aa","linker","label"} for x in tokens[:i]):
            warnings.append(f"N-terminal cap '{t.raw}' appears after buildable units; chemistry may not match intent.")
        if t.kind == "c_terminal" and i != len(tokens)-1:
            warnings.append(f"C-terminal cap '{t.raw}' appears before the end; treated as terminal annotation.")
    if len([t for t in tokens if t.kind == "n_terminal"]) > 1:
        warnings.append("Multiple N-terminal caps were supplied; first one is used for chemistry.")
    if len([t for t in tokens if t.kind == "c_terminal"]) > 1:
        warnings.append("Multiple C-terminal caps were supplied; last one is used.")
    return warnings

def tokens_to_smiles(tokens_raw: List[str]) -> Tuple[str, List[Token], List[str], List[AtomRange]]:
    if not tokens_raw:
        raise PepforgeBuildError("Empty sequence input.")
    tokens = [classify_token(t) for t in tokens_raw]
    warnings: List[str] = validate_tokens(tokens)
    atom_ranges: List[AtomRange] = []

    ncap = ""
    ncap_token: Optional[Token] = None
    cterm = "OH"
    chain_units: List[Token] = []
    seen_sequence_like = False

    for tok in tokens:
        if tok.kind == "n_terminal":
            if seen_sequence_like:
                warnings.append(f"N-terminal cap '{tok.raw}' appeared after sequence start; ignored as chemistry in v1.3.")
            elif ncap:
                warnings.append(f"Multiple N-terminal caps found; using first cap and ignoring '{tok.raw}'.")
            else:
                ncap = tok.unit_smiles or ""; ncap_token = tok
            continue
        if tok.kind == "c_terminal":
            cterm = tok.raw
            continue

        # v2.0.0 hotfix:
        # Leading lipid chemical tokens such as Pal/Myr/Ste/Lau are N-terminal
        # acyl caps, not sequence/label units. This prevents Pal-dG-dH-dK-NH2
        # from being built as an amino-palmitoyl-like fragment and keeps the
        # C-terminal NH2 as a real amide atom.
        if tok.kind == "chemical" and tok.raw in N_TERMINAL_ACYL_CHEM_CAPS and not seen_sequence_like and not chain_units:
            if ncap:
                raise PepforgeBuildError(
                    f"N-terminal acyl token '{tok.raw}' cannot be combined with the existing N-terminal cap "
                    f"'{ncap_token.raw if ncap_token else 'N-cap'}' without an explicit dual-modification linkage rule."
                )
            ncap = N_TERMINAL_ACYL_CHEM_CAPS[tok.raw]
            ncap_token = Token(tok.raw, "n_terminal", ncap, note=f"explicit N-terminal {tok.raw} acyl cap", heavy_atom_count=_heavy_count(ncap))
            continue

        if tok.kind == "label":
            if tok.unit_smiles is None:
                raise PepforgeBuildError(
                    f"Label '{tok.raw}' is recognized, but that name does not define one unique peptide-bound derivative. "
                    "A curated derivative/attachment rule is required; Pepforge will not fabricate a 3D structure."
                )
            if chain_units or seen_sequence_like:
                raise PepforgeBuildError(
                    f"Free label token '{tok.raw}' is only buildable as the N-terminal label in the current explicit chemistry model. "
                    f"For residue labeling use side-chain notation such as K({tok.raw}) when that linkage is defined."
                )
            if ncap:
                raise PepforgeBuildError(
                    f"N-terminal label '{tok.raw}' cannot be combined with the existing N-terminal cap '{ncap_token.raw if ncap_token else 'N-cap'}' without an explicit linkage rule."
                )
            meta = LABEL_CHEMISTRY_METADATA.get(tok.raw, {})
            if meta.get("structure_convention") in {"5-FITC", "5-FAM"}:
                warnings.append(
                    f"Token '{tok.raw}' uses Pepforge's explicit {meta['structure_convention']} structure convention. "
                    "If the experimental reagent is another regioisomer or a mixed-isomer product, supply/use a curated derivative instead."
                )
            chain_units.append(tok)
            continue
        if tok.kind == "chemical":
            # Explicit N-terminal acyl chemicals were handled above.  Any
            # remaining chemical token lacks a unique generic covalent graph.
            if tok.raw in N_TERMINAL_ACYL_CHEM_CAPS:
                raise PepforgeBuildError(
                    f"Chemical acyl token '{tok.raw}' is only buildable at the N-terminus or through explicit side-chain amide notation (for example K({tok.raw}))."
                )
            raise PepforgeBuildError(
                f"Chemical token '{tok.raw}' is recognized but does not define one unique peptide attachment. "
                "A curated derivative/attachment rule is required; no display-only surrogate is generated."
            )
        if tok.kind == "linker":
            if tok.unit_smiles is None:
                raise PepforgeBuildError(
                    f"Linker '{tok.raw}' is recognized, but the token does not define one unique peptide-bound product. "
                    "Choose an explicit amino/PEG linker or provide curated attachment chemistry."
                )
            seen_sequence_like = True
            chain_units.append(tok)
            continue
        if tok.kind in {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"}:
            if tok.unit_smiles is None:
                raise PepforgeBuildError(
                    f"Non-natural amino acid '{tok.raw}' is recognized, but PSB has no curated stereochemical monomer graph for it. "
                    "No canonical-amino-acid surrogate is generated."
                )
            seen_sequence_like = True
            chain_units.append(tok)
            continue

    if not chain_units:
        raise PepforgeBuildError("No buildable peptide/linker/label units found.")

    smiles_parts: List[str] = []
    cursor = 1
    if ncap:
        smiles_parts.append(ncap)
        n = _heavy_count(ncap)
        atom_ranges.append(AtomRange(ncap_token.raw if ncap_token else "Ncap", "n_terminal", KIND_LABELS["n_terminal"], cursor, cursor + n - 1, ncap_token.note if ncap_token else ""))
        cursor += n

    for tok in chain_units:
        smiles_parts.append(tok.unit_smiles or "")
        n = tok.heavy_atom_count or _heavy_count(tok.unit_smiles)
        atom_ranges.append(AtomRange(tok.raw, tok.kind, KIND_LABELS.get(tok.kind, tok.kind), cursor, cursor + n - 1, tok.note))
        cursor += n

    # Materialize the requested C-terminal cap.  Generic C-terminal label
    # attachment is deliberately not fabricated; labels must use an explicit
    # N-terminal or side-chain rule above.
    terminal_atom = "N" if cterm == "NH2" else "O"
    smiles_parts.append(terminal_atom)
    atom_ranges.append(AtomRange(cterm, "c_terminal_atom", KIND_LABELS["c_terminal"], cursor, cursor, "terminal atom added to last carbonyl"))
    cursor += 1

    return "".join(smiles_parts), tokens, warnings, atom_ranges

def _add_mol_properties(mol, sequence: str, tokens: List[Token], atom_ranges: List[AtomRange], warnings: List[str], name: str) -> None:
    mol.SetProp("_Name", name)
    mol.SetProp("Pepforge_Version", VERSION)
    mol.SetProp("Pepforge_Input", sequence)
    mol.SetProp("Pepforge_Tokens", "|".join(t.raw for t in tokens))
    mol.SetProp("Pepforge_Token_Kinds", "|".join(t.kind for t in tokens))
    mol.SetProp("Pepforge_Atom_Ranges", json.dumps([asdict(r) for r in atom_ranges], ensure_ascii=False))
    mol.SetProp("Pepforge_Warnings", " | ".join(warnings))
    mol.SetProp("Pepforge_Notice", "Labels are modifications, not peptide sequence residues. Linkers are spacer units, not STD residues.")

def audit_template_files(base_dir: str | Path | None = None) -> Dict[str, Any]:
    """Audit only templates that are actually advertised as available.

    Recognized tokens that require a curated derivative are reported as
    ``unavailable_by_design`` rather than as missing files.  This distinction
    prevents an absent/ambiguous chemistry definition from being disguised by
    a generated display-only SDF.
    """
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parents[1]
    records: List[Dict[str, Any]] = []
    ok = missing = unreadable = unavailable = 0
    for tok, rec in sorted(TEMPLATE_READY_REGISTRY.items()):
        rel = rec.get("template_file")
        row = dict(rec)
        row["template_formula"] = None
        row["template_heavy_atoms"] = None
        if not rel:
            unavailable += 1
            row["template_abs_path"] = None
            row["exists"] = False
            row["readable_by_rdkit"] = False
            row["audit_status"] = "unavailable_by_design_requires_curated_derivative"
            records.append(row)
            continue
        path = base / str(rel)
        row["template_abs_path"] = str(path)
        row["exists"] = path.exists()
        row["readable_by_rdkit"] = False
        if not path.exists():
            missing += 1
            row["audit_status"] = "missing_expected_template"
        elif Chem is None:
            unreadable += 1
            row["audit_status"] = "rdkit_unavailable"
            row["read_error"] = "RDKit not available"
        else:
            try:
                suppl = Chem.SDMolSupplier(str(path), removeHs=False)
                mol = suppl[0] if len(suppl) else None
                if mol is None:
                    unreadable += 1
                    row["audit_status"] = "unreadable"
                    row["read_error"] = "RDKit returned None"
                else:
                    ok += 1
                    row["audit_status"] = "ok"
                    row["readable_by_rdkit"] = True
                    row["template_formula"] = rdMolDescriptors.CalcMolFormula(mol)
                    row["template_heavy_atoms"] = int(mol.GetNumHeavyAtoms())
            except Exception as exc:
                unreadable += 1
                row["audit_status"] = "unreadable"
                row["read_error"] = str(exc)
        records.append(row)
    return {
        "version": VERSION,
        "template_mode": "chemistry_explicit_attachment_registry_v2",
        "summary": {
            "total": len(records), "ok": ok, "missing": missing,
            "unreadable": unreadable, "unavailable_by_design": unavailable,
        },
        "records": records,
    }


def _template_audit_for_tokens(tokens: List[Token], base_dir: str | Path | None = None) -> List[Dict[str, Any]]:
    full = audit_template_files(base_dir)
    by_token = {r.get("token"): r for r in full.get("records", [])}
    out = []
    for t in tokens:
        out.append(by_token.get(t.raw, {"token": t.raw, "category": t.kind, "source": "inline_or_terminal", "exists": None, "readable_by_rdkit": None}))
    return out

def make_report(meta: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Pepforge PyMOL Structure Tool v{meta.get('version')} report")
    lines.append("=" * 64)
    lines.append(f"Input: {meta.get('input')}")
    lines.append(f"Formula: {meta.get('formula')}")
    lines.append(f"Exact MW: {meta.get('exact_mw')}")
    lines.append(f"Heavy atoms: {meta.get('heavy_atoms')}")
    lines.append("")
    lines.append("Category counts:")
    for k, v in sorted((meta.get('category_counts') or {}).items()):
        lines.append(f"  - {k}: {v}")
    lines.append("")
    lines.append("Token / atom-range map:")
    for r in meta.get('atom_ranges', []):
        lines.append(f"  - {r.get('token'):>16s} | {r.get('kind'):<18s} | heavy rank {r.get('heavy_start_1based')}-{r.get('heavy_end_1based')} | {r.get('note','')}")
    lines.append("")
    lines.append("Attach-point map:")
    for ap in meta.get('attach_point_map', []):
        lines.append(f"  - {ap.get('token'):>16s} | {ap.get('kind'):<18s} | IN global {ap.get('global_in_atom_1based')} | OUT global {ap.get('global_out_atom_1based')}")
    lines.append("")
    lines.append("Chemistry audit:")
    audit = meta.get('chemistry_audit') or {}
    for k, v in audit.items():
        lines.append(f"  - {k}: {v}")
    lines.append("")
    lines.append("Conformer summary:")
    conf = meta.get('conformer_summary') or {}
    for k, v in conf.items():
        if k == 'energies':
            lines.append(f"  - energies: {len(v)} conformer record(s)")
        else:
            lines.append(f"  - {k}: {v}")
    lines.append("")
    lines.append("Conformational-family analysis:")
    ca = meta.get('conformation_analysis') or {}
    lines.append(f"  - status: {ca.get('status', 'unavailable')}")
    lines.append(f"  - method: {ca.get('method', '')}")
    lines.append(f"  - family_counts: {ca.get('family_counts', {})}")
    lines.append(f"  - claim_guard: {ca.get('claim_guard', '')}")
    lines.append("")
    lines.append("Sequence-aware top-five conformers:")
    lines.append(f"  - ranking_method: {ca.get('ranking_method', '')}")
    for row in ca.get('top_conformers', []) or []:
        lines.append(
            f"  - rank {row.get('rank')}: {row.get('family')} | "
            f"role={row.get('candidate_role')} | "
            f"sequence_support={row.get('sequence_support')} | "
            f"within-molecule energy={row.get('energy')} | {row.get('selection_reason', '')}"
        )
    seq_ev = meta.get('sequence_conformation_evidence') or {}
    lines.append("Sequence evidence summary:")
    lines.append(f"  - canonical-L coverage: {seq_ev.get('canonical_L_coverage_fraction', 0.0)}")
    lines.append(f"  - helix breakers: {seq_ev.get('helix_breaker_positions', [])}")
    lines.append(f"  - opposite-charge i,i+3/i+4 pairs: {seq_ev.get('opposite_charge_i3_i4_pairs', [])}")
    lines.append(f"  - beta-hairpin context windows: {seq_ev.get('beta_hairpin_context_windows', [])}")
    lines.append(f"  - PPII proline positions: {seq_ev.get('proline_positions_for_PPII_context', [])}")
    lines.append(f"  - claim_guard: {seq_ev.get('claim_guard', '')}")
    lit = seq_ev.get('literature_sequence_screen') or {}
    lines.append("Literature-derived sequence design screen:")
    lines.append(f"  - alpha/beta/gamma backbone: {lit.get('alpha_beta_gamma_peptidomimetic', {})}")
    lines.append(f"  - amphipathic alpha-helix: {lit.get('amphipathic_alpha_helix', {})}")
    lines.append(f"  - coiled-coil heptad: {lit.get('coiled_coil_heptad_compatibility', {})}")
    lines.append(f"  - beta alternation: {lit.get('beta_strand_alternation', {})}")
    lines.append(f"  - turn/hairpin motifs: {lit.get('turn_and_hairpin_motifs', {})}")
    lines.append(f"  - aggregation screen: {lit.get('aggregation_screen', {})}")
    lines.append(f"  - SPPS difficult-sequence screen: {lit.get('spps_difficult_sequence_screen', {})}")
    lines.append(f"  - chemical liabilities: {lit.get('chemical_liability_screen', {})}")
    lines.append(f"  - cysteine topology: {lit.get('cysteine_topology', {})}")
    lines.append(f"  - claim_guard: {lit.get('claim_guard', '')}")
    he = meta.get('canonical_L_helix_evidence') or {}
    lines.append("Canonical-L alpha-helix evidence (Pace-Scholtz 1998):")
    lines.append(f"  - evidence coverage: {he.get('supported_residues', 0)}/{he.get('peptide_like_residues', 0)}")
    lines.append(f"  - mean delta-delta-G kcal/mol: {he.get('mean_ddg_kcal_mol')}")
    lines.append(f"  - interpretation: {he.get('interpretation', '')}")
    if he.get('unsupported_or_noncanonical'):
        lines.append(f"  - unsupported/noncanonical: {[x.get('token') for x in he.get('unsupported_or_noncanonical', [])]}")
    lines.append("")
    lines.append("Template mode:")
    lines.append(f"  - {meta.get('template_mode')}")
    lines.append(f"  - {meta.get('template_registry_notice')}")
    ta = meta.get('template_audit') or []
    if ta:
        lines.append("Template audit:")
        for rec in ta:
            token = rec.get('token')
            category = rec.get('category')
            source = rec.get('source')
            curation = rec.get('curation_status', '')
            template_file = rec.get('template_file', '')
            lines.append(f"  - {token}: {category} | {source} | {template_file} | {curation}")
    lines.append("")
    lines.append("Warnings:")
    ws = meta.get('warnings') or []
    if ws:
        for w in ws: lines.append(f"  - {w}")
    else:
        lines.append("  - none")
    lines.append("")
    lines.append("Fixed interpretation rule:")
    lines.append("  Biotin/FITC/FAM are labels, not peptide residues; FITC and FAM use explicit 5-isomer conventions and are reported as such.")
    lines.append("  TAMRA/Cy5/NBD/DOTA and ambiguous Chol/Mal/Dde derivatives are recognized but require curated attachment chemistry before 3D construction.")
    lines.append("  Ahx/AEEA/PEG4/PEG8/bAla/gAla are explicit linker conventions, not STD residues.")
    lines.append("  Leading Pal/Myr/Ste/Lau/Gal/Caf/Nic are explicit N-terminal acyl caps; the same acyl set may be used through defined side-chain amide notation.")
    lines.append("  Generic Cys labeling chemistry is not inferred. C-terminal NH2 is materialized as an amide atom.")
    lines.append("  STD AA remains the 20 canonical amino acids; dX means D-form where X is canonical.")
    return "\n".join(lines) + "\n"


def _energy_for_conformer(mol, conf_id: int = 0) -> Optional[float]:
    """Return approximate force-field energy for an embedded conformer."""
    if Chem is None or AllChem is None or mol is None:
        return None
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            props = AllChem.MMFFGetMoleculeProperties(mol)
            ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=int(conf_id))
        else:
            ff = AllChem.UFFGetMoleculeForceField(mol, confId=int(conf_id))
        return float(ff.CalcEnergy()) if ff is not None else None
    except Exception:
        return None


def _optimize_conformers(mol, conf_ids: List[int], max_iters: int, warnings: List[str], num_threads: int = 2) -> Dict[str, Any]:
    """Optimize conformers and return best conformer/energy summary."""
    summary: Dict[str, Any] = {
        "requested_conformers": len(conf_ids),
        "embedded_conformers": len(conf_ids),
        "best_conf_id": None,
        "best_energy": None,
        "energy_unit": "RDKit force-field arbitrary/mol units; compare within same molecule only",
        "method": None,
        "energies": [],
    }
    if not conf_ids:
        return summary
    use_mmff = False
    try:
        use_mmff = bool(AllChem.MMFFHasAllMoleculeParams(mol))
    except Exception:
        use_mmff = False
    summary["method"] = "MMFF94" if use_mmff else "UFF"
    if not use_mmff:
        warnings.append("MMFF parameters incomplete; using UFF optimization/energy ranking.")
    try:
        if use_mmff:
            results = AllChem.MMFFOptimizeMoleculeConfs(mol, maxIters=int(max_iters), numThreads=max(1, int(num_threads)))
        else:
            results = AllChem.UFFOptimizeMoleculeConfs(mol, maxIters=int(max_iters), numThreads=max(1, int(num_threads)))
        for conf_id, result in zip(conf_ids, results):
            not_converged, energy = result
            if int(not_converged) != 0:
                warnings.append(f"Conformer {conf_id} did not fully converge within max iterations.")
            summary["energies"].append({"conf_id": int(conf_id), "energy": float(energy), "not_converged": int(not_converged)})
    except Exception as exc:
        warnings.append(f"Conformer optimization warning: {exc}")
        for conf_id in conf_ids:
            summary["energies"].append({"conf_id": int(conf_id), "energy": _energy_for_conformer(mol, conf_id), "not_converged": None})
    valid = [e for e in summary["energies"] if e.get("energy") is not None]
    if valid:
        best = min(valid, key=lambda x: x["energy"])
        summary["best_conf_id"] = int(best["conf_id"])
        summary["best_energy"] = float(best["energy"])
    return summary


def _copy_best_conformer_only(mol, best_conf_id: Optional[int]):
    """Return a molecule retaining only the best conformer for cleaner SDF/PDB export."""
    if best_conf_id is None:
        return mol
    try:
        new = Chem.Mol(mol)
        conf = mol.GetConformer(int(best_conf_id))
        new.RemoveAllConformers()
        new.AddConformer(conf, assignId=True)
        return new
    except Exception:
        return mol


def _append_conformers_until(
    mol,
    minimum_count: int,
    seed: int,
    num_threads: int,
    max_retries: int,
    warnings: List[str],
) -> Tuple[List[int], List[Dict[str, Any]]]:
    """Adaptively append real conformers until the public Top-5 contract is met."""
    new_ids: List[int] = []
    attempts: List[Dict[str, Any]] = []
    for attempt in range(max(0, int(max_retries))):
        before = int(mol.GetNumConformers())
        if before >= int(minimum_count):
            break
        params = AllChem.ETKDGv3()
        params.randomSeed = int(seed) + 1009 * (attempt + 1)
        params.enforceChirality = True
        params.useSmallRingTorsions = True
        params.useMacrocycleTorsions = True
        params.useRandomCoords = attempt > 0
        params.pruneRmsThresh = -1.0
        try:
            params.clearConfs = False
            params.numThreads = max(1, int(num_threads))
        except AttributeError:
            pass
        requested = max(1, int(minimum_count) - before)
        try:
            created = [int(cid) for cid in AllChem.EmbedMultipleConfs(mol, numConfs=requested, params=params)]
        except Exception as exc:
            created = []
            warnings.append(f"Adaptive conformer retry {attempt + 1} warning: {exc}")
        new_ids.extend(created)
        attempts.append({
            "attempt": attempt + 1,
            "requested": requested,
            "created": len(created),
            "random_coordinates": bool(params.useRandomCoords),
            "conformer_count_after": int(mol.GetNumConformers()),
        })
    return new_ids, attempts


def _optimize_added_conformers(
    mol,
    conf_ids: List[int],
    max_iters: int,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for cid in conf_ids:
        not_converged = None
        try:
            if AllChem.MMFFHasAllMoleculeParams(mol):
                not_converged = int(AllChem.MMFFOptimizeMolecule(mol, confId=int(cid), maxIters=int(max_iters)))
            else:
                not_converged = int(AllChem.UFFOptimizeMolecule(mol, confId=int(cid), maxIters=int(max_iters)))
        except Exception as exc:
            warnings.append(f"Adaptive conformer {cid} optimization warning: {exc}")
        records.append({
            "conf_id": int(cid),
            "energy": _energy_for_conformer(mol, int(cid)),
            "not_converged": not_converged,
            "source": "adaptive_top5_retry",
        })
    return records

def build_structure(
    sequence: str,
    output_dir: str | Path = ".",
    name: str = "pepforge_structure",
    seed: int = 61453,
    optimize: bool = True,
    max_iters: int = 200,
    num_confs: int = 8,
    num_threads: int = 2,
    keep_all_confs: bool = False,
    environment_conditions: Optional[Dict[str, Any]] = None,
    search_profile: str = "evidence_fast",
    min_final_conformers: int = 5,
    max_embedding_retries: int = 2,
) -> BuildResult:
    _require_rdkit()
    outdir = Path(output_dir); outdir.mkdir(parents=True, exist_ok=True)
    raw_tokens = expand_and_tokenize(sequence)
    smiles, tokens, warnings, atom_ranges = tokens_to_smiles(raw_tokens)

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise PepforgeBuildError(f"RDKit failed to parse generated SMILES: {smiles}")
    _add_mol_properties(mol, sequence, tokens, atom_ranges, warnings, name)

    mol_h = Chem.AddHs(mol, addCoords=True)
    _add_mol_properties(mol_h, sequence, tokens, atom_ranges, warnings, name)

    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    params.useSmallRingTorsions = True
    params.useMacrocycleTorsions = True
    params.enforceChirality = True
    try:
        params.numThreads = max(1, int(num_threads))
    except AttributeError:
        pass
    try:
        params.pruneRmsThresh = 0.5
    except Exception:
        LOGGER.debug("Optional operation skipped", exc_info=True)
    requested_confs = max(1, int(num_confs or 1))
    conf_ids = list(AllChem.EmbedMultipleConfs(mol_h, numConfs=requested_confs, params=params))
    if not conf_ids:
        warnings.append("ETKDG multi-conformer embedding failed; retrying one conformer with random coordinates.")
        params.useRandomCoords = True
        conf_id = AllChem.EmbedMolecule(mol_h, params)
        if conf_id < 0:
            raise PepforgeBuildError("RDKit could not generate a 3D conformer for this input.")
        conf_ids = [int(conf_id)]

    conformer_summary = {
        "requested_conformers": requested_confs,
        "embedded_conformers": len(conf_ids),
        "best_conf_id": int(conf_ids[0]) if conf_ids else None,
        "best_energy": None,
        "energy_unit": "not optimized",
        "method": "ETKDG only",
        "energies": [],
    }
    if optimize:
        conformer_summary = _optimize_conformers(mol_h, conf_ids, max_iters, warnings, num_threads=num_threads)
    conformer_summary["worker_threads"] = max(1, int(num_threads))
    conformer_summary["max_optimization_iterations"] = int(max_iters)

    # v2.0.0 peptide-conformation upgrade: evaluate the stochastic ETKDG
    # ensemble plus explicit canonical-L backbone-basin seeds. This prevents a
    # short run from accidentally missing alpha/3_10/beta/PPII search regions.
    # Seeds are search candidates, not predictions, and are never forced onto
    # D/non-natural/side-chain-modified peptides.
    seed_sources = add_canonical_l_backbone_seed_conformers(mol_h, atom_ranges)
    if seed_sources:
        for cid, label in seed_sources.items():
            conformer_summary.setdefault("energies", []).append({
                "conf_id": int(cid),
                "energy": _energy_for_conformer(mol_h, int(cid)),
                "not_converged": None,
                "source": label,
                "note": "torsion-basin seed; not force-field optimized after torsion steering",
            })
        conformer_summary["backbone_seed_conformers"] = seed_sources
        conformer_summary["embedded_conformers"] = int(mol_h.GetNumConformers())

    required_final = max(1, int(min_final_conformers))
    added_ids, retry_attempts = _append_conformers_until(
        mol_h, required_final, int(seed), int(num_threads), int(max_embedding_retries), warnings
    )
    conformer_summary.setdefault("energies", []).extend(
        _optimize_added_conformers(mol_h, added_ids, max(20, int(max_iters)), warnings)
    )
    conformer_summary["adaptive_embedding_attempts"] = retry_attempts
    conformer_summary["minimum_final_conformers"] = required_final
    conformer_summary["embedded_conformers"] = int(mol_h.GetNumConformers())
    if int(mol_h.GetNumConformers()) < required_final:
        raise PepforgeBuildError(
            f"PSB could generate only {mol_h.GetNumConformers()} distinct coordinate candidates; "
            f"the requested exact Top {required_final} contract was not met."
        )

    conformer_sources = {int(cid): label for cid, label in seed_sources.items()}
    conformer_sources.update({int(cid): "adaptive_top5_retry" for cid in added_ids})
    conformation_analysis = analyze_conformer_ensemble(
        mol_h, atom_ranges, conformer_summary.get("energies", []), conformer_sources=conformer_sources
    )
    helix_evidence = canonical_l_helix_evidence(tokens)
    sequence_evidence = sequence_conformation_evidence(tokens)
    family_plan = evidence_guided_family_plan(sequence_evidence, search_profile)
    rmsd_matrix = pairwise_conformer_rmsd(mol_h)
    top_conformers = select_top_conformers(
        conformation_analysis, sequence_evidence, limit=required_final,
        pairwise_rmsd=rmsd_matrix,
        minimum_rmsd_A=float((family_plan.get("budget") or {}).get("rmsd_threshold_A", 1.0)),
        family_priority=list(family_plan.get("family_priority") or []),
    )
    if len(top_conformers) != required_final:
        raise PepforgeBuildError(
            f"PSB generated {mol_h.GetNumConformers()} coordinate candidates but could rank only "
            f"{len(top_conformers)} of the required {required_final}; inspect backbone resolution."
        )
    conformation_analysis["top_conformers"] = top_conformers
    conformation_analysis["top_conformer_limit"] = required_final
    conformation_analysis["ranking_method"] = (
        "family-diverse ordinal selection: sequence-supported families first, "
        "then contextual families, with a 1.0 A symmetry-aware heavy-atom RMSD diversity filter; "
        "within-molecule force-field energy is used only as a tie-breaker"
    )
    conformation_analysis["rmsd_diversity_threshold_A"] = 1.0

    selected_best_id = top_conformers[0].get("conf_id") if top_conformers else conformer_summary.get("best_conf_id")
    conformer_summary["best_conf_id_by_sequence_aware_selection"] = selected_best_id
    mol_export = mol_h if keep_all_confs else _copy_best_conformer_only(mol_h, selected_best_id)
    _add_mol_properties(mol_export, sequence, tokens, atom_ranges, warnings, name)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "pepforge_structure"
    sdf_path = outdir / f"{safe}.sdf"
    pdb_path = outdir / f"{safe}.pdb"
    meta_path = outdir / f"{safe}.json"
    report_path = outdir / f"{safe}_report.txt"
    ensemble_sdf_path = outdir / f"{safe}_conformer_ensemble.sdf"
    family_csv_path = outdir / f"{safe}_conformer_families.csv"
    torsion_csv_path = outdir / f"{safe}_backbone_torsions.csv"
    top5_sdf_path = outdir / f"{safe}_top5_conformers.sdf"
    top5_csv_path = outdir / f"{safe}_top5_conformers.csv"

    # Preserve the full sampled ensemble as a separate SDF. The primary SDF/PDB
    # remains the lowest-force-field-energy representative for compatibility.
    top5_pdb_paths = []
    try:
        ensemble_writer = Chem.SDWriter(str(ensemble_sdf_path))
        if ensemble_writer is None:
            raise OSError(f"RDKit SDWriter returned None for {ensemble_sdf_path}")
        for conf in mol_h.GetConformers():
            ensemble_writer.write(mol_h, confId=int(conf.GetId()))
        ensemble_writer.close()
    except Exception as exc:
        warnings.append(f"Conformer ensemble SDF write warning: {exc}")

    try:
        conf_rows = list((conformation_analysis or {}).get("conformers") or [])
        fields = list(conf_rows[0].keys()) if conf_rows else ["conf_id", "family", "energy"]
        with family_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            if conf_rows:
                writer.writerows(conf_rows)
        torsion_rows = list((conformation_analysis or {}).get("residue_torsions") or [])
        tfields = list(torsion_rows[0].keys()) if torsion_rows else ["conf_id", "residue_index", "token", "phi_deg", "psi_deg", "basin"]
        with torsion_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=tfields)
            writer.writeheader()
            if torsion_rows:
                writer.writerows(torsion_rows)
    except Exception as exc:
        warnings.append(f"Conformation analysis CSV write warning: {exc}")

    top_fields = list(top_conformers[0].keys()) if top_conformers else ["rank", "conf_id", "family", "energy", "sequence_support", "selection_reason"]
    try:
        with top5_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=top_fields)
            writer.writeheader()
            if top_conformers:
                writer.writerows(top_conformers)
    except Exception as exc:
        warnings.append(f"Top-five CSV export warning: {exc}")

    ranked_models = []
    for row in top_conformers:
        cid, rank = int(row["conf_id"]), int(row["rank"])
        model = _copy_best_conformer_only(mol_h, cid)
        model.SetProp("Pepforge_rank", str(rank))
        model.SetProp("Pepforge_family", str(row.get("family", "")))
        model.SetProp("Pepforge_sequence_support", str(row.get("sequence_support", "")))
        ranked_models.append((row, rank, model))
        ranked_pdb = outdir / f"{safe}_rank{rank}_{str(row.get('family', 'conformer'))}.pdb"
        try:
            Chem.MolToPDBFile(model, str(ranked_pdb))
        except Exception:
            ranked_pdb.write_text(Chem.MolToPDBBlock(model), encoding="utf-8", errors="ignore")
        if ranked_pdb.exists() and ranked_pdb.stat().st_size > 0:
            top5_pdb_paths.append(str(ranked_pdb))

    try:
        top_writer = Chem.SDWriter(str(top5_sdf_path))
        if top_writer is None:
            raise OSError(f"RDKit SDWriter returned None for {top5_sdf_path}")
        for _row_data, _rank, model in ranked_models:
            top_writer.write(model)
        top_writer.close()
    except Exception as exc:
        warnings.append(f"Top-five SDF export warning: {exc}")
    if len(top5_pdb_paths) != required_final:
        raise PepforgeBuildError(
            f"PSB ranked {required_final} structures but exported only {len(top5_pdb_paths)} PDB files."
        )

    # Pepforge V2.0.0 functional-stability behavior:
    # RDKit's C++ file writers can fail on some Windows user/temp paths.
    # If SDWriter/MolToPDBFile refuses the output path, fall back to Python-level
    # text writing from MolBlock/PDBBlock. This is more tolerant of Unicode paths.
    try:
        writer = Chem.SDWriter(str(sdf_path))
        if writer is None:
            raise OSError(f"RDKit SDWriter returned None for {sdf_path}")
        if keep_all_confs:
            for cid in range(mol_export.GetNumConformers()):
                writer.write(mol_export, confId=cid)
        else:
            writer.write(mol_export)
        writer.close()
    except Exception as exc:
        warnings.append(f"RDKit SDWriter path fallback used: {exc}")
        if keep_all_confs and mol_export.GetNumConformers() > 1:
            blocks = []
            for cid in range(mol_export.GetNumConformers()):
                blocks.append(Chem.MolToMolBlock(mol_export, confId=cid) + "\n$$$$\n")
            sdf_path.write_text("".join(blocks), encoding="utf-8", errors="ignore")
        else:
            sdf_path.write_text(Chem.MolToMolBlock(mol_export) + "\n$$$$\n", encoding="utf-8", errors="ignore")
    try:
        Chem.MolToPDBFile(mol_export, str(pdb_path))
    except Exception as exc:
        warnings.append(f"RDKit PDB writer path fallback used: {exc}")
        pdb_path.write_text(Chem.MolToPDBBlock(mol_export), encoding="utf-8", errors="ignore")

    audit = _chemistry_audit(mol_export, tokens, smiles)
    attach_point_map = _build_attach_point_map(tokens, atom_ranges)

    conditions = dict(environment_conditions or {})
    condition_record = {
        "pH": conditions.get("pH"),
        "temperature_C": conditions.get("temperature_C"),
        "ionic_strength_mM": conditions.get("ionic_strength_mM"),
        "environment": conditions.get("environment", "aqueous_unspecified"),
        "used_in_coordinate_energy": False,
        "reason": "RDKit ETKDG/MMFF/UFF here is not an explicit-solvent constant-pH calculation; conditions are recorded for interpretation and external validation, not converted into an invented energy correction.",
    }
    meta: Dict[str, Any] = {
        "version": VERSION,
        "input": sequence,
        "tokens": [asdict(t) for t in tokens],
        "generated_smiles": smiles,
        "warnings": warnings,
        "formula": rdMolDescriptors.CalcMolFormula(mol_export),
        "exact_mw": float(Descriptors.ExactMolWt(mol_export)),
        "heavy_atoms": int(mol.GetNumHeavyAtoms()),
        "atom_ranges": [asdict(r) for r in atom_ranges],
        "attach_point_map": attach_point_map,
        "category_counts": {},
        "chemistry_audit": audit,
        "conformer_summary": conformer_summary,
        "conformation_analysis": conformation_analysis,
        "canonical_L_helix_evidence": helix_evidence,
        "sequence_conformation_evidence": sequence_evidence,
        "evidence_guided_family_plan": family_plan,
        "environment_conditions": condition_record,
        "conformation_evidence_references": EVIDENCE_REFERENCES,
        "conformation_claim_guard": "Generated family counts are conformer-sampling outcomes, not experimental populations or free-energy probabilities. Unsupported modified residues are not assigned invented propensity numbers.",
        "conformer_ensemble_sdf_path": str(ensemble_sdf_path),
        "conformer_family_csv_path": str(family_csv_path),
        "backbone_torsion_csv_path": str(torsion_csv_path),
        "top5_conformer_sdf_path": str(top5_sdf_path),
        "top5_conformer_csv_path": str(top5_csv_path),
        "top5_conformer_pdb_paths": top5_pdb_paths,
        "template_mode": "chemistry_explicit_attachment_registry_v2",
        "template_audit": _template_audit_for_tokens(tokens),
        "label_chemistry": {t.raw: LABEL_CHEMISTRY_METADATA[t.raw] for t in tokens if t.raw in LABEL_CHEMISTRY_METADATA},
        "template_registry_notice": "Only explicitly defined chemistry is buildable. Tokens marked requires_curated_derivative are intentionally not assigned a display-only structure.",
        "sdf_path": str(sdf_path),
        "pdb_path": str(pdb_path),
        "meta_path": str(meta_path),
        "report_path": str(report_path),
    }
    for t in tokens:
        meta["category_counts"][t.kind] = meta["category_counts"].get(t.kind, 0) + 1
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(make_report(meta), encoding="utf-8")

    return BuildResult(sequence, tokens, smiles, Chem.MolToMolBlock(mol_export), str(sdf_path), str(pdb_path), str(meta_path), str(report_path), warnings, meta["formula"], meta["exact_mw"], meta["heavy_atoms"], atom_ranges)

def build_batch(items: List[Tuple[str, str]], output_dir: str | Path = ".", optimize: bool = True, num_confs: int = 8) -> List[Dict[str, Any]]:
    """Build many sequences. items = [(name, sequence), ...]. Returns status rows."""
    rows: List[Dict[str, Any]] = []
    for name, sequence in items:
        try:
            result = build_structure(sequence, output_dir=output_dir, name=name, optimize=optimize, num_confs=num_confs)
            rows.append({"name": name, "sequence": sequence, "status": "success", "sdf_path": result.sdf_path, "pdb_path": result.pdb_path, "meta_path": result.meta_path, "report_path": result.report_path, "formula": result.formula, "exact_mw": result.exact_mw, "warnings": " | ".join(result.warnings)})
        except Exception as exc:
            rows.append({"name": name, "sequence": sequence, "status": "failed", "error": str(exc)})
    return rows

def read_batch_csv(path: str | Path) -> List[Tuple[str, str]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise PepforgeBuildError("CSV has no header. Use columns: name,sequence")
        lower = {h.lower(): h for h in reader.fieldnames}
        seq_col = lower.get("sequence") or lower.get("seq")
        name_col = lower.get("name") or lower.get("id") or lower.get("rank")
        if not seq_col:
            raise PepforgeBuildError("CSV must contain a sequence column.")
        out = []
        for i, row in enumerate(reader, start=1):
            seq = (row.get(seq_col) or "").strip()
            if not seq: continue
            name = (row.get(name_col) if name_col else None) or f"pep_{i:03d}"
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_") or f"pep_{i:03d}"
            out.append((name, seq))
        return out

def describe_parse(sequence: str) -> Dict[str, object]:
    input_expansions = []
    for part in _split_top_level(sequence):
        normalized = _normalize_token(part)
        if normalized in TAG_EXPANSIONS:
            input_expansions.append({
                "raw": part,
                "kind": "tag_expansion",
                "expanded_sequence": TAG_EXPANSIONS[normalized],
                "note": "tag is expanded to its explicit canonical peptide sequence before 3D construction",
            })
        elif normalized in SEQUENCE_LINKER_EXPANSIONS:
            input_expansions.append({
                "raw": part,
                "kind": "sequence_linker_expansion",
                "expanded_sequence": SEQUENCE_LINKER_EXPANSIONS[normalized],
                "note": "peptide linker shorthand is expanded residue-by-residue before 3D construction",
            })
    raw = expand_and_tokenize(sequence)
    toks = [classify_token(t) for t in raw]
    try:
        smiles, _, warnings, ranges = tokens_to_smiles(raw)
    except Exception as exc:
        smiles, warnings, ranges = None, [str(exc)], []
    return {
        "version": VERSION,
        "input": sequence,
        "input_expansions": input_expansions,
        "tokens": [{"raw": t.raw, "kind": t.kind, "label": KIND_LABELS.get(t.kind, t.kind), "note": t.note, "parent_residue": t.parent_residue, "modification": t.modification} for t in toks],
        "generated_smiles_preview": smiles,
        "atom_ranges_preview": [asdict(r) for r in ranges],
        "warnings": warnings,
        "aliases_supported": TOKEN_ALIASES,
        "supported_tokens": supported_token_table(),
        "fixed_rule": "Labels/linkers/chemicals are never canonicalized into amino-acid residues. FITC/FAM use explicit 5-isomer conventions; ambiguous derivatives are recognized but require curated attachment chemistry before 3D construction.",
    }
