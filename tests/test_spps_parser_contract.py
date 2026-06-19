from apps.spps_planner_app.spps_planner.parser import parse_sequence

cases = {
    "EEMQRR": ("", "EEMQRR", "", list("EEMQRR")),
    "EEMQRR-NH2": ("", "EEMQRR", "NH2", list("EEMQRR")),
    "-EEMQRR-NH2": ("", "EEMQRR", "NH2", list("EEMQRR")),
    "Ac-EEMQRR-NH2": ("Ac", "EEMQRR", "NH2", list("EEMQRR")),
    "AcEEMQRR-NH2": ("Ac", "EEMQRR", "NH2", list("EEMQRR")),
    "FITC-EEMQRR-NH2": ("FITC", "EEMQRR", "NH2", list("EEMQRR")),
    "ACDE-NH2": ("", "ACDE", "NH2", list("ACDE")),
    "PALE-NH2": ("", "PALE", "NH2", list("PALE")),
}

for seq, expected in cases.items():
    p = parse_sequence(seq)
    got = (p.nterm, p.core, p.cterm_text, p.core_tokens)
    assert got == expected, f"{seq}: expected {expected}, got {got}"

print("SPPS parser contract passed")
