"""Optional sequence-first Auto Plan confirmation UI.

The existing Project Manager Generate remains the calculation authority.
No empirical cleavage recommendation is manufactured by this preview.
"""
from __future__ import annotations
import math
import tkinter as tk
from tkinter import ttk, messagebox
from spps_planner.parser import parse_sequence


def preview_inputs(sequence, scale, resin, loading, chemistry, copies):
    if not str(sequence or "").strip():
        raise ValueError("Enter a peptide sequence first.")
    parsed = parse_sequence(str(sequence).strip())
    tokens = list(parsed.core_tokens)
    if not tokens:
        raise ValueError("The sequence has no recognized amino-acid residues.")
    try:
        amount, load = float(scale), float(loading)
        count = int(copies)
    except (TypeError, ValueError) as exc:
        raise ValueError("Scale, loading, and copies must be numeric.") from exc
    if not all(math.isfinite(v) and v > 0 for v in (amount, load)) or count < 1:
        raise ValueError("Scale, loading, and copies must be positive finite values.")
    if not str(resin).strip():
        raise ValueError("Select a resin before generating.")
    cys = sum(str(token).upper() == "C" for token in tokens)
    tfa_eq = 100 * cys if cys else (30 if len(tokens) <= 7 else 80 if len(tokens) <= 15 else 100)
    return {
        "sequence": str(sequence).strip(), "residues": len(tokens),
        "scale": amount, "resin": str(resin).strip(), "loading": load,
        "copies": count, "chemistry": str(chemistry).strip(),
        "resin_g": amount / load, "tfa_eq": tfa_eq,
        "cys_count": cys, "nterm": parsed.nterm, "cterm": parsed.cterm_text,
    }


def open_auto_plan(gui):
    try:
        data = preview_inputs(gui.pm_sequence.get(), gui.pm_scale.get(),
                              gui.pm_resin.get(), gui.pm_loading.get(),
                              gui.pm_chemistry.get(), gui.pm_copies.get())
    except (ValueError, KeyError, AttributeError) as exc:
        messagebox.showerror("Auto Plan — check inputs", str(exc), parent=gui)
        return
    win = tk.Toplevel(gui)
    win.title("Auto Plan | SPPS Planner V8.0.0")
    win.geometry("720x590")
    win.minsize(580, 450)
    win.transient(gui)
    body = ttk.Frame(win, padding=16)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Auto Plan — review before generation", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(body, text="Optional: existing Generate and Step 1 / Step 2 remain unchanged.", wraplength=660).pack(anchor="w", pady=(4, 12))
    text = tk.Text(body, height=19, wrap="word", font=("Consolas", 10), relief="flat", borderwidth=6)
    text.pack(fill="both", expand=True)
    details = [
        "CURRENT PROJECT INPUTS (not changed by opening this window)",
        f"Sequence       {data['sequence']}",
        f"Residues       {data['residues']}",
        f"N-terminal     {data['nterm'] or 'none'}",
        f"C-terminal     {data['cterm'] or 'from resin / sequence notation'}",
        f"Scale          {data['scale']:g} mmol  ×  {data['copies']} copies",
        f"Resin          {data['resin']}",
        f"Loading        {data['loading']:g} mmol/g",
        f"Resin mass     {data['resin_g']:g} g per copy (theoretical)",
        f"Chemistry      {data['chemistry']}",
        "",
        "CLEAVAGE PLANNING — RULE-BASED, NOT VERIFIED RECIPE",
        f"TFA basis      {data['tfa_eq']} eq (Cys count: {data['cys_count']})",
        "Cocktail       NOT auto-selected; use verified operator conditions",
        "Time           NOT inferable from sequence alone",
        "TIS / NH4I     NEVER automatically added",
        "",
        "GENERATE WILL UPDATE",
        "Plan · Materials · Checklist · Total Materials · Cleavage / Workup",
        "using the existing engine and active Project Manager settings.",
        "Inspect the resulting tables and evidence before laboratory use.",
    ]
    text.insert("1.0", "\n".join(details))
    text.configure(state="disabled")
    status = ttk.Label(body, text="Review the above assumptions before applying.", foreground="#815500")
    status.pack(anchor="w", pady=(8, 6))
    buttons = ttk.Frame(body)
    buttons.pack(fill="x")

    def generate():
        try:
            latest = preview_inputs(gui.pm_sequence.get(), gui.pm_scale.get(), gui.pm_resin.get(),
                                    gui.pm_loading.get(), gui.pm_chemistry.get(), gui.pm_copies.get())
            if latest != data:
                messagebox.showwarning("Auto Plan", "Project values changed since preview. Reopen Auto Plan to review the new inputs.", parent=win)
                return
            gui.pm_generate_selected()
            idx = gui.pm_current_index()
            item = gui.pm_items[idx] if idx is not None else None
            if not item or item.get("status") != "Calculated":
                status.configure(text="Generation did not complete; inspect the Project Manager error.")
                return
            status.configure(text="Plan generated. Review Plan, Materials, Checklist and Cleavage tabs.", foreground="#176b3a")
            messagebox.showinfo("Auto Plan", "Existing engine generated the selected project outputs.\nReview the tables and confirm cleavage conditions before use.", parent=win)
        except Exception as exc:
            status.configure(text="Generation failed; no successful result was confirmed.")
            messagebox.showerror("Auto Plan", str(exc), parent=win)

    ttk.Button(buttons, text="Generate Full Plan", command=generate).pack(side="left")
    ttk.Button(buttons, text="Close", command=win.destroy).pack(side="right")
    return win
