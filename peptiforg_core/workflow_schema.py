from __future__ import annotations

PROJECT_SCHEMA_NOTE = """
Pepforge workflow mode uses a lightweight project.json file.
The schema is intentionally simple so each module can remain independently executable.

Core transfer points:
1. input_sequence -> Hot Spot Finder
2. selected_hotspots -> Peptide Design Engine
3. selected_candidates -> Peptide Structure Builder
4. candidate structures -> SPPS Planner
5. structures + target -> Docking Workbench / external validation
6. output_files + candidate manifests -> final project/session record
""".strip()

SELECTED_HOTSPOT_COLUMNS = [
    "region_start", "region_end", "sequence", "hotspot_score", "record_name",
    "secondary_structure", "beta_edge_candidate", "beta_edge_evidence",
    "beta_edge_backbone_pairing_atoms", "beta_edge_local_strand_axis_xyz", "beta_edge_register_status", "note"
]

SELECTED_CANDIDATE_COLUMNS = [
    "candidate_id", "sequence", "core_sequence", "modifications", "rank", "score_total", "pareto_rank", "manifest", "note"
]
