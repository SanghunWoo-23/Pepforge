from __future__ import annotations

PROJECT_SCHEMA_NOTE = """
Pepforge workflow mode uses a lightweight project.json file.
The schema is intentionally simple so each module can remain independently executable.

Core transfer points:
1. input_sequence -> Hot Spot Finder
2. selected_hotspots -> Peptide Design Engine
3. selected_candidates -> SPPS Planner
4. output_files -> final project/session record
""".strip()

SELECTED_HOTSPOT_COLUMNS = [
    "region_start", "region_end", "sequence", "hotspot_score", "record_name", "note"
]

SELECTED_CANDIDATE_COLUMNS = [
    "candidate_id", "sequence", "core_sequence", "modifications", "rank", "score_total", "note"
]
