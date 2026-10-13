from __future__ import annotations

"""Shared Native Result Viewer used by PSB and Docking Workbench.

The viewer consumes Pepforge's shared docking-result contract plus optional
native mechanics/trajectory follow-up records.  It intentionally keeps score,
quality and provenance visible together so an experimental native score is not
mistaken for measured affinity or production-MD evidence.
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from peptiforg_core.native_result_review_v1 import build_pose_review, build_pose_comparison, build_trajectory_review, build_cluster_medoid_comparison, build_gain_loss_review, build_cluster_medoid_montage
from peptiforg_core.native_result_compare_v1 import compare_poses, trajectory_cluster_summary, export_review_report, export_multi_pose_matrix, export_trajectory_cluster_rmsd_matrix
from peptiforg_core.native_result_interpretation_v1 import interpret_native_result, export_native_result_interpretation


RESULT_VIEW_VERSION = "0.6.0"


def _as_records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return list(value.to_dict(orient="records"))
        except Exception:
            return []
    if isinstance(value, list):
        return [dict(x) for x in value if isinstance(x, dict)]
    return []


def _short(value: Any, limit: int = 180) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SharedNativeResultPanel(ttk.Frame):
    """Reusable, scroll-safe viewer for normalized Pepforge native results."""

    def __init__(
        self,
        master,
        *,
        open_path_callback: Callable[[str | Path], Any] | None = None,
        rerun_followup_callback: Callable[[str], Any] | None = None,
        title: str = "Unified Native Results",
    ):
        super().__init__(master)
        self.open_path_callback = open_path_callback
        self.rerun_followup_callback = rerun_followup_callback
        self._pose_paths: dict[str, str] = {}
        self._last_output_dir = ""
        self._all_evidence: list[dict[str, Any]] = []
        self._all_followups: list[dict[str, Any]] = []
        self._selected_pose_id = ""
        self._normalized: dict[str, Any] = {}
        self._compare_a = ""
        self._compare_b = ""
        self._interaction_filter = tk.StringVar(value="ALL")
        self._trajectory_frame_var = tk.IntVar(value=0)
        self._trajectory_frame_max = 0
        self._build(title)

    def _build(self, title: str) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(header, text=title).pack(side="left")
        ttk.Label(
            header,
            text="Shared view: pose → interaction → mechanics → trajectory → provenance",
        ).pack(side="left", padx=12)
        ttk.Button(header, text="Open selected pose", command=self.open_selected_pose).pack(side="right", padx=3)
        ttk.Button(header, text="3D review", command=self.open_selected_review).pack(side="right", padx=3)
        self.rerun_btn = ttk.Button(header, text="Run follow-up for selected", command=self.rerun_selected_followup)
        self.rerun_btn.pack(side="right", padx=3)
        ttk.Button(header, text="Show all", command=self.show_all).pack(side="right", padx=3)
        ttk.Button(header, text="Open result folder", command=self.open_result_folder).pack(side="right", padx=3)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=4, pady=(0,2))
        ttk.Label(controls, text="Interaction filter").pack(side="left")
        self.interaction_filter_box = ttk.Combobox(controls, textvariable=self._interaction_filter, state="readonly", width=18,
            values=("ALL","hydrogen_bond","hydrophobic","salt_bridge","pi_pi","cation_pi","clash","van_der_Waals","weak_C_H_O_N"))
        self.interaction_filter_box.pack(side="left", padx=(4,10))
        self.interaction_filter_box.bind("<<ComboboxSelected>>", lambda _e: self._render_detail_rows())
        ttk.Button(controls, text="Set compare A", command=self.set_compare_a).pack(side="left", padx=2)
        ttk.Button(controls, text="Set compare B", command=self.set_compare_b).pack(side="left", padx=2)
        ttk.Button(controls, text="Open A/B comparison", command=self.open_pose_comparison).pack(side="left", padx=2)
        ttk.Button(controls, text="Compare metrics", command=self.show_pose_comparison_metrics).pack(side="left", padx=2)
        ttk.Button(controls, text="Export review report", command=self.export_review_report).pack(side="left", padx=2)
        ttk.Button(controls, text="Interpret result", command=self.show_interpretation).pack(side="left", padx=2)
        ttk.Button(controls, text="Gain/Loss 3D", command=self.open_gain_loss_review).pack(side="left", padx=2)
        ttk.Button(controls, text="Multi-pose matrix", command=self.export_multi_pose_matrix).pack(side="left", padx=2)
        self.compare_label = ttk.Label(controls, text="A: -   B: -")
        self.compare_label.pack(side="left", padx=8)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        self.summary_tree = self._tree_tab("Summary", ("item", "value", "interpretation"), (180, 220, 520))
        self.pose_tree = self._tree_tab(
            "Poses",
            ("rank", "pose", "engine", "score", "quality", "contacts", "clashes", "pdb"),
            (60, 120, 190, 110, 80, 80, 70, 360),
        )
        self.interaction_tree = self._tree_tab(
            "Interactions",
            ("pose", "interaction", "target", "peptide", "distance_A", "geometry", "level", "note"),
            (110, 120, 150, 150, 90, 110, 100, 360),
        )
        self.mechanics_tree = self._tree_tab(
            "Mechanics",
            ("model", "item", "value", "unit", "interpretation"),
            (90, 180, 150, 70, 520),
        )
        self.trajectory_tree = self._tree_tab(
            "Trajectory",
            ("model", "frame", "rmsd_A", "rg_A", "cluster", "interpretation"),
            (90, 70, 90, 90, 80, 520),
        )
        self.compare_tree = self._tree_tab(
            "Compare",
            ("metric", "value", "interpretation"),
            (220, 180, 620),
        )
        self.interpretation_tree = self._tree_tab(
            "Interpretation",
            ("section", "item", "detail"),
            (150, 320, 620),
        )
        self.provenance_tree = self._tree_tab(
            "Provenance",
            ("item", "value", "note"),
            (200, 360, 480),
        )
        traj_controls = ttk.Frame(self.notebook.nametowidget(self.trajectory_tree.winfo_parent()))
        traj_controls.grid(row=2, column=0, sticky="ew", pady=(2,0))
        ttk.Button(traj_controls, text="Open selected frame", command=self.open_selected_trajectory_frame).pack(side="left", padx=2)
        ttk.Button(traj_controls, text="Open medoid frame", command=self.open_medoid_frame).pack(side="left", padx=2)
        ttk.Button(traj_controls, text="Compare cluster medoids", command=self.open_cluster_medoid_comparison).pack(side="left", padx=2)
        ttk.Button(traj_controls, text="Cluster RMSD matrix", command=self.export_cluster_rmsd_matrix).pack(side="left", padx=2)
        ttk.Button(traj_controls, text="Medoid montage", command=self.open_cluster_medoid_montage).pack(side="left", padx=2)
        ttk.Label(traj_controls, text="Frame").pack(side="left", padx=(10,2))
        self.trajectory_scale = ttk.Scale(traj_controls, from_=0, to=0, orient="horizontal", command=self._on_trajectory_scale, length=220)
        self.trajectory_scale.pack(side="left", padx=2)
        self.trajectory_frame_label = ttk.Label(traj_controls, text="0")
        self.trajectory_frame_label.pack(side="left", padx=4)
        ttk.Button(traj_controls, text="Open slider frame", command=self.open_slider_trajectory_frame).pack(side="left", padx=2)
        self.pose_tree.bind("<<TreeviewSelect>>", self._on_pose_selected)

    def _tree_tab(self, label: str, columns: tuple[str, ...], widths: tuple[int, ...]):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=label)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=55, stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    @staticmethod
    def _clear_tree(tree) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def clear(self) -> None:
        for tree in (
            self.summary_tree,
            self.pose_tree,
            self.interaction_tree,
            self.mechanics_tree,
            self.trajectory_tree,
            self.compare_tree,
            self.interpretation_tree,
            self.provenance_tree,
        ):
            self._clear_tree(tree)
        self._pose_paths.clear()
        self._last_output_dir = ""
        self._all_evidence = []
        self._all_followups = []
        self._selected_pose_id = ""
        self._normalized = {}
        self._compare_a = ""
        self._compare_b = ""
        self._trajectory_frame_max = 0
        if hasattr(self, "trajectory_scale"):
            self.trajectory_scale.configure(to=0); self.trajectory_scale.set(0)
        self.compare_label.configure(text="A: -   B: -") if hasattr(self, "compare_label") else None

    def load_result(
        self,
        normalized: dict[str, Any] | None,
        *,
        followups: list[dict[str, Any]] | None = None,
        source: str = "",
        output_dir: str | Path | None = None,
    ) -> None:
        self.clear()
        normalized = dict(normalized or {})
        self._normalized = normalized
        followups = [dict(x) for x in (followups or []) if isinstance(x, dict)]
        if output_dir:
            self._last_output_dir = str(Path(output_dir).expanduser())

        poses = _as_records(normalized.get("poses"))
        evidence = _as_records(normalized.get("evidence"))
        guard = normalized.get("claim_guard") or "Docking output is structural-search evidence, not measured affinity."

        summary = [
            ("status", normalized.get("status", ""), "Shared docking-result status."),
            ("engine", normalized.get("engine", ""), "Engine that produced the pose search."),
            ("engine_version", normalized.get("engine_version", ""), "Recorded engine implementation version."),
            ("evidence_grade", normalized.get("evidence_grade", ""), "Evidence grade is kept separate from experimental validation."),
            ("pose_count", len(poses), "Number of normalized pose records."),
            ("interaction_rows", len(evidence), "Geometry-aware interaction evidence rows."),
            ("followup_count", len(followups), "Native mechanics/trajectory follow-up records."),
            ("claim_guard", guard, "Scientific interpretation guard."),
        ]
        for row in summary:
            self.summary_tree.insert("", "end", values=tuple(_short(x) for x in row))

        for p in poses:
            pid = str(p.get("pose_id") or f"pose_{p.get('pose_rank','')}")
            pdb = str(p.get("pose_pdb") or "")
            if pdb:
                self._pose_paths[pid] = pdb
            self.pose_tree.insert(
                "", "end", iid=pid if pid and not self.pose_tree.exists(pid) else None,
                values=(
                    p.get("pose_rank", ""), pid, p.get("engine", ""), p.get("engine_score", ""),
                    p.get("quality_status", ""), p.get("contact_count", ""), p.get("clash_count", ""), _short(pdb, 360),
                ),
            )

        self._all_evidence = evidence
        self._all_followups = followups
        self._render_detail_rows()
        self._render_interpretation()

        provenance_rows = [
            ("viewer_version", RESULT_VIEW_VERSION, "Shared PSB / Docking Workbench result-view implementation."),
            ("source", source, "UI or pipeline that supplied this result."),
            ("contract_version", normalized.get("contract_version", ""), "Shared docking-result contract version."),
            ("engine", normalized.get("engine", ""), "Docking engine provenance."),
            ("evidence_grade", normalized.get("evidence_grade", ""), "Does not imply experimental validation."),
            ("claim_guard", guard, "Visible scientific claim boundary."),
        ]
        for row in provenance_rows:
            self.provenance_tree.insert("", "end", values=tuple(_short(x, 480) for x in row))

    def _followup_pose_id(self, item: dict[str, Any]) -> str:
        model = item.get("model_rank")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        selected = payload.get("selected_pose") or item.get("selected_pose") or {}
        pid = str(selected.get("pose_id") or "")
        if model and pid and not pid.startswith(f"m{int(model):02d}_"):
            pid = f"m{int(model):02d}_{pid}"
        return pid

    def _render_detail_rows(self) -> None:
        for tree in (self.interaction_tree, self.mechanics_tree, self.trajectory_tree):
            self._clear_tree(tree)
        selected = self._selected_pose_id
        interaction_filter = self._interaction_filter.get() if hasattr(self, "_interaction_filter") else "ALL"
        for e in self._all_evidence:
            if selected and str(e.get("pose_id") or "") != selected:
                continue
            if interaction_filter != "ALL" and str(e.get("interaction") or "") != interaction_filter:
                continue
            self.interaction_tree.insert(
                "", "end",
                values=(
                    e.get("pose_id", ""), e.get("interaction", ""), e.get("target_residue", ""),
                    e.get("peptide_residue", ""), e.get("distance_A", ""), e.get("geometry_status", ""),
                    e.get("evidence_level", ""), _short(e.get("note", ""), 360),
                ),
            )
        for idx, item in enumerate(self._all_followups, 1):
            follow_pose_id = self._followup_pose_id(item)
            if selected and follow_pose_id and follow_pose_id != selected:
                continue
            model = item.get("model_rank") or idx
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
            selected_pose = payload.get("selected_pose") or {}
            mechanics = payload.get("native_mechanics") or {}
            traj = mechanics.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
            mech_quality = mechanics.get("quality_gate") or {}
            traj_quality = traj.get("quality_gate") or {}
            mech_rows = [
                ("selected_pose", follow_pose_id or selected_pose.get("pose_id", ""), "-", "Selected docking pose used for this follow-up."),
                ("docking_quality", selected_pose.get("quality_status", ""), "-", "Quality status from shared docking result."),
                ("mechanics_status", mechanics.get("status", item.get("status", "")), "-", "Experimental Pepforge native mechanics; not production MD."),
                ("mechanics_quality", mech_quality.get("status", ""), "-", "Geometry/mechanics quality gate."),
                ("initial_reduced_score", mechanics.get("initial_reduced_score", ""), "reduced", "Internal reduced score; not physical energy."),
                ("final_reduced_score", mechanics.get("final_reduced_score", ""), "reduced", "Internal reduced score; not physical energy."),
                ("trajectory_quality", traj_quality.get("status", ""), "-", "Descriptive trajectory-analysis quality gate."),
                ("frame_count", traj.get("frame_count", ""), "frames", "Saved coordinate frames."),
            ]
            for name, value, unit, interpretation in mech_rows:
                self.mechanics_tree.insert("", "end", values=(model, name, _short(value), unit, interpretation))
            frame_records = item.get("frames")
            if frame_records is None:
                frame_records = payload.get("frames")
            frame_record_list = _as_records(frame_records)
            for fr in frame_record_list:
                self.trajectory_tree.insert(
                    "", "end", values=(model, fr.get("frame", ""), fr.get("rmsd_A", ""), fr.get("rg_A", ""), fr.get("cluster", ""),
                    _short(fr.get("interpretation", "Descriptive native-mechanics frame; no equilibrium claim."), 520)),
                )
        frame_values=[]
        for iid in self.trajectory_tree.get_children():
            vals=self.trajectory_tree.item(iid, "values")
            try: frame_values.append(int(float(vals[1])))
            except Exception: pass
        self._trajectory_frame_max=max(frame_values) if frame_values else 0
        if hasattr(self, "trajectory_scale"):
            self.trajectory_scale.configure(to=max(0,self._trajectory_frame_max))
            if int(round(float(self.trajectory_scale.get()))) > self._trajectory_frame_max:
                self.trajectory_scale.set(self._trajectory_frame_max)

    def _on_pose_selected(self, _event=None) -> None:
        selected = self.pose_tree.selection()
        self._selected_pose_id = selected[0] if selected else ""
        self._render_detail_rows()
        self._render_interpretation()
        self._render_selection_provenance()

    def _render_selection_provenance(self) -> None:
        for iid in list(self.provenance_tree.get_children()):
            values = self.provenance_tree.item(iid, "values")
            if values and str(values[0]) == "selected_pose":
                self.provenance_tree.delete(iid)
        if not self._selected_pose_id:
            return
        self.provenance_tree.insert("", "end", values=("selected_pose", self._selected_pose_id, "Active viewer filter; downstream tabs show matching evidence/follow-up where available."))

    def show_all(self) -> None:
        self._selected_pose_id = ""
        try:
            self.pose_tree.selection_remove(self.pose_tree.selection())
        except Exception:
            pass
        self._render_detail_rows()
        self._render_interpretation()
        self._render_selection_provenance()

    def selected_pose_id(self) -> str:
        return self._selected_pose_id

    def rerun_selected_followup(self) -> None:
        pid = self._selected_pose_id
        if pid and self.rerun_followup_callback:
            self.rerun_followup_callback(pid)

    def open_selected_pose(self) -> None:
        selected = self.pose_tree.selection()
        if not selected:
            return
        pid = selected[0]
        path = self._pose_paths.get(pid)
        if path and self.open_path_callback:
            self.open_path_callback(path)

    def open_result_folder(self) -> None:
        if self._last_output_dir and self.open_path_callback:
            self.open_path_callback(self._last_output_dir)

    def _review_dir(self) -> Path:
        base = Path(self._last_output_dir).expanduser() if self._last_output_dir else Path.cwd() / "pepforge_review"
        out = base / "viewer_review"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def open_selected_review(self) -> None:
        pid = self._selected_pose_id
        if not pid:
            return
        filt = self._interaction_filter.get()
        visible = None if filt == "ALL" else [filt]
        try:
            art = build_pose_review(self._normalized, self._review_dir(), pose_id=pid, visible_interactions=visible)
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return

    def set_compare_a(self) -> None:
        if self._selected_pose_id:
            self._compare_a = self._selected_pose_id
            self._refresh_compare_label()

    def set_compare_b(self) -> None:
        if self._selected_pose_id:
            self._compare_b = self._selected_pose_id
            self._refresh_compare_label()

    def _refresh_compare_label(self) -> None:
        if hasattr(self, "compare_label"):
            self.compare_label.configure(text=f"A: {self._compare_a or '-'}   B: {self._compare_b or '-'}")

    def open_pose_comparison(self) -> None:
        if not self._compare_a or not self._compare_b or self._compare_a == self._compare_b:
            return
        try:
            art = build_pose_comparison(self._normalized, self._review_dir(), pose_a=self._compare_a, pose_b=self._compare_b)
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return

    def _selected_followup_for_pose(self) -> dict[str, Any] | None:
        pid = self._selected_pose_id
        for item in self._all_followups:
            if not pid or self._followup_pose_id(item) == pid:
                return item
        return self._all_followups[0] if self._all_followups else None

    def open_selected_trajectory_frame(self) -> None:
        sel = self.trajectory_tree.selection()
        if not sel:
            return
        vals = self.trajectory_tree.item(sel[0], "values")
        if len(vals) < 2:
            return
        try:
            frame = int(float(vals[1]))
        except Exception:
            return
        follow = self._selected_followup_for_pose()
        if not follow:
            return
        try:
            art = build_trajectory_review(follow, self._review_dir(), frame=frame)
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return

    def open_medoid_frame(self) -> None:
        follow = self._selected_followup_for_pose()
        if not follow:
            return
        try:
            art = build_trajectory_review(follow, self._review_dir(), frame=None)
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return

    def open_cluster_medoid_comparison(self) -> None:
        follow=self._selected_followup_for_pose()
        if not follow: return
        try:
            art=build_cluster_medoid_comparison(follow,self._review_dir())
            if self.open_path_callback: self.open_path_callback(art["pml"])
        except Exception:
            return

    def _on_trajectory_scale(self, value) -> None:
        try: frame=max(0,min(self._trajectory_frame_max,int(round(float(value)))))
        except Exception: frame=0
        self._trajectory_frame_var.set(frame)
        if hasattr(self, "trajectory_frame_label"):
            self.trajectory_frame_label.configure(text=str(frame))

    def open_slider_trajectory_frame(self) -> None:
        follow=self._selected_followup_for_pose()
        if not follow: return
        try:
            art=build_trajectory_review(follow,self._review_dir(),frame=int(self._trajectory_frame_var.get()))
            if self.open_path_callback: self.open_path_callback(art["pml"])
        except Exception:
            return

    def show_pose_comparison_metrics(self) -> None:
        self._clear_tree(self.compare_tree)
        if not self._compare_a or not self._compare_b or self._compare_a == self._compare_b:
            return
        try:
            data=compare_poses(self._normalized,self._compare_a,self._compare_b)
        except Exception:
            return
        geo=data.get("geometry") or {}; inter=data.get("interactions") or {}
        rows=[
            ("pose_A",self._compare_a,"Comparison reference A."),("pose_B",self._compare_b,"Comparison reference B."),
            ("score_A",data.get("score_a"),"Native engine score; not affinity."),("score_B",data.get("score_b"),"Native engine score; not affinity."),
            ("ligand_RMSD_A",geo.get("ligand_rmsd_A"),"Peptide heavy-atom RMSD after common receptor-backbone superposition."),
            ("peptide_centroid_shift_A",geo.get("peptide_centroid_shift_A"),"Centroid displacement after receptor alignment."),
            ("contact_jaccard",inter.get("contact_jaccard"),"Overlap of categorized residue-pair interaction annotations."),
            ("shared_interactions",inter.get("shared_interactions"),"Interaction annotations present in both poses."),
            ("gained_in_B",len(inter.get("gained_in_b") or []),"Annotations present in B but not A; not energetic gain."),
            ("lost_from_A",len(inter.get("lost_from_a") or []),"Annotations present in A but not B; not energetic loss."),
        ]
        for row in rows: self.compare_tree.insert("","end",values=tuple(_short(x,620) for x in row))
        for prefix, changes in (("GAIN",inter.get("gained_in_b") or []),("LOSS",inter.get("lost_from_a") or [])):
            for x in changes:
                text=f"{x.get('interaction','')} | {x.get('target_residue','')} ↔ {x.get('peptide_residue','')}"
                self.compare_tree.insert("","end",values=(prefix,text,"Categorical contact change only."))
        try: self.notebook.select(self.notebook.nametowidget(self.compare_tree.winfo_parent()))
        except Exception: pass

    def export_review_report(self) -> None:
        try:
            art=export_review_report(self._normalized,self._all_followups,self._review_dir()/"report",pose_a=self._compare_a,pose_b=self._compare_b)
            if self.open_path_callback: self.open_path_callback(art["markdown"])
        except Exception:
            return

    def _render_interpretation(self) -> None:
        if not hasattr(self, "interpretation_tree"):
            return
        self._clear_tree(self.interpretation_tree)
        data = interpret_native_result(self._normalized, self._all_followups, selected_pose_id=self._selected_pose_id)
        headline = [
            ("Summary", "pose", data.get("pose_id") or "-"),
            ("Summary", "quality", data.get("quality_status") or "UNKNOWN"),
            ("Summary", "contacts / clashes", f"{data.get('contact_count',0)} / {data.get('clash_count',0)}"),
        ]
        for row in headline:
            self.interpretation_tree.insert("", "end", values=row)
        for section, key in (("Strength", "strengths"), ("Warning", "warnings"), ("Next action", "next_actions"), ("Supported", "supported_interpretation"), ("Not supported", "not_supported")):
            for idx, item in enumerate(data.get(key) or [], 1):
                self.interpretation_tree.insert("", "end", values=(section, idx, _short(item, 620)))
        self.interpretation_tree.insert("", "end", values=("Boundary", "claim_guard", _short(data.get("claim_guard"), 620)))

    def show_interpretation(self) -> None:
        self._render_interpretation()
        try:
            self.notebook.select(self.notebook.nametowidget(self.interpretation_tree.winfo_parent()))
        except Exception:
            pass
        try:
            art = export_native_result_interpretation(self._normalized, self._all_followups, self._review_dir() / "interpretation", selected_pose_id=self._selected_pose_id)
            if self.open_path_callback:
                self.open_path_callback(art["markdown"])
        except Exception:
            return

    def open_gain_loss_review(self) -> None:
        if not self._compare_a or not self._compare_b or self._compare_a == self._compare_b:
            return
        try:
            art = build_gain_loss_review(self._normalized, self._review_dir(), pose_a=self._compare_a, pose_b=self._compare_b)
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return

    def export_multi_pose_matrix(self) -> None:
        try:
            art = export_multi_pose_matrix(self._normalized, self._review_dir())
            if self.open_path_callback:
                self.open_path_callback(art["json"])
        except Exception:
            return

    def export_cluster_rmsd_matrix(self) -> None:
        follow = self._selected_followup_for_pose()
        if not follow:
            return
        try:
            art = export_trajectory_cluster_rmsd_matrix(follow, self._review_dir())
            if self.open_path_callback:
                self.open_path_callback(art["csv"])
        except Exception:
            return

    def open_cluster_medoid_montage(self) -> None:
        follow = self._selected_followup_for_pose()
        if not follow:
            return
        try:
            art = build_cluster_medoid_montage(follow, self._review_dir())
            if self.open_path_callback:
                self.open_path_callback(art["pml"])
        except Exception:
            return


__all__ = ["RESULT_VIEW_VERSION", "SharedNativeResultPanel"]
