"""Lightweight single source of truth for PDE chemistry option names.

This module intentionally imports only Python builtins so both the standalone PDE
and Workflow Mode can populate chemistry selectors without triggering NumPy/RDKit
or the full PDE engine during GUI startup.
"""
from __future__ import annotations

PDE_TAG_TYPES = [
    "His6", "His8", "His10", "FLAG", "HA", "Myc", "StrepII", "TwinStrep",
    "V5", "T7", "ALFA", "AviTag", "SpyTag",
]
PDE_BASE_CHEM_TYPES = [
    "Pal", "Myr", "Stear", "Ole", "Chol", "Nic", "Caf", "Gal", "Ac", "Bz",
    "Fmoc", "Boc", "Succinyl", "Maleimide", "Azide", "Alkyne", "DBCO", "TCO",
    "Tetrazine", "BiotinCap",
]
PDE_LABEL_TYPES = [
    "NONE", "BIOTIN", "Desthiobiotin", "FITC", "FAM", "TAMRA", "ROX", "CY3",
    "CY5", "CY5_5", "CY7", "Alexa488", "Alexa555", "Alexa647", "DOTA", "NOTA",
    "DFO", "NBD", "Dansyl", "BODIPY", "EDANS", "Dabcyl", "BHQ1", "BHQ2",
]
PDE_LINKER_TYPES = [
    "Gly", "GG", "GGG", "GS", "GSG", "G4S", "G4Sx2", "Ahx", "AEEA", "PEG1",
    "PEG2", "PEG3", "PEG4", "PEG6", "PEG8", "PEG12", "PEG24", "Sar", "Pro",
    "PipLink", "LysLink", "CysLink", "SS", "Triazole", "Click", "DSS", "SMCC",
    "SulfoSMCC", "EDC", "Hydrazone", "Oxime",
]

# Verified against the V4 explicit PSB graph builder.  Workflow Mode exposes only
# this intersection so every selectable chemistry can reach PSB without a hidden
# canonical substitution. The standalone PDE keeps the full catalogs above.
WORKFLOW_PSB_SAFE_BASE_CHEM_TYPES = [
    "Pal", "Myr", "Stear", "Nic", "Caf", "Gal", "Ac", "Fmoc", "Boc",
]
WORKFLOW_PSB_SAFE_LINKER_TYPES = [
    "Gly", "GG", "GGG", "GS", "GSG", "G4S", "G4Sx2", "Ahx", "AEEA", "PEG1",
    "PEG2", "PEG3", "PEG4", "PEG6", "PEG8", "PEG12", "PEG24", "Sar", "Pro",
]
WORKFLOW_PSB_SAFE_TAG_TYPES = PDE_TAG_TYPES.copy()
WORKFLOW_PSB_SAFE_LABEL_TYPES = ["NONE", "BIOTIN", "FITC", "FAM"]
WORKFLOW_PSB_SAFE_NON_NAT_TYPES = [
    "Nle", "Nva", "Abu", "Aib", "Sar", "Orn", "Dab", "Dap", "Cit", "Hyp",
    "Cha", "Nal", "bAla", "gAla",
]
