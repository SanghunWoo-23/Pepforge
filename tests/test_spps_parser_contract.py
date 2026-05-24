from apps.spps_planner_app.spps_planner.parser import parse_sequence

cases = {
    "EEMQRR": ("", "EEMQRR", ""),
    "EEMQRR-NH2": ("", "EEMQRR", "NH2"),
    "-EEMQRR-NH2": ("", "EEMQRR", "NH2"),
    "Ac-EEMQRR-NH2": ("Ac", "EEMQRR", "NH2"),
    "AcEEMQRR-NH2": ("Ac", "EEMQRR", "NH2"),
    "FITC-EEMQRR-NH2": ("FITC", "EEMQRR", "NH2"),
}

for seq, expected in cases.items():
    p = parse_sequence(seq)
    got = (p.nterm, p.core, p.cterm_text)
    assert got == expected, f"{seq}: expected {expected}, got {got}"
    assert p.core_tokens == list("EEMQRR"), f"{seq}: bad tokens {p.core_tokens}"

print("SPPS parser contract passed")
