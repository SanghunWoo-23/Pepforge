
# =========================================================
# Peptide Design Engine — VERIFIED COLAB UI
# =========================================================
from IPython.display import display, Markdown
import ipywidgets as widgets

target_input = widgets.Textarea(value="DELIKFVRWA\nYYERWFCAA", description="Targets", layout=widgets.Layout(width='650px', height='80px'))
pop_size = widgets.IntSlider(value=200, min=20, max=1000, step=20, description="POP")
gen_max = widgets.IntSlider(value=20, min=1, max=150, step=1, description="GEN")
seed_input = widgets.IntText(value=42, description="Seed")
engine_mode = widgets.Dropdown(options=["NSGA2","GA"], value="NSGA2", description="Engine")
design_mode = widgets.Dropdown(options=["SINGLE","MULTI","BRIDGE"], value="MULTI", description="TargetMode")
bridge_anchor_len = widgets.IntSlider(value=4, min=2, max=10, description="BridgeAnchor")
bridge_require_order = widgets.Checkbox(value=True, description="Bridge A→B")

len_mode = widgets.Dropdown(options=["RANGE","FIX"], value="RANGE", description="LenMode")
fix_len = widgets.IntSlider(value=24, min=8, max=80, description="FixLen")
min_len = widgets.IntSlider(value=18, min=5, max=80, description="MinLen")
max_len = widgets.IntSlider(value=30, min=5, max=120, description="MaxLen")
fix_len_text = widgets.BoundedIntText(value=24, min=8, max=80, description="Fix#")
min_len_text = widgets.BoundedIntText(value=18, min=5, max=80, description="Min#")
max_len_text = widgets.BoundedIntText(value=30, min=5, max=120, description="Max#")
length_count_mode = widgets.Dropdown(options=["TOKEN","RESIDUE","EXPANDED"], value="TOKEN", description="LenCount")
trim_to_length_checkbox = widgets.Checkbox(value=True, description="Trim to length")

use_d = widgets.Checkbox(value=True, description="D-form")
use_non_nat = widgets.Checkbox(value=True, description="Non-natural")
use_tag = widgets.Checkbox(value=True, description="Tag")
tag_types = widgets.SelectMultiple(options=["His6","His8","His10","FLAG","HA","Myc","StrepII","TwinStrep","V5","T7","ALFA","AviTag","SpyTag"], value=["His6"], description="Tags")
use_base_chem = widgets.Checkbox(value=True, description="Base chem")
base_chem_types = widgets.SelectMultiple(options=["Pal","Myr","Stear","Ole","Chol","Nic","Caf","Gal","Ac","Bz","Fmoc","Boc","Succinyl","Maleimide","Azide","Alkyne","DBCO","TCO","Tetrazine","BiotinCap"], value=["Ac"], description="Chem")
use_label = widgets.Checkbox(value=True, description="Label")
label_types = widgets.SelectMultiple(options=["NONE","BIOTIN","FITC","FAM","TAMRA","CY3","CY5","Alexa488","Alexa647","DOTA","NOTA","DFO"], value=["NONE"], description="Labels")
use_cterm_nh2 = widgets.Checkbox(value=True, description="C-term NH2")
force_chemistry_tokens = widgets.Checkbox(value=False, description="Soft-enrich selected chem")
chemistry_bonus_weight = widgets.FloatSlider(value=0.35, min=0.0, max=1.0, step=0.05, description="ChemBonus")
terminal_rules_strict = widgets.Checkbox(value=True, description="Strict terminal rules")

use_linker = widgets.Checkbox(value=True, description="Linker")
linker_mode = widgets.Dropdown(options=["FIX","MIX","AUTO"], value="MIX", description="LinkMode")
fix_linker = widgets.Dropdown(options=["Ahx","PEG4","PEG8","bAla","gAla","AA_G2","AA_G4","AA_GS2","AA_GS4"], value="PEG4", description="FixLink")
linker_types = widgets.SelectMultiple(options=["Ahx","PEG4","PEG8","bAla","gAla","Gly","GG","GGG","GS","GSG","AA_G2","AA_G4","AA_G6","AA_A2","AA_A4","AA_GS2","AA_GS4","AA_GS6","AA_AP"], value=["AA_GS2","AA_G4","PEG4"], description="Linkers")
linker_pos = widgets.Text(value="2,4", description="LinkPos")
max_linkers = widgets.IntSlider(value=2, min=0, max=6, description="MaxLink")
aa_linker_lib = widgets.Checkbox(value=True, description="AA linker lib")
aa_linker_mode = widgets.Dropdown(options=["TOKEN","EXPAND_TO_RESIDUES"], value="TOKEN", description="AALinkMode")

motif_lock = widgets.Checkbox(value=True, description="Motif lock")
locked_motifs = widgets.Text(value="RGD,KLVFF", description="Motifs")
locked_motif_pos = widgets.Text(value="RGD:2;KLVFF:-6", description="MotifPos")
lock_residues = widgets.Text(value="C,W", description="ProtectAA")
dual_min_distance = widgets.IntSlider(value=6, min=0, max=30, description="DualDist")

binder_mode = widgets.Dropdown(options=["BALANCED","AFFINITY_FIRST","DEVELOPABILITY","DUAL_BINDER","CYCLIC_PEPTIDE"], value="BALANCED", description="Binder")
clusters = widgets.IntSlider(value=5, min=1, max=20, description="Clusters")
final_topk = widgets.IntSlider(value=10, min=1, max=100, description="TopK")

docking_stage = widgets.Dropdown(options=["OFF","FINAL_TOP_ONLY","EVERY_N_GENERATIONS"], value="FINAL_TOP_ONLY", description="DockStage")
docking_engine = widgets.Dropdown(options=["NONE","CUSTOM","ROSETTA","VINA","DIFFDOCK"], value="NONE", description="DockEngine")
use_af = widgets.Checkbox(value=False, description="Use AF")
af_lform_only = widgets.Checkbox(value=True, description="AF L-form only")

use_optional_ml = widgets.Checkbox(value=False, description="Optional ML rerank")
ml_rerank_weight = widgets.FloatSlider(value=0.20, min=0.0, max=0.8, step=0.05, description="ML weight")
prepare_pseudodock = widgets.Checkbox(value=False, description="Pseudo-dock FASTA")
receptor_sequence = widgets.Textarea(value="", description="Receptor", placeholder="Paste receptor protein sequence for optional pseudo-docking", layout=widgets.Layout(width='650px', height='90px'))
pseudodock_topk = widgets.IntSlider(value=10, min=1, max=50, description="PseudoTopK")

auto_hotspot = widgets.Checkbox(value=False, description="Auto hotspot")
hotspot_source = widgets.Dropdown(options=["SEQUENCE","PDB"], value="SEQUENCE", description="HotSource")
hotspot_window = widgets.IntSlider(value=6, min=3, max=15, step=1, description="HotWin")
hotspot_topk = widgets.IntSlider(value=5, min=1, max=20, step=1, description="HotTopK")
hotspot_sequence = widgets.Textarea(value="", description="ProteinSeq", placeholder="Paste protein sequence", layout=widgets.Layout(width='650px', height='90px'))
hotspot_pdb_text = widgets.Textarea(value="", description="PDB text", placeholder="Optional: paste PDB text, or upload .pdb file below", layout=widgets.Layout(width='650px', height='100px'))
hotspot_pdb_upload = widgets.FileUpload(accept=".pdb,.ent,.txt", multiple=False, description="Upload PDB file")
hotspot_chain = widgets.Text(value="", description="Chain", placeholder="optional")
hotspot_lock_as_motif = widgets.Checkbox(value=False, description="Lock hotspots")
hotspot_replace_targets = widgets.Checkbox(value=True, description="Use as TARGETS")
hotspot_min_exposure = widgets.FloatSlider(value=0.35, min=0.0, max=1.0, step=0.05, description="MinExpose")
hotspot_binding_weight = widgets.FloatSlider(value=0.80, min=0.0, max=2.0, step=0.05, description="HotWeight")
hotspot_debug_mode = widgets.Checkbox(value=True, description="Hotspot debug / fallback")
hotspot_debug_force_topk = widgets.IntSlider(value=5, min=1, max=20, step=1, description="DebugTopK")
motif_position_mode = widgets.Dropdown(options=["FREE","N_TERM","CENTER","C_TERM"], value="FREE", description="MotifPos")
motif_position_map_text = widgets.Textarea(value="", description="MotifMap", placeholder="KLVFF:CENTER\nHHHHHH:C_TERM", layout=widgets.Layout(width='650px', height='80px'))

def _motif_position_map_from_text(x):
    result = {}
    for line in str(x).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().replace("-", "").replace(" ", "")
        v = v.strip().upper()
        if k and v in ["FREE","N_TERM","CENTER","C_TERM"]:
            result[k] = v
    return result



# ---- Length UI stabilization ----
# Sliders and number boxes are linked so Colab does not treat them as separate values.
widgets.jslink((fix_len, "value"), (fix_len_text, "value"))
widgets.jslink((min_len, "value"), (min_len_text, "value"))
widgets.jslink((max_len, "value"), (max_len_text, "value"))

def _sync_length_widgets(*_):
    """Keep FIX/RANGE UI internally consistent."""
    if len_mode.value == "FIX":
        min_len.value = int(fix_len.value)
        max_len.value = int(fix_len.value)
        min_len.disabled = True
        max_len.disabled = True
        min_len_text.disabled = True
        max_len_text.disabled = True
        fix_len.disabled = False
        fix_len_text.disabled = False
    else:
        min_len.disabled = False
        max_len.disabled = False
        min_len_text.disabled = False
        max_len_text.disabled = False
        fix_len.disabled = True
        fix_len_text.disabled = True
        if int(min_len.value) > int(max_len.value):
            max_len.value = int(min_len.value)

def _on_fix_len_change(change):
    if len_mode.value == "FIX":
        min_len.value = int(fix_len.value)
        max_len.value = int(fix_len.value)

def _on_min_len_change(change):
    if len_mode.value == "RANGE" and int(min_len.value) > int(max_len.value):
        max_len.value = int(min_len.value)

def _on_max_len_change(change):
    if len_mode.value == "RANGE" and int(max_len.value) < int(min_len.value):
        min_len.value = int(max_len.value)

len_mode.observe(_sync_length_widgets, names="value")
fix_len.observe(_on_fix_len_change, names="value")
min_len.observe(_on_min_len_change, names="value")
max_len.observe(_on_max_len_change, names="value")
_sync_length_widgets()

run_button = widgets.Button(description="RUN FINAL PIPELINE", button_style="success")
output = widgets.Output()

fast_mode_button = widgets.Button(description="Fast Mode", button_style="info", tooltip="Quick demo / distribution preset")
paper_mode_button = widgets.Button(description="Paper Mode", button_style="primary", tooltip="Manuscript-oriented preset")
explore_mode_button = widgets.Button(description="Exploration Mode", button_style="warning", tooltip="Chemistry-rich exploration preset")
hotspot_only_button = widgets.Button(description="Hotspot Only Mode", button_style="success", tooltip="Use extracted hotspots as TARGETS without locking them as motifs")

def apply_fast_mode(_=None):
    """Fast demo preset: short, simple, quick."""
    len_mode.value = "RANGE"
    min_len.value = 10
    max_len.value = 12
    fix_len.value = 12
    pop_size.value = 100
    gen_max.value = 8
    final_topk.value = 10
    design_mode.value = "MULTI"
    binder_mode.value = "BALANCED"

    use_d.value = False
    use_non_nat.value = False
    use_linker.value = False
    use_tag.value = False
    use_base_chem.value = False
    use_label.value = False
    use_cterm_nh2.value = True

    motif_lock.value = False
    docking_stage.value = "FINAL_TOP_ONLY"
    docking_engine.value = "NONE"
    use_af.value = False
    use_optional_ml.value = False
    prepare_pseudodock.value = False
    _sync_length_widgets()

def apply_paper_mode(_=None):
    """Paper preset: interpretable, docking-ready, moderate search."""
    len_mode.value = "RANGE"
    min_len.value = 12
    max_len.value = 15
    fix_len.value = 14
    pop_size.value = 200
    gen_max.value = 20
    final_topk.value = 25
    design_mode.value = "BRIDGE"
    binder_mode.value = "BALANCED"

    use_d.value = False
    use_non_nat.value = False
    use_linker.value = True
    use_tag.value = False
    use_base_chem.value = False
    use_label.value = False
    use_cterm_nh2.value = True

    motif_lock.value = True
    docking_stage.value = "FINAL_TOP_ONLY"
    docking_engine.value = "NONE"
    use_af.value = False
    use_optional_ml.value = False
    ml_rerank_weight.value = 0.20
    prepare_pseudodock.value = False
    _sync_length_widgets()

def apply_hotspot_only_mode(_=None):
    """Hotspot-only preset: target-derived hotspot bias without forced motif insertion."""
    len_mode.value = "RANGE"
    min_len.value = 12
    max_len.value = 15
    fix_len.value = 14
    pop_size.value = 200
    gen_max.value = 20
    final_topk.value = 25
    design_mode.value = "MULTI"
    binder_mode.value = "BALANCED"

    # Chemistry kept conservative for paper-friendly direct candidates.
    use_d.value = False
    use_non_nat.value = False
    use_linker.value = False
    use_tag.value = False
    use_base_chem.value = False
    use_label.value = False
    use_cterm_nh2.value = True

    # Motif is intentionally disabled; hotspot is used as target bias only.
    motif_lock.value = False
    locked_motifs.value = ""
    locked_motif_pos.value = ""
    motif_position_mode.value = "FREE"
    motif_position_map_text.value = ""

    # Hotspot-only core settings.
    auto_hotspot.value = True
    hotspot_source.value = "SEQUENCE"
    hotspot_window.value = 6
    hotspot_topk.value = 5
    hotspot_replace_targets.value = True
    hotspot_lock_as_motif.value = False
    hotspot_min_exposure.value = 0.35
    hotspot_binding_weight.value = 0.80

    # Keep validation/export conservative.
    docking_stage.value = "FINAL_TOP_ONLY"
    docking_engine.value = "NONE"
    use_af.value = False
    use_optional_ml.value = False
    prepare_pseudodock.value = False
    _sync_length_widgets()

def apply_exploration_mode(_=None):
    """Exploration preset: chemically diverse candidate generation."""
    len_mode.value = "RANGE"
    min_len.value = 12
    max_len.value = 20
    fix_len.value = 16
    pop_size.value = 300
    gen_max.value = 30
    final_topk.value = 50
    design_mode.value = "BRIDGE"
    binder_mode.value = "BALANCED"

    use_d.value = True
    use_non_nat.value = True
    use_linker.value = True
    use_tag.value = True
    use_base_chem.value = True
    use_label.value = True
    use_cterm_nh2.value = True

    motif_lock.value = True
    docking_stage.value = "FINAL_TOP_ONLY"
    docking_engine.value = "NONE"
    use_af.value = False
    use_optional_ml.value = True
    ml_rerank_weight.value = 0.20
    prepare_pseudodock.value = False

fast_mode_button.on_click(apply_fast_mode)
paper_mode_button.on_click(apply_paper_mode)
explore_mode_button.on_click(apply_exploration_mode)
hotspot_only_button.on_click(apply_hotspot_only_mode)

def _design_mode_to_engine(x):
    if x == "SINGLE":
        return "SINGLE_TARGET"
    if x == "BRIDGE":
        return "BRIDGE_LINKER"
    return "MULTI_TARGET_BINDER"

def _list_from_text(x):
    return [v.strip() for v in str(x).replace("\n", ",").split(",") if v.strip()]

def _targets_from_text(x):
    # Accept newline, comma, semicolon, pipe, or slash as target separators.
    import re
    parts = re.split(r"[\\n,;|/]+", str(x))
    return [list(v.strip().replace("-", "").replace(" ", "")) for v in parts if v.strip()]

def _positions_from_text(x):
    vals = []
    for v in _list_from_text(x):
        try:
            vals.append(int(v))
        except Exception:
            pass
    return vals

def _motif_pos_from_text(x):
    vals = []
    for item in str(x).split(";"):
        if ":" not in item:
            continue
        m, p = item.split(":", 1)
        m = m.strip().replace("-", "").replace(" ", "")
        try:
            pos = int(p.strip())
        except Exception:
            continue
        if m:
            vals.append({"motif": list(m), "pos": pos})
    return vals



def _pdb_text_from_upload():
    """Read uploaded PDB file from Colab FileUpload widget."""
    try:
        if not hotspot_pdb_upload.value:
            return ""
        val = hotspot_pdb_upload.value
        # ipywidgets 7: dict; ipywidgets 8: tuple/list of dict-like items
        if isinstance(val, dict):
            item = next(iter(val.values()))
            content = item.get("content", b"")
        else:
            item = list(val)[0]
            content = item.get("content", b"") if isinstance(item, dict) else getattr(item, "content", b"")
        if isinstance(content, memoryview):
            content = content.tobytes()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return str(content)
    except Exception:
        return ""

def _normalize_length_config(cfg):
    """Normalize length configuration before sending it to the engine."""
    cfg = dict(cfg)
    cfg["FIX_LENGTH"] = int(cfg.get("FIX_LENGTH", 24))
    cfg["MIN_LENGTH"] = int(cfg.get("MIN_LENGTH", 18))
    cfg["MAX_LENGTH"] = int(cfg.get("MAX_LENGTH", 30))
    if cfg.get("LEN_MODE") == "FIX":
        cfg["MIN_LENGTH"] = cfg["FIX_LENGTH"]
        cfg["MAX_LENGTH"] = cfg["FIX_LENGTH"]
    else:
        if cfg["MIN_LENGTH"] > cfg["MAX_LENGTH"]:
            cfg["MIN_LENGTH"], cfg["MAX_LENGTH"] = cfg["MAX_LENGTH"], cfg["MIN_LENGTH"]
    return cfg

def build_config():
    cfg = {
        "TARGETS": _targets_from_text(target_input.value),
        "POP": pop_size.value,
        "GEN": gen_max.value,
        "SEED": seed_input.value,
        "ENGINE_MODE": engine_mode.value,
        "DESIGN_MODE": _design_mode_to_engine(design_mode.value),
        "TARGET_MODE_LABEL": design_mode.value,
        "BRIDGE_ANCHOR_LEN": bridge_anchor_len.value,
        "BRIDGE_REQUIRE_ORDER": bridge_require_order.value,

        "LEN_MODE": len_mode.value,
        "FIX_LENGTH": fix_len.value,
        "MIN_LENGTH": min_len.value,
        "MAX_LENGTH": max_len.value,
        "LENGTH_COUNT_MODE": length_count_mode.value,
        "TRIM_TO_LENGTH": trim_to_length_checkbox.value,

        "USE_D": use_d.value,
        "USE_NON_NAT": use_non_nat.value,
        "USE_TAG": use_tag.value,
        "TAG_TYPES": list(tag_types.value),
        "USE_BASE_CHEM": use_base_chem.value,
        "BASE_CHEM_TYPES": list(base_chem_types.value),
        "USE_LABEL": use_label.value,
        "LABEL_TYPES": list(label_types.value),
        "USE_CTERM_NH2": use_cterm_nh2.value,
        "ENRICH_SELECTED_CHEMISTRY": force_chemistry_tokens.value,
        "CHEMISTRY_BONUS_WEIGHT": chemistry_bonus_weight.value,
        "CHEMISTRY_LONG_TARGET_BALANCE": True,
        "TERMINAL_RULES_STRICT": terminal_rules_strict.value,
        "NTERM_ONLY_CHEM_TAG_LABEL": True,
        "DISALLOW_NTERM_LINKER": True,
        "DISALLOW_CTERM_LINKER": False,

        "USE_LINKER": use_linker.value,
        "LINKER_MODE": linker_mode.value,
        "FIX_LINKER_TYPE": fix_linker.value,
        "LINKER_TYPES": list(linker_types.value),
        "LINKER_POS": _positions_from_text(linker_pos.value),
        "MAX_LINKERS": max_linkers.value,
        "USE_AA_LINKER_LIBRARY": aa_linker_lib.value,
        "LINKER_LENGTH_SELECTION_MODE": aa_linker_mode.value,

        "MOTIF_LOCK": motif_lock.value,
        "LOCKED_MOTIFS": [list(x.replace("-", "").replace(" ", "")) for x in _list_from_text(locked_motifs.value)],
        "LOCKED_MOTIF_POS": _motif_pos_from_text(locked_motif_pos.value),
        "LOCK_RESIDUES": _list_from_text(lock_residues.value),
        "DUAL_MIN_DISTANCE": dual_min_distance.value,

        "BINDER_MODE": binder_mode.value,
        "CLUSTERS": clusters.value,
        "FINAL_TOPK": final_topk.value,
        "DOCKING_STAGE": docking_stage.value,
        "DOCKING_ENGINE": docking_engine.value,
        "USE_REAL_DOCKING": docking_stage.value != "OFF" and docking_engine.value != "NONE",
        "USE_AF": use_af.value,
        "AF_LFORM_ONLY": af_lform_only.value,
        "USE_OPTIONAL_ML": use_optional_ml.value,
        "ML_RERANK_WEIGHT": ml_rerank_weight.value,
        "PREPARE_PSEUDODOCKING_COLAB": prepare_pseudodock.value,
        "RECEPTOR_SEQUENCE": receptor_sequence.value,
        "PSEUDODOCKING_TOPK": pseudodock_topk.value,
        "AUTO_HOTSPOT": auto_hotspot.value,
        "HOTSPOT_SOURCE": hotspot_source.value,
        "HOTSPOT_WINDOW": hotspot_window.value,
        "HOTSPOT_TOPK": hotspot_topk.value,
        "HOTSPOT_SEQUENCE": hotspot_sequence.value,
        "HOTSPOT_PDB_TEXT": _pdb_text_from_upload() or hotspot_pdb_text.value,
        "HOTSPOT_CHAIN": hotspot_chain.value,
        "HOTSPOT_LOCK_AS_MOTIF": hotspot_lock_as_motif.value,
        "HOTSPOT_REPLACE_TARGETS": hotspot_replace_targets.value,
        "HOTSPOT_MIN_EXPOSURE": hotspot_min_exposure.value,
        "HOTSPOT_BINDING_WEIGHT": hotspot_binding_weight.value,
        "HOTSPOT_DEBUG_MODE": hotspot_debug_mode.value,
        "HOTSPOT_DEBUG_FORCE_TOPK": hotspot_debug_force_topk.value,
        "MOTIF_POSITION_MODE": motif_position_mode.value,
        "MOTIF_POSITION_MAP": _motif_position_map_from_text(motif_position_map_text.value),
    }
    return _normalize_length_config(cfg)

def display_ui():
    display(Markdown("## Peptide Design Engine — Final Colab UI"))
    display(widgets.HTML("<b>Preset Modes:</b> use these buttons to quickly apply recommended settings."))
    display(widgets.HBox([fast_mode_button, paper_mode_button, explore_mode_button, hotspot_only_button]))
    tabs = widgets.Tab()
    tabs.children = [
        widgets.VBox([
            target_input,
            widgets.HBox([pop_size, gen_max, seed_input, engine_mode]),
            widgets.HBox([design_mode, bridge_anchor_len, bridge_require_order]),
            widgets.HTML("<b>TargetMode:</b> SINGLE = one target/hotspot bias, MULTI = multiple targets/hotspots, BRIDGE = target-derived anchors/linker design."),
            widgets.HBox([len_mode, fix_len, fix_len_text, min_len, min_len_text, max_len, max_len_text]),
            widgets.HBox([length_count_mode, trim_to_length_checkbox]),
            widgets.HTML("<b>Length:</b> TOKEN mode counts selected chemical/linker/tag/label tokens as construct length; NH2 is excluded. Use RESIDUE for pure amino-acid mer length."),
        ]),
        widgets.VBox([
            widgets.HBox([use_d, use_non_nat, use_cterm_nh2, force_chemistry_tokens, chemistry_bonus_weight, terminal_rules_strict]),
            widgets.HBox([use_tag, tag_types]),
            widgets.HBox([use_base_chem, base_chem_types]),
            widgets.HBox([use_label, label_types]),
        ]),
        widgets.VBox([
            widgets.HBox([use_linker, linker_mode, fix_linker]),
            widgets.HBox([linker_types, linker_pos, max_linkers]),
            widgets.HBox([aa_linker_lib, aa_linker_mode]),
        ]),
        widgets.VBox([
            widgets.HBox([motif_lock, locked_motifs]),
            widgets.HBox([locked_motif_pos, lock_residues, dual_min_distance]),
        ]),
        widgets.VBox([
            widgets.HBox([binder_mode, clusters, final_topk]),
            widgets.HBox([docking_stage, docking_engine, use_af, af_lform_only]),
            widgets.HTML("<b>Optional extensions</b>"),
            widgets.HBox([use_optional_ml, ml_rerank_weight]),
            widgets.HBox([prepare_pseudodock, pseudodock_topk]),
            receptor_sequence,
        ]),
        widgets.VBox([
            widgets.HTML("<b>Automatic hotspot / epitope-like extraction</b><br>Sequence mode: paste ProteinSeq or use Targets as fallback.<br>PDB mode: upload a .pdb file below. Text input is still supported."),
            widgets.HBox([auto_hotspot, hotspot_source, hotspot_window, hotspot_topk]),
            widgets.HBox([hotspot_replace_targets, hotspot_lock_as_motif]),
            widgets.HBox([hotspot_chain, hotspot_min_exposure, hotspot_binding_weight]),
            widgets.HBox([hotspot_debug_mode, hotspot_debug_force_topk]),
            hotspot_sequence,
            hotspot_pdb_text,
            hotspot_pdb_upload,
            widgets.HTML("<b>Motif position control</b>"),
            widgets.HBox([motif_position_mode]),
            motif_position_map_text,
        ]),
    ]
    for i, title in enumerate(["Basic/Length","Chemistry","Linker","Motif/Constraint","Final/Research","Hotspot/Position"]):
        tabs.set_title(i, title)
    display(tabs, run_button, output)

display_ui()
