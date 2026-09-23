"""Small, dependency-free MSDS/SDS lookup helper for Pepforge V4.

Pepforge does not scrape, cache, or certify third-party safety data.  This
module only opens an explicit Google SDS/MSDS search in the user's default web
browser.  The operator must still verify the supplier, product, concentration,
and CAS number against the material actually used in the lab.
"""
from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote_plus
from typing import Iterable, Sequence


# Search-friendly expansions.  They improve Google queries without pretending
# that an abbreviation uniquely identifies a supplier/product formulation.
CHEMICAL_ALIASES: dict[str, str] = {
    "DMF": "N,N-Dimethylformamide",
    "DCM": "Dichloromethane",
    "NMP": "N-Methyl-2-pyrrolidone",
    "MEOH": "Methanol",
    "METHANOL": "Methanol",
    "TFA": "Trifluoroacetic acid",
    "TIS": "Triisopropylsilane",
    "DIPEA": "N,N-Diisopropylethylamine",
    "DIEA": "N,N-Diisopropylethylamine",
    "DIC": "N,N'-Diisopropylcarbodiimide",
    "HOBT": "1-Hydroxybenzotriazole",
    "OXYMA": "Oxyma Pure",
    "HBTU": "HBTU peptide coupling reagent",
    "HATU": "HATU peptide coupling reagent",
    "HCTU": "HCTU peptide coupling reagent",
    "PYBOP": "PyBOP peptide coupling reagent",
    "PIPERIDINE": "Piperidine",
    "HYDRAZINE": "Hydrazine",
    "NH4I": "Ammonium iodide",
    "AMMONIUM IODIDE": "Ammonium iodide",
    "ETHER": "Diethyl ether",
    "DIETHYL ETHER": "Diethyl ether",
    "N-HEXANE": "n-Hexane",
    "HEXANE": "n-Hexane",
    "AC": "Acetyl peptide N-terminus",
    "PAL": "Palmitic acid",
    "MYR": "Myristic acid",
    "NIC": "Nicotinic acid",
    "CAF": "Caffeic acid",
    "GAL": "Gallic acid",
    "BIOTIN": "Biotin",
    "FITC": "Fluorescein isothiocyanate",
    "FAM": "6-Carboxyfluorescein",
    "CY5": "Cyanine5 dye",
    "AHX": "6-Aminohexanoic acid",
    "AEEA": "AEEA aminoethoxyethoxyacetic acid",
    "PEG4": "PEG4 linker",
    "PEG8": "PEG8 linker",
    "NLE": "Norleucine",
    "ORN": "Ornithine",
    "AIB": "2-Aminoisobutyric acid",
    "CHA": "Cyclohexylalanine",
    "NAL": "Naphthylalanine",
    "DAB": "2,4-Diaminobutyric acid",
    "CIT": "Citrulline",
    "HYP": "Hydroxyproline",
}


def _norm(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()


def canonical_search_term(term: object) -> str:
    """Return a search-friendly label while preserving unknown exact names."""
    text = " ".join(str(term or "").strip().split())
    if not text:
        return ""
    return CHEMICAL_ALIASES.get(_norm(text), text)


def google_msds_url(term: object) -> str:
    """Build a Google query URL for SDS/MSDS lookup."""
    chemical = canonical_search_term(term)
    if not chemical:
        raise ValueError("Enter or select a chemical/reagent before opening MSDS/SDS search.")
    query = f'"{chemical}" SDS MSDS safety data sheet'
    return "https://www.google.com/search?q=" + quote_plus(query)


def open_google_msds(term: object, opener=None) -> str:
    """Open a Google SDS/MSDS search and return the URL used."""
    url = google_msds_url(term)
    browser = opener or webbrowser.open_new_tab
    browser(url)
    return url


def unique_terms(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value or "").strip().split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def terms_from_text(value: object) -> list[str]:
    """Extract known reagent abbreviations from mixed condition strings.

    If no known token can be found, the original non-empty text is retained so
    exact bottle/material names can still be searched directly.
    """
    text = " ".join(str(value or "").strip().split())
    if not text:
        return []

    matches: list[tuple[int, int, str]] = []
    upper = text.upper()
    # Preserve the order in which components appear in the recipe while using
    # longest aliases as a tie-breaker for overlapping names.
    for alias in CHEMICAL_ALIASES:
        pat = r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])"
        match = re.search(pat, upper)
        if match:
            matches.append((match.start(), -len(alias), alias))
    if matches:
        matches.sort()
        return unique_terms(alias for _pos, _neg_len, alias in matches)

    # Strip obvious numeric recipe decoration, but do not rewrite chemistry.
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*(?:eq|mL|uL|µL|mmol|mol|M|%|h|min)\b", " ", text, flags=re.I)
    cleaned = " ".join(cleaned.split()).strip(" /,+;:")
    return [cleaned or text]


def peptide_chemistry_terms(sequence: object) -> list[str]:
    """Return explicit non-standard/terminal chemistry tokens from notation.

    Natural one-letter residues are intentionally not expanded into protected
    SPPS bottle identities because PDE notation does not specify protection
    state or supplier.  SPPS Materials is the authoritative place for exact
    synthesis-reagent lookup.
    """
    raw = str(sequence or "").strip()
    if not raw:
        return []
    try:
        from peptiforg_core.peptide_tokens import parse_peptide_notation

        parsed = parse_peptide_notation(raw)
        terms: list[str] = []
        if parsed.nterm:
            terms.append(parsed.nterm)
        terms.extend(parsed.linker_tokens)
        terms.extend(parsed.aa_like_tokens)
        terms.extend(parsed.unknown_tokens)
        # Compact dAA tokens are chemistry-relevant even though the shared parser
        # maps them to natural-AA surrogates for sequence-level calculations.
        terms.extend(re.findall(r"(?<![A-Za-z])d[A-Z](?![A-Za-z])", raw))
        return unique_terms(terms)
    except Exception:
        return []


def show_msds_lookup(
    parent,
    terms: Sequence[object] | None = None,
    *,
    title: str = "MSDS / SDS lookup",
    note: str = "",
):
    """Show an editable lookup dialog that opens Google in the default browser."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    choices = unique_terms(terms or [])
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(True, False)
    try:
        from peptiforg_core.ui_helpers import set_pepforge_icon
        from peptiforg_core.ui_theme import apply_pepforge_theme

        set_pepforge_icon(win)
        apply_pepforge_theme(win)
    except Exception:
        # Safety lookup must remain usable even if optional suite styling fails.
        pass

    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="MSDS / SDS web lookup", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text=(
            "Select a material or type an exact reagent/product name. Pepforge opens a Google SDS/MSDS search "
            "in your default browser; it does not certify or cache third-party safety data."
        ),
        wraplength=620,
        justify="left",
    ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

    query_var = tk.StringVar(value=choices[0] if choices else "")
    combo = ttk.Combobox(frame, textvariable=query_var, values=choices, state="normal", width=72)
    combo.grid(row=2, column=0, sticky="ew")
    combo.focus_set()

    if note:
        ttk.Label(frame, text=note, foreground="#555", wraplength=620, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 2))

    status = tk.StringVar(value="Verify supplier/product/CAS and concentration before lab use.")
    ttk.Label(frame, textvariable=status, foreground="#555", wraplength=620, justify="left").grid(row=4, column=0, sticky="ew", pady=(8, 8))

    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, sticky="e")

    def do_open(_event=None):
        term = query_var.get().strip()
        if not term:
            messagebox.showinfo("MSDS / SDS", "Select or enter a chemical/reagent first.", parent=win)
            return
        try:
            url = open_google_msds(term)
            status.set(f"Opened Google SDS/MSDS search for: {canonical_search_term(term)}")
            return url
        except Exception as exc:
            messagebox.showerror("MSDS / SDS", f"Could not open the web browser:\n{exc}", parent=win)
            return None

    ttk.Button(buttons, text="Open Google SDS / MSDS", command=do_open).pack(side="left", padx=4)
    ttk.Button(buttons, text="Close", command=win.destroy).pack(side="left", padx=4)
    combo.bind("<Return>", do_open)
    return win


__all__ = [
    "CHEMICAL_ALIASES",
    "canonical_search_term",
    "google_msds_url",
    "open_google_msds",
    "peptide_chemistry_terms",
    "show_msds_lookup",
    "terms_from_text",
    "unique_terms",
]
