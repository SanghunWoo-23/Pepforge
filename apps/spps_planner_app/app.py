from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from spps_planner.database import load_compounds, save_compounds, DATA_DIR
from spps_planner.engine import PlanInput, generate_step_matrix, generate_detailed_operations, generate_materials, plan_summary
from spps_planner.export import export_excel, export_csvs
from spps_planner.ml import train_supervised, detect_anomalies

st.set_page_config(page_title="SPPS Python Planner", layout="wide")
st.title("SPPS Python Planner")
st.caption("Excel-like field input + CSV/XLSX export + ML-ready data management")

with st.sidebar:
    st.header("Input")
    seq = st.text_input("Sequence", "Ac-EEMQRR-NH2")
    resin = st.selectbox("Resin family", ["Amide", "CTC/Trityl"])
    scale = st.number_input("Resin scale (mmol)", min_value=0.0, value=400.0, step=10.0)
    loading = st.number_input("Resin loading rate (mmol/g)", min_value=0.01, value=0.8, step=0.05)
    coupling_eq = st.number_input("Coupling eq", min_value=0.0, value=5.0, step=0.5)
    ac_eq = st.number_input("Ac/DIEA eq", min_value=0.0, value=3.0, step=0.5)
    inp = PlanInput(sequence=seq, resin=resin, scale_mmol=scale, resin_loading_mmol_g=loading, coupling_eq=coupling_eq, ac_eq=ac_eq)

tabs = st.tabs(["Summary", "Synthesis Form", "Raw Materials", "DB Editor", "Data Log", "ML Lab"])

with tabs[0]:
    summary = plan_summary(inp)
    st.dataframe(pd.DataFrame([summary]), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Step matrix")
        st.dataframe(generate_step_matrix(inp), use_container_width=True)
    with c2:
        st.subheader("Export")
        outdir = Path("outputs") / f"{seq.replace('-', '_')}_{resin.replace('/', '-')}_{int(scale)}mmol"
        if st.button("Generate CSV + XLSX outputs"):
            export_csvs(inp, outdir)
            export_excel(inp, outdir / "spps_plan.xlsx")
            st.success(f"Saved: {outdir}")

with tabs[1]:
    st.subheader("Wash-by-wash synthesis form")
    st.dataframe(generate_detailed_operations(inp), use_container_width=True, height=650)

with tabs[2]:
    st.subheader("Raw material use")
    st.dataframe(generate_materials(inp), use_container_width=True, height=650)

with tabs[3]:
    st.subheader("Compound DB editor")
    df = load_compounds()
    edited = st.data_editor(df, use_container_width=True, height=650, num_rows="dynamic")
    if st.button("Save compound DB"):
        save_compounds(edited)
        st.success("Saved data/compounds.csv")

with tabs[4]:
    st.subheader("Add actual run data")
    uploaded = st.file_uploader("Upload actual run CSV/XLSX", type=["csv", "xlsx"])
    log_path = DATA_DIR / "actual_runs.csv"
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

with tabs[5]:
    st.subheader("ML Lab")
    st.write("Use after actual_runs.csv has target columns such as yield_percent, purity_percent, actual_dmf_mL, or failed.")
    log_path = DATA_DIR / "actual_runs.csv"
    if log_path.exists():
        df = pd.read_csv(log_path)
        st.dataframe(df, use_container_width=True)
        target = st.selectbox("Target column", df.columns.tolist() if len(df.columns) else [])
        task = st.selectbox("Task", ["regression", "classification"])
        if st.button("Train model") and target:
            try:
                metrics = train_supervised(log_path, target, Path("models") / f"{target}_{task}.joblib", task=task)
                st.success(metrics)
            except Exception as e:
                st.error(str(e))
        if st.button("Run anomaly detection"):
            try:
                out = Path("outputs") / "actual_runs_anomaly.csv"
                result = detect_anomalies(log_path, out)
                st.dataframe(result, use_container_width=True)
                st.success(f"Saved {out}")
            except Exception as e:
                st.error(str(e))
