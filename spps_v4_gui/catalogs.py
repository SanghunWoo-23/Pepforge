"""Static desktop UI catalogs used by the accepted SPPS Planner layout."""
from __future__ import annotations

PLAN_COLUMNS = [
    "No", "Unit name", "Unit eq", "Unit amount(g)", "Unit volume(mL)",
    "Coupling reagent 1", "Coupling reagent 1 eq", "Coupling reagent 1 count",
    "Coupling reagent 2 / catalyst", "Coupling reagent 2 / catalyst eq",
    "Coupling reagent 2 / catalyst count", "Coupling base", "Coupling base eq",
    "Coupling base count", "Coupling cocktail solvent",
    "Coupling cocktail volume(mL)", "Deprotection base", "Deprotection ratio",
    "Deprotection count", "Solvent 1", "Solvent 1 count", "Solvent 2",
    "Solvent 2 count", "Repeat",
]

MATERIAL_COLUMNS = [
    "step", "material", "class", "MW", "planned_mmol", "planned_g",
    "planned_mL", "use_count", "repeat", "phase", "note", "source",
]

RESIN_VALUES = [
    "Amide", "Rink Amide", "Rink Amide AM", "Rink Amide MBHA",
    "Rink Amide ChemMatrix", "Rink Amide Tentagel", "Wang", "HMPB",
    "Sieber Amide", "PAL resin", "CTC/Trityl", "2-CTC", "2-CTC",
    "Trityl chloride resin", "Tentagel", "Manual",
]

REAGENT_VALUES = [
    "", "DIC", "DCC", "EDC", "EDC-HCl", "HBTU", "HATU", "HCTU", "TBTU",
    "TSTU", "TNTU", "PyBOP", "PyAOP", "BOP", "DEPBT", "COMU", "T3P",
    "DMTMM", "TFFH", "BTC", "CDI", "MSNT", "Ghosez reagent", "PyClocK",
    "PyBrOP", "Manual",
]

CATALYST_VALUES = [
    "", "HOBt", "HOBt hydrate", "Cl-HOBt", "6-Cl-HOBt", "HOAt", "Oxyma",
    "Oxyma Pure", "K-Oxyma", "Ethyl cyano(hydroxyimino)acetate", "DMAP",
    "NHS", "Sulfo-NHS", "HOSu", "HODhbt", "DHO", "HOOBt", "HOSBt",
    "CuCl", "CuBr", "Pd(PPh3)4", "Phenylsilane", "Manual",
]

BASE_VALUES = [
    "", "DIEA", "DIPEA", "NMM", "TEA", "Triethylamine", "Pyridine",
    "2,4,6-collidine", "2,6-lutidine", "DBU", "Piperidine", "TMP", "TBAF",
    "NaHCO3", "Na2CO3", "K2CO3", "NaOH", "KOH", "Manual",
]

DEPRO_VALUES = [
    "Piperidine", "20% Piperidine/DMF", "DBU", "Piperazine", "Morpholine",
    "4-methylpiperidine", "TFA", "Hydrazine", "Pd(PPh3)4", "Manual",
]

RATIO_VALUES = [
    "20% in DMF", "2% DBU + 2% piperidine in DMF",
    "20% piperidine + 0.1 M HOBt", "Manual",
]

SOLVENT_VALUES = [
    "", "DMF", "NMP", "DCM", "90% DCM / 10% DMF", "10% DMF/DCM",
    "DCM/DMF", "DMF/NMP", "MeOH", "EtOH", "i-PrOH", "IPA", "ACN", "MeCN",
    "THF", "DMSO", "TFA", "TIS", "EDT", "Water", "H2O", "Ether",
    "Diethyl ether", "MTBE", "Dioxane", "Toluene", "Hexane", "EtOAc",
    "Acetone", "CHCl3", "HFIP", "Manual",
]

FMOC_AA_VALUES = [
    "Fmoc-Ala-OH", "Fmoc-Arg(Pbf)-OH", "Fmoc-Asn(Trt)-OH",
    "Fmoc-Asp(OtBu)-OH", "Fmoc-Cys(Trt)-OH", "Fmoc-Gln(Trt)-OH",
    "Fmoc-Glu(OtBu)-OH", "Fmoc-Gly-OH", "Fmoc-His(Trt)-OH",
    "Fmoc-Ile-OH", "Fmoc-Leu-OH", "Fmoc-Lys(Boc)-OH", "Fmoc-Met-OH",
    "Fmoc-Phe-OH", "Fmoc-Pro-OH", "Fmoc-Ser(tBu)-OH",
    "Fmoc-Thr(tBu)-OH", "Fmoc-Trp(Boc)-OH", "Fmoc-Tyr(tBu)-OH",
    "Fmoc-Val-OH",
]

FMOC_D_AA_VALUES = [
    "Fmoc-D-Ala-OH", "Fmoc-D-Arg(Pbf)-OH", "Fmoc-D-Asn(Trt)-OH",
    "Fmoc-D-Asp(OtBu)-OH", "Fmoc-D-Cys(Trt)-OH",
    "Fmoc-D-Gln(Trt)-OH", "Fmoc-D-Glu(OtBu)-OH",
    "Fmoc-D-His(Trt)-OH", "Fmoc-D-Ile-OH", "Fmoc-D-Leu-OH",
    "Fmoc-D-Lys(Boc)-OH", "Fmoc-D-Met-OH", "Fmoc-D-Phe-OH",
    "Fmoc-D-Pro-OH", "Fmoc-D-Ser(tBu)-OH", "Fmoc-D-Thr(tBu)-OH",
    "Fmoc-D-Trp(Boc)-OH", "Fmoc-D-Tyr(tBu)-OH", "Fmoc-D-Val-OH",
]

AC_AA_VALUES = [
    "Ac-Ala-OH", "Ac-Arg(Pbf)-OH", "Ac-Asn(Trt)-OH",
    "Ac-Asp(OtBu)-OH", "Ac-Cys(Trt)-OH", "Ac-Gln(Trt)-OH",
    "Ac-Glu(OtBu)-OH", "Ac-Gly-OH", "Ac-His(Trt)-OH",
    "Ac-Ile-OH", "Ac-Leu-OH", "Ac-Lys(Boc)-OH", "Ac-Met-OH",
    "Ac-Phe-OH", "Ac-Pro-OH", "Ac-Ser(tBu)-OH", "Ac-Thr(tBu)-OH",
    "Ac-Trp(Boc)-OH", "Ac-Tyr(tBu)-OH", "Ac-Val-OH",
]

FMOC_PROTECTED_VARIANT_VALUES = [
    "Fmoc-Cys(Acm)-OH", "Fmoc-Cys(StBu)-OH", "Fmoc-Cys(tBu)-OH",
    "Fmoc-Lys(Dde)-OH", "Fmoc-Lys(ivDde)-OH", "Fmoc-Lys(Alloc)-OH",
    "Fmoc-Lys(Mtt)-OH", "Fmoc-Lys(Fmoc)-OH",
    "Fmoc-D-Lys(Dde)-OH", "Fmoc-D-Lys(ivDde)-OH",
    "Fmoc-Asp(OAll)-OH", "Fmoc-Glu(OAll)-OH",
    "Fmoc-Met(O)-OH", "Fmoc-Met(O2)-OH",
]

FMOC_NON_NATURAL_AA_VALUES = [
    "Fmoc-trans-4-Hyp-OH", "Fmoc-Nle-OH", "Fmoc-Nva-OH",
    "Fmoc-Orn(Boc)-OH", "Fmoc-Dap(Boc)-OH", "Fmoc-Dab(Boc)-OH",
    "Fmoc-Aib-OH", "Fmoc-Sar-OH", "Fmoc-4-benzoyl-L-Phe-OH",
    "Fmoc-Cha-OH", "Fmoc-Cit-OH", "Fmoc-hArg(Pbf)-OH",
    "Fmoc-hLys(Boc)-OH", "Fmoc-Pen(Trt)-OH",
    "Fmoc-Abu-OH", "Fmoc-D-Abu-OH", "Fmoc-1-Nal-OH",
    "Fmoc-2-Nal-OH", "Fmoc-D-1-Nal-OH", "Fmoc-D-2-Nal-OH",
    "Fmoc-Tic-OH", "Fmoc-D-Tic-OH", "Fmoc-4-F-Phe-OH",
    "Fmoc-D-4-F-Phe-OH", "Fmoc-4-Cl-Phe-OH", "Fmoc-D-4-Cl-Phe-OH",
    "Fmoc-N-Me-Ala-OH", "Fmoc-N-Me-Leu-OH", "Fmoc-N-Me-Phe-OH",
    "Fmoc-N-Me-Val-OH", "Fmoc-Pra-OH", "Fmoc-D-Pra-OH",
]

FMOC_LINKER_VALUES = [
    "Fmoc-6-Ahx-OH", "Fmoc-AEEA-OH", "Fmoc-5-Ava-OH",
    "Fmoc-11-Aun-OH", "Fmoc-12-Ado-OH", "Fmoc-β-Ala-OH",
    "Fmoc-GABA-OH",
    "Fmoc-NH-PEG1-CH2COOH", "Fmoc-NH-PEG2-CH2COOH",
    "Fmoc-NH-PEG3-CH2COOH", "Fmoc-NH-PEG4-CH2COOH",
    "Fmoc-NH-PEG5-CH2COOH", "Fmoc-NH-PEG6-CH2COOH",
    "Fmoc-NH-PEG8-CH2COOH", "Fmoc-NH-PEG11-CH2COOH",
    "Fmoc-NH-PEG12-CH2COOH",
    "Fmoc-N-amido-PEG3-acid", "Fmoc-N-amido-PEG4-acid",
    "Fmoc-N-amido-PEG5-acid", "Fmoc-N-amido-PEG6-acid",
    "Fmoc-N-amido-PEG8-acid", "Fmoc-N-amido-PEG10-acid",
    "Fmoc-N-amido-PEG12-acid", "Fmoc-N-amido-PEG20-acid",
    "Fmoc-N-amido-PEG24-acid",
]

LABEL_VALUES = [
    "FITC", "Biotin", "Biotin acid", "Biotin-NHS", "Desthiobiotin",
    "Desthiobiotin-NHS", "5-FAM", "6-FAM", "FAM-NHS", "5-TAMRA",
    "6-TAMRA", "TAMRA-NHS", "CY5-NHS", "Sulfo-Cy5-NHS-K",
    "Sulfo-Cy5-NHS-TEA", "Dabcyl", "DOTA-tris(tBu)",
    "DOTA-NHS-tris(tBu)", "NOTA-NHS", "DBCO acid", "DBCO-PEG4-acid",
    "Biotin-PEG4-acid", "Biotin-PEG4-NHS", "Mca", "Rhodamine B",
]

CHEMICAL_MODIFIER_VALUES = [
    "Acetic anhydride (Ac2O)", "Palmitic acid", "Myristic acid",
    "Stearic acid", "Oleic acid", "Gallic acid", "Nicotinic acid",
    "Caffeic acid", "Chol-Suc",
]

TAG_VALUES = [
    "His6", "His8", "His10", "FLAG", "HA", "Myc", "StrepII",
    "TwinStrep", "V5", "T7", "ALFA", "AviTag", "SpyTag",
]

UNIT_VALUES = [
    "", *FMOC_AA_VALUES, *FMOC_D_AA_VALUES, *AC_AA_VALUES,
    *FMOC_PROTECTED_VARIANT_VALUES, *FMOC_NON_NATURAL_AA_VALUES,
    *FMOC_LINKER_VALUES, *LABEL_VALUES, *CHEMICAL_MODIFIER_VALUES,
    *TAG_VALUES, "Manual",
]

LEGACY_UNIT_ALIASES = {
    **dict(zip("ARNDCEQGHILKMFPSTWYV", FMOC_AA_VALUES)),
    **dict(zip(
        ("Ala", "Arg", "Asn", "Asp", "Cys", "Gln", "Glu", "Gly",
         "His", "Ile", "Leu", "Lys", "Met", "Phe", "Pro", "Ser",
         "Thr", "Trp", "Tyr", "Val"),
        FMOC_AA_VALUES,
    )),
    **dict(zip(
        ("D-Ala", "D-Arg", "D-Asn", "D-Asp", "D-Cys", "D-Gln",
         "D-Glu", "D-His", "D-Ile", "D-Leu", "D-Lys", "D-Met",
         "D-Phe", "D-Pro", "D-Ser", "D-Thr", "D-Trp", "D-Tyr",
         "D-Val"),
        FMOC_D_AA_VALUES,
    )),
    "dA": "Fmoc-D-Ala-OH", "dR": "Fmoc-D-Arg(Pbf)-OH",
    "dN": "Fmoc-D-Asn(Trt)-OH", "dD": "Fmoc-D-Asp(OtBu)-OH",
    "dC": "Fmoc-D-Cys(Trt)-OH", "dQ": "Fmoc-D-Gln(Trt)-OH",
    "dE": "Fmoc-D-Glu(OtBu)-OH", "dH": "Fmoc-D-His(Trt)-OH",
    "dI": "Fmoc-D-Ile-OH", "dL": "Fmoc-D-Leu-OH",
    "dK": "Fmoc-D-Lys(Boc)-OH", "dM": "Fmoc-D-Met-OH",
    "dF": "Fmoc-D-Phe-OH", "dP": "Fmoc-D-Pro-OH",
    "dS": "Fmoc-D-Ser(tBu)-OH", "dT": "Fmoc-D-Thr(tBu)-OH",
    "dW": "Fmoc-D-Trp(Boc)-OH", "dY": "Fmoc-D-Tyr(tBu)-OH",
    "dV": "Fmoc-D-Val-OH",
    "dG": "Fmoc-Gly-OH",
    "D-A": "Fmoc-D-Ala-OH", "D-R": "Fmoc-D-Arg(Pbf)-OH",
    "D-N": "Fmoc-D-Asn(Trt)-OH", "D-D": "Fmoc-D-Asp(OtBu)-OH",
    "D-C": "Fmoc-D-Cys(Trt)-OH", "D-Q": "Fmoc-D-Gln(Trt)-OH",
    "D-E": "Fmoc-D-Glu(OtBu)-OH", "D-G": "Fmoc-Gly-OH",
    "D-H": "Fmoc-D-His(Trt)-OH", "D-I": "Fmoc-D-Ile-OH",
    "D-L": "Fmoc-D-Leu-OH", "D-K": "Fmoc-D-Lys(Boc)-OH",
    "D-M": "Fmoc-D-Met-OH", "D-F": "Fmoc-D-Phe-OH",
    "D-P": "Fmoc-D-Pro-OH", "D-S": "Fmoc-D-Ser(tBu)-OH",
    "D-T": "Fmoc-D-Thr(tBu)-OH", "D-W": "Fmoc-D-Trp(Boc)-OH",
    "D-Y": "Fmoc-D-Tyr(tBu)-OH", "D-V": "Fmoc-D-Val-OH",
    "Hyp": "Fmoc-trans-4-Hyp-OH", "Nle": "Fmoc-Nle-OH",
    "Nva": "Fmoc-Nva-OH", "Orn": "Fmoc-Orn(Boc)-OH",
    "Dap": "Fmoc-Dap(Boc)-OH", "Dab": "Fmoc-Dab(Boc)-OH",
    "Aib": "Fmoc-Aib-OH", "Sar": "Fmoc-Sar-OH",
    "Bpa": "Fmoc-4-benzoyl-L-Phe-OH", "Cha": "Fmoc-Cha-OH",
    "Cit": "Fmoc-Cit-OH", "hArg": "Fmoc-hArg(Pbf)-OH",
    "hLys": "Fmoc-hLys(Boc)-OH", "Pen": "Fmoc-Pen(Trt)-OH",
    "Ahx": "Fmoc-6-Ahx-OH", "AEEA": "Fmoc-AEEA-OH",
    "PEG1": "Fmoc-NH-PEG1-CH2COOH", "PEG2": "Fmoc-NH-PEG2-CH2COOH",
    "PEG3": "Fmoc-NH-PEG3-CH2COOH", "PEG4": "Fmoc-NH-PEG4-CH2COOH",
    "PEG5": "Fmoc-NH-PEG5-CH2COOH",
    "PEG6": "Fmoc-NH-PEG6-CH2COOH", "PEG8": "Fmoc-NH-PEG8-CH2COOH",
    "PEG11": "Fmoc-NH-PEG11-CH2COOH",
    "PEG12": "Fmoc-NH-PEG12-CH2COOH",
    "PEG24": "Fmoc-N-amido-PEG24-acid",
    "bAla": "Fmoc-β-Ala-OH", "gAla": "Fmoc-GABA-OH",
    "GABA": "Fmoc-GABA-OH",
}


def canonical_unit_name(value: object) -> str:
    """Convert legacy display aliases to one unambiguous bottle name."""
    text = str(value or "").strip()
    return LEGACY_UNIT_ALIASES.get(text, text)

MW_FALLBACK = {
    "A": 311.29, "R": 648.77, "N": 596.67, "D": 411.45, "C": 585.72,
    "Q": 610.70, "E": 425.48, "G": 297.26, "H": 619.72, "I": 353.42,
    "L": 353.42, "K": 468.55, "M": 371.45, "F": 387.43, "P": 337.37,
    "S": 383.39, "T": 397.42, "W": 526.58, "Y": 459.50, "V": 339.39,
    "DIC": 126.20, "DCC": 206.33, "EDC": 191.70, "HBTU": 379.25,
    "HATU": 380.23, "HCTU": 413.69, "TBTU": 321.08, "PyBOP": 520.39,
    "PyAOP": 521.36, "BOP": 442.28, "COMU": 427.35, "T3P": 318.18,
    "DMTMM": 276.72, "TFFH": 226.19, "BTC": 296.75, "CDI": 162.15,
    "MSNT": 284.29, "HOBt": 135.13, "Cl-HOBt": 169.57,
    "6-Cl-HOBt": 169.57, "HOAt": 136.11, "Oxyma": 142.11,
    "Oxyma Pure": 142.11, "K-Oxyma": 180.20, "DMAP": 122.17,
    "NHS": 115.09, "Sulfo-NHS": 217.13, "HOSu": 115.09,
    "HODhbt": 151.12, "DHO": 151.12, "DIEA": 129.25, "DIPEA": 129.25,
    "NMM": 101.15, "TEA": 101.19, "Pyridine": 79.10,
    "2,4,6-collidine": 121.18, "2,6-lutidine": 107.16, "DBU": 152.24,
    "Piperidine": 85.15, "Piperazine": 86.14, "Morpholine": 87.12,
    "4-methylpiperidine": 99.18, "TMP": 141.25, "Ac2O": 102.09,
    "Acetic anhydride": 102.09, "AcOH": 60.05, "Acetic acid": 60.05,
    "DMF": 73.09, "NMP": 99.13, "DCM": 84.93, "MeOH": 32.04,
    "EtOH": 46.07, "i-PrOH": 60.10, "ACN": 41.05, "THF": 72.11,
    "DMSO": 78.13, "TFA": 114.02, "TIS": 158.36, "Water": 18.02,
    "Ether": 74.12, "Diethyl ether": 74.12, "MTBE": 88.15,
    "FITC": 389.38, "Biotin": 244.31, "Biotin-NHS": 341.38,
    "FAM": 376.32, "TAMRA": 430.45, "ROX": 534.56, "CY3": 766.90,
    "CY5": 792.99, "CY7": 818.03, "Dabcyl": 252.28, "BHQ1": 552.50,
    "BHQ2": 579.50, "DOTA": 404.42, "NOTA": 393.35, "Ahx": 131.17,
    "AEEA": 175.20, "PEG1": 149.15, "PEG3": 237.25, "PEG4": 281.30,
    "PEG6": 369.41, "PEG8": 457.52, "bAla": 89.09, "gAla": 103.12,
    "His6": 840.8, "His8": 1098.9, "His10": 1357.1, "FLAG": 1012.0,
    "HA": 1102.2, "Myc": 1203.3, "StrepII": 1010.1,
    "TwinStrep": 2300.6, "V5": 1421.5, "T7": 1315.4, "ALFA": 1583.8,
    "AviTag": 1622.8, "SpyTag": 1515.6, "Pal": 256.43,
    "Palmitic acid": 256.43, "Myr": 228.38, "Myristic acid": 228.38,
    "Nic": 123.11, "Nicotinic acid": 123.11, "Caf": 180.16,
    "Caffeic acid": 180.16, "Gal": 170.12, "Gallic acid": 170.12,
    "Stear": 284.48, "Stearic acid": 284.48,
}

MW_FALLBACK.update({
    "Fmoc-D-Ala-OH": 311.29, "Fmoc-D-Arg(Pbf)-OH": 648.77,
    "Fmoc-D-Asn(Trt)-OH": 596.67, "Fmoc-D-Asp(OtBu)-OH": 411.45,
    "Fmoc-D-Cys(Trt)-OH": 585.72, "Fmoc-D-Gln(Trt)-OH": 610.70,
    "Fmoc-D-Glu(OtBu)-OH": 425.48, "Fmoc-D-His(Trt)-OH": 619.72,
    "Fmoc-D-Ile-OH": 353.42, "Fmoc-D-Leu-OH": 353.42,
    "Fmoc-D-Lys(Boc)-OH": 468.55, "Fmoc-D-Met-OH": 371.45,
    "Fmoc-D-Phe-OH": 387.43, "Fmoc-D-Pro-OH": 337.37,
    "Fmoc-D-Ser(tBu)-OH": 383.44, "Fmoc-D-Thr(tBu)-OH": 397.47,
    "Fmoc-D-Trp(Boc)-OH": 526.58, "Fmoc-D-Tyr(tBu)-OH": 459.54,
    "Fmoc-D-Val-OH": 339.39,
    "Fmoc-6-Ahx-OH": 353.42, "Fmoc-AEEA-OH": 383.44,
    "Fmoc-5-Ava-OH": 339.39, "Fmoc-11-Aun-OH": 423.55,
    "Fmoc-12-Ado-OH": 437.57, "Fmoc-β-Ala-OH": 311.33,
    "Fmoc-GABA-OH": 325.36,
    "Fmoc-NH-PEG1-CH2COOH": 341.4,
    "Fmoc-NH-PEG2-CH2COOH": 385.4,
    "Fmoc-NH-PEG3-CH2COOH": 429.5,
    "Fmoc-NH-PEG4-CH2COOH": 473.5,
    "Fmoc-NH-PEG5-CH2COOH": 517.6,
    "Fmoc-NH-PEG6-CH2COOH": 561.6,
    "Fmoc-NH-PEG8-CH2COOH": 649.7,
    "Fmoc-NH-PEG11-CH2COOH": 781.9,
    "Fmoc-NH-PEG12-CH2COOH": 826.0,
    "Fmoc-N-amido-PEG3-acid": 443.50,
    "Fmoc-N-amido-PEG4-acid": 487.54,
    "Fmoc-N-amido-PEG5-acid": 531.59,
    "Fmoc-N-amido-PEG6-acid": 575.66,
    "Fmoc-N-amido-PEG8-acid": 663.75,
    "Fmoc-N-amido-PEG10-acid": 751.87,
    "Fmoc-N-amido-PEG12-acid": 840.0,
    "Fmoc-N-amido-PEG20-acid": 1192.4,
    "Fmoc-N-amido-PEG24-acid": 1368.6,
    "Fmoc-trans-4-Hyp-OH": 353.37, "Fmoc-Nle-OH": 353.41,
    "Fmoc-Nva-OH": 339.39, "Fmoc-Orn(Boc)-OH": 454.52,
    "Fmoc-Dap(Boc)-OH": 426.51, "Fmoc-Dab(Boc)-OH": 440.49,
    "Fmoc-Aib-OH": 325.36, "Fmoc-Sar-OH": 311.33,
    "Fmoc-4-benzoyl-L-Phe-OH": 491.54, "Fmoc-Cha-OH": 393.48,
    "Fmoc-Cit-OH": 397.43, "Fmoc-hArg(Pbf)-OH": 662.80,
    "Fmoc-hLys(Boc)-OH": 482.58, "Fmoc-Pen(Trt)-OH": 613.77,
})

MW_FALLBACK.update({
    "Fmoc-Cys(Acm)-OH": 414.48, "Fmoc-Cys(StBu)-OH": 433.55,
    "Fmoc-Cys(tBu)-OH": 399.50, "Fmoc-Lys(Dde)-OH": 532.63,
    "Fmoc-Lys(ivDde)-OH": 560.68, "Fmoc-Lys(Alloc)-OH": 510.58,
    "Fmoc-Lys(Mtt)-OH": 624.77, "Fmoc-Lys(Fmoc)-OH": 590.67,
    "Fmoc-D-Lys(Dde)-OH": 532.63, "Fmoc-D-Lys(ivDde)-OH": 560.68,
    "Fmoc-Asp(OAll)-OH": 397.42, "Fmoc-Glu(OAll)-OH": 411.45,
    "Fmoc-Met(O)-OH": 387.45, "Fmoc-Met(O2)-OH": 403.45,
    "Fmoc-Abu-OH": 325.36, "Fmoc-D-Abu-OH": 325.36,
    "Fmoc-1-Nal-OH": 437.49, "Fmoc-2-Nal-OH": 437.49,
    "Fmoc-D-1-Nal-OH": 437.49, "Fmoc-D-2-Nal-OH": 437.49,
    "Fmoc-Tic-OH": 399.44, "Fmoc-D-Tic-OH": 399.44,
    "Fmoc-4-F-Phe-OH": 405.42, "Fmoc-D-4-F-Phe-OH": 405.42,
    "Fmoc-4-Cl-Phe-OH": 421.88, "Fmoc-D-4-Cl-Phe-OH": 421.88,
    "Fmoc-N-Me-Ala-OH": 325.36, "Fmoc-N-Me-Leu-OH": 367.44,
    "Fmoc-N-Me-Phe-OH": 401.46, "Fmoc-N-Me-Val-OH": 353.41,
    "Fmoc-Pra-OH": 347.37, "Fmoc-D-Pra-OH": 347.37,
    "5-FAM": 376.32, "6-FAM": 376.32, "FAM-NHS": 473.39,
    "5-TAMRA": 430.46, "6-TAMRA": 430.46, "TAMRA-NHS": 527.53,
    "CY5-NHS": 855.07, "Sulfo-Cy5-NHS-K": 777.95,
    "Sulfo-Cy5-NHS-TEA": 1050.35, "DOTA-tris(tBu)": 572.73,
    "DOTA-NHS-tris(tBu)": 669.81, "NOTA-NHS": 444.40,
    "DBCO acid": 305.33, "DBCO-PEG4-acid": 552.60,
    "Desthiobiotin": 214.26, "Desthiobiotin-NHS": 311.34,
    "Biotin-PEG4-acid": 491.61, "Biotin-PEG4-NHS": 588.68,
    "Mca": 234.21, "Rhodamine B": 479.02,
    "Stearic acid": 284.48, "Oleic acid": 282.46,
    "Chol-Suc": 486.73,
})

LIQUID_DENSITY = {
    "DIC": 0.815, "AC2O": 1.08, "ACETIC ANHYDRIDE": 1.08, "ACOH": 1.05,
    "ACETIC ACID": 1.05, "DIEA": 0.742, "DIPEA": 0.742, "NMM": 0.92,
    "TEA": 0.726, "PYRIDINE": 0.982, "2,4,6-COLLIDINE": 0.917,
    "2,6-LUTIDINE": 0.925, "PIPERIDINE": 0.862, "DBU": 1.02,
    "DMF": 0.944, "NMP": 1.03, "DCM": 1.33, "MEOH": 0.792,
    "ETOH": 0.789, "I-PROH": 0.786, "ACN": 0.786, "THF": 0.889,
    "DMSO": 1.10, "TFA": 1.49, "TIS": 0.773, "WATER": 1.00,
    "ETHER": 0.713, "DIETHYL ETHER": 0.713, "MTBE": 0.740,
}

AA_LIKE_LINKER_TOKENS = {
    "AHX", "AEEA", "CHA", "AIB", "NLE", "ORN", "CIT", "HYP", "DAB", "NAL",
    "BALA", "B-ALA", "GABA", "PEG1", "PEG2", "PEG3", "PEG4", "PEG6",
    "PEG8", "PEG12", "PEG24", "G4S", "G4SX2", "SAR", "BA", "BETA-ALA",
}

CHEMICAL_LABEL_TOKENS = {
    "AC", "AC-", "ACETYL", "ACETYL CAP", "AC / ACETYL CAP", "FITC",
    "BIOTIN", "BIOTIN-NHS", "BIOTIN ACID", "BIOTINCAP", "FAM", "5-FAM",
    "6-FAM", "FAM-NHS", "TAMRA", "ROX", "CY3", "CY5", "CY5_5", "CY7",
    "DABCYL", "BHQ", "BHQ1", "BHQ2", "DOTA", "NOTA", "DFO", "NBD",
    "DANSYL", "BODIPY", "EDANS", "PAL", "PALMITIC ACID", "PALMITICACID",
    "PALMITOYL", "MYR", "MYRISTIC ACID", "MYRISTICACID", "MYRISTOYL",
    "STEAR", "STEARIC ACID", "STEARICACID", "OLE", "OLEIC ACID",
    "OLEICACID", "GAL", "GALLIC ACID", "GALLICACID", "GALLOYL", "NIC",
    "NICOTINIC ACID", "NICOTINICACID", "CAF", "CAFFEIC ACID",
    "CAFFEICACID", "CAFFEOYL", "MALEIMIDE", "NHS",
}

CHEMICAL_DISPLAY_NAMES = {
    "PAL": "Palmitic acid", "PALMITICACID": "Palmitic acid",
    "PALMITOYL": "Palmitic acid", "MYR": "Myristic acid",
    "MYRISTICACID": "Myristic acid", "MYRISTOYL": "Myristic acid",
    "GAL": "Gallic acid", "GALLICACID": "Gallic acid",
    "GALLOYL": "Gallic acid", "CAF": "Caffeic acid",
    "CAFFEICACID": "Caffeic acid", "CAFFEOYL": "Caffeic acid",
    "NIC": "Nicotinic acid", "NICOTINICACID": "Nicotinic acid",
    "NICOTINOYL": "Nicotinic acid", "STEAR": "Stearic acid",
    "STEARICACID": "Stearic acid", "STE": "Stearic acid",
    "OLE": "Oleic acid", "OLEICACID": "Oleic acid",
}
