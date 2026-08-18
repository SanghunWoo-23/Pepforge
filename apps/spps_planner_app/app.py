from __future__ import annotations
import re
import pandas as pd
import streamlit as st
from spps_planner.database import load_compounds, save_compounds, audit_compound_database
from spps_planner.engine import (
    PlanInput,
    generate_step_matrix,
    generate_detailed_operations,
    generate_materials,
    generate_step_reagent_plan,
    generate_printable_checklist,
    generate_cleavage_cocktail,
    cleavage_cocktail_presets,
    recommend_cleavage_preset,
    validate_plan,
    plan_summary,
)
from spps_planner.export import export_excel, export_csvs
from spps_planner.ml import train_supervised, detect_anomalies
from spps_planner.user_paths import user_data_file, user_models_dir, user_outputs_dir
from spps_planner.version import VERSION_NAME, DATA_VERSION


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "")).strip("_")
    return slug[:80] or "spps_run"


st.set_page_config(page_title=VERSION_NAME, layout="wide")
st.title(VERSION_NAME)
st.caption(f"Solid phase peptide synthesis calculator. Data: {DATA_VERSION}. Sequence parsing, reagent planning, wash checklist, project export, cleavage cocktail, and validation warnings.")

with st.sidebar:
    st.header("Input")
    seq = st.text_input("Sequence", "")
    resin = st.selectbox("Resin family", ["Amide", "CTC/Trityl"])
    scale = st.number_input("Resin scale (mmol)", min_value=0.0, value=400.0, step=10.0)
    loading = st.number_input("Resin loading rate (mmol/g)", min_value=0.01, value=0.8, step=0.05)
    st.subheader("Stoichiometry")
    coupling_eq = st.number_input("Default AA coupling eq", min_value=0.0, value=5.0, step=0.5)
    auto_short = st.checkbox("Auto short peptide rule: 1–5 mer = 2 eq", value=True)
    short_eq = st.number_input("Short peptide AA eq", min_value=0.0, value=2.0, step=0.5)
    ac_eq = st.number_input("N-term chemical/label/tag eq", min_value=0.0, value=3.0, step=0.5)
    coupling_repeats = st.number_input("Default AA coupling repeat", min_value=1, value=1, step=1)
    modifier_repeats = st.number_input("Default N-term modifier repeat", min_value=1, value=1, step=1)
    st.subheader("Chemistry defaults")
    coupling_reagent = st.selectbox("Coupling reagent", ["DIC", "HBTU", "HATU", "HCTU", "TBTU", "TSTU", "TNTU", "PyBOP", "PyBrOP", "PyClocK", "COMU", "DCC", "EDC-HCl", "DEPBT", "Ghosez reagent", "", "Other"], index=0)
    if coupling_reagent == "Other":
        coupling_reagent = st.text_input("Custom coupling reagent", "")
    catalyst = st.text_input("Catalyst/additive", "HOBt")
    base = st.text_input("Base", "")
    solvent = st.text_input("Reaction solvent", "DMF")
    st.subheader("2-CTC loading")
    loading_aa_eq = st.number_input("2-CTC loading AA eq", min_value=0.0, value=2.0, step=0.5)
    loading_diea_eq = st.number_input("2-CTC loading DIEA eq", min_value=0.0, value=4.0, step=0.5)
    tfa_factor = st.number_input("TFA factor for Amide resin", min_value=0.0, value=10.0, step=0.5)
    st.subheader("Cleavage cocktail")
    preset_options = cleavage_cocktail_presets()["preset"].tolist() + ["CUSTOM"]
    cleavage_preset = st.selectbox("Cocktail preset", preset_options, index=0)
    cleavage_eq_override = st.number_input("Cleavage cocktail eq override (0 = auto)", min_value=0.0, value=0.0, step=1.0)
    cleavage_tfa_percent = st.number_input("TFA % v/v", min_value=0.0, max_value=100.0, value=95.0, step=0.5)
    cleavage_tis_percent = st.number_input("TIS % v/v", min_value=0.0, max_value=100.0, value=2.5, step=0.5)
    cleavage_water_percent = st.number_input("Water % v/v", min_value=0.0, max_value=100.0, value=2.5, step=0.5)
    cleavage_reserve_mL = st.number_input("Minimum total cocktail volume reserve (mL, 0 = eq-based only)", min_value=0.0, value=0.0, step=0.1)
    cleavage_components_text = st.text_area("Custom cocktail components", value="", height=70, help="Only used when filled. Example: TFA=92.5;TIS=2.5;Water=2.5;EDT=2.5. Set a component to 0 or omit it to exclude.")
    overrides = st.text_area("Manual step overrides", value="", height=120, help="Examples: unit=FITC; reagent_eq=2; base=DIEA or step=3; coupling_repeat=2")

inp = PlanInput(
    sequence=seq,
    resin=resin,
    scale_mmol=scale,
    resin_loading_mmol_g=loading,
    coupling_eq=coupling_eq,
    ac_eq=ac_eq,
    default_coupling_repeats=int(coupling_repeats),
    default_modifier_repeats=int(modifier_repeats),
    default_coupling_reagent=coupling_reagent,
    default_catalyst=catalyst,
    default_base=base,
    default_reaction_solvent=solvent,
    tfa_factor=tfa_factor,
    cleavage_tfa_percent=cleavage_tfa_percent,
    cleavage_tis_percent=cleavage_tis_percent,
    cleavage_water_percent=cleavage_water_percent,
    cleavage_eq_override=cleavage_eq_override,
    cleavage_preset=cleavage_preset,
    cleavage_components_text=cleavage_components_text,
    cleavage_reserve_mL=cleavage_reserve_mL,
    loading_aa_eq=loading_aa_eq,
    loading_diea_eq=loading_diea_eq,
    auto_short_peptide_eq=auto_short,
    short_peptide_coupling_eq=short_eq,
    step_overrides_text=overrides,
)

tabs = st.tabs(["Summary", "Plan", "Synthesis Form", "Raw Materials", "Cleavage Cocktail", "Validation", "DB Audit", "DB Editor", "Data Log", "ML Lab"])

with tabs[0]:
    try:
        summary = plan_summary(inp)
        st.dataframe(pd.DataFrame([summary]), use_container_width=True)
        outdir = user_outputs_dir() / f"{_safe_slug(seq)}_{_safe_slug(resin)}_{int(scale)}mmol"
        if st.button("Generate CSV + XLSX outputs"):
            export_csvs(inp, outdir)
            export_excel(inp, outdir / "spps_plan.xlsx")
            st.success(f"Saved: {outdir}")
    except Exception as e:
        st.error(str(e))

with tabs[1]:
    try:
        st.subheader("Excel-like synthesis plan")
        st.dataframe(generate_step_matrix(inp), use_container_width=True, height=450)
        st.subheader("Step reagent plan")
        st.dataframe(generate_step_reagent_plan(inp), use_container_width=True, height=450)
    except Exception as e:
        st.error(str(e))

with tabs[2]:
    try:
        st.subheader("Wash-by-wash synthesis form")
        st.dataframe(generate_detailed_operations(inp), use_container_width=True, height=700)
        st.subheader("Printable checklist")
        st.dataframe(generate_printable_checklist(inp), use_container_width=True, height=350)
    except Exception as e:
        st.error(str(e))

with tabs[3]:
    try:
        st.subheader("Total raw material use")
        st.dataframe(generate_materials(inp), use_container_width=True, height=700)
    except Exception as e:
        st.error(str(e))

with tabs[4]:
    try:
        st.subheader("Cleavage cocktail calculator")
        rec = recommend_cleavage_preset(inp)
        st.info(f"Auto recommendation: {rec.get('preset')} — {rec.get('reason')}")
        st.dataframe(generate_cleavage_cocktail(inp), use_container_width=True, height=350)
        st.subheader("Available cleavage cocktail presets")
        st.dataframe(cleavage_cocktail_presets(), use_container_width=True, height=300)
    except Exception as e:
        st.error(str(e))

with tabs[5]:
    try:
        st.subheader("Validation warnings")
        vdf = validate_plan(inp)
        st.dataframe(vdf, use_container_width=True, height=500)
        if (vdf.get("level") == "ERROR").any():
            st.error("Blocking validation issue found.")
        elif (vdf.get("level") == "WARNING").any():
            st.warning("Non-blocking warnings found. Review before bench use.")
        else:
            st.success("No blocking issue detected by automated checks.")
    except Exception as e:
        st.error(str(e))

with tabs[6]:
    try:
        st.subheader("Database audit")
        st.dataframe(audit_compound_database(), use_container_width=True, height=600)
    except Exception as e:
        st.error(str(e))

with tabs[7]:
    st.subheader("Compound DB editor")
    df = load_compounds()
    edited = st.data_editor(df, use_container_width=True, height=650, num_rows="dynamic")
    if st.button("Save compound DB"):
        save_compounds(edited)
        st.success("Saved data/compounds.csv")

with tabs[8]:
    st.subheader("Add actual run data")
    uploaded = st.file_uploader("Upload actual run CSV/XLSX", type=["csv", "xlsx"])
    log_path = user_data_file("actual_runs.csv")
    if uploaded:
        new = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        st.dataframe(new, use_container_width=True)
        if st.button("Append uploaded rows to actual_runs.csv"):
            old = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()
            pd.concat([old, new], ignore_index=True).to_csv(log_path, index=False, encoding="utf-8-sig")
            st.success("Appended actual run data")
    st.subheader("Current actual_runs.csv")
    if log_path.exists():
        st.dataframe(pd.read_csv(log_path), use_container_width=True)

with tabs[9]:
    st.subheader("ML Lab")
    st.write("Use after actual_runs.csv has target columns such as yield_percent, purity_percent, actual_dmf_mL, or failed.")
    log_path = user_data_file("actual_runs.csv")
    if log_path.exists():
        df = pd.read_csv(log_path)
        st.dataframe(df, use_container_width=True)
        target = st.selectbox("Target column", df.columns.tolist() if len(df.columns) else [])
        task = st.selectbox("Task", ["regression", "classification"])
        if st.button("Train model") and target:
            try:
                metrics = train_supervised(log_path, target, user_models_dir() / f"{target}_{task}.joblib", task=task)
                st.success(metrics)
            except Exception as e:
                st.error(str(e))
        if st.button("Run anomaly detection"):
            try:
                out = user_outputs_dir() / "actual_runs_anomaly.csv"
                result = detect_anomalies(log_path, out)
                st.dataframe(result, use_container_width=True)
                st.success(f"Saved {out}")
            except Exception as e:
                st.error(str(e))
