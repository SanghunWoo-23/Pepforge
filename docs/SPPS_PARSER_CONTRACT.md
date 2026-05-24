# SPPS Parser Contract

The SPPS parser must recognize the following as the same core peptide:

- EEMQRR
- EEMQRR-NH2
- -EEMQRR-NH2
- Ac-EEMQRR-NH2
- AcEEMQRR-NH2
- FITC-EEMQRR-NH2
- Biotin-EEMQRR-NH2

Expected parsing for EEMQRR-NH2:

    nterm = ""
    core = "EEMQRR"
    cterm = "NH2"
    core_tokens = ["E", "E", "M", "Q", "R", "R"]

Expected parsing for Ac-EEMQRR-NH2:

    nterm = "Ac"
    core = "EEMQRR"
    cterm = "NH2"
    core_tokens = ["E", "E", "M", "Q", "R", "R"]
