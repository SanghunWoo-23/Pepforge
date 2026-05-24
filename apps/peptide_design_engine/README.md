# Peptide Design Engine

A Colab-first peptide design framework for chemistry-aware peptide candidate generation, hotspot-guided target bias, motif-position control, docking-readiness classification, and structured export for downstream validation.

---

## Overview

Peptide Design Engine generates, filters, ranks, and exports peptide candidates under biochemical and structural constraints.

The framework is designed to support:

- interactive Colab-based peptide design
- single / multi / bridge target modes
- fixed or ranged peptide length control
- chemistry-aware peptide construction
- automatic hotspot-like fragment extraction from protein sequence or PDB text
- functional motif insertion and motif-position control
- docking-readiness classification
- structured CSV / FASTA / manifest export
- optional analysis plots for manuscript figures

This tool does **not** perform molecular docking, binding energy calculation, molecular dynamics simulation, or experimental validation. It prepares candidate peptides and structured outputs for downstream validation workflows.

---

## Core Concept

```text
target / sequence / PDB input
        ↓
optional hotspot extraction
        ↓
target-derived design bias
        ↓
peptide candidate generation
        ↓
chemistry / motif / linker constraints
        ↓
scoring and filtering
        ↓
docking-readiness classification
        ↓
CSV / FASTA / manifest export
        ↓
optional analysis figures
```

---

## Key Features

### 1. Colab-first interactive UI

The Colab interface provides selectable parameters and preset modes.

Preset modes:

| Preset | Purpose |
|---|---|
| Fast Mode | quick demo and fast testing |
| Paper Mode | manuscript-oriented candidate generation |
| Exploration Mode | chemistry-rich exploratory search |
| Hotspot Only Mode | hotspot-derived TARGETS without forced motif insertion |

---

### 2. Target modes

The UI exposes three target/design modes:

| Mode | Meaning |
|---|---|
| SINGLE | single target or single hotspot-bias design |
| MULTI | multiple targets or multiple extracted hotspots |
| BRIDGE | bridge/linker design using target-derived anchors |

When a full protein sequence or PDB text is used with Auto Hotspot enabled, extracted hotspot-like fragments can be used as TARGETS.

---

### 3. Chemistry-aware peptide design

Supported design elements include:

- canonical L-form residues
- D-form residues
- noncanonical residues
- amino-acid linkers
- chemical linkers
- tags
- labels
- chemical modification tokens
- C-terminal amide option

Modified candidates are preserved and classified rather than silently discarded.

---

### 4. Hotspot-guided target bias

The optional hotspot module can extract hotspot-like fragments from:

1. protein sequence using sliding-window heuristic scoring
2. PDB text using a lightweight C-alpha neighbor-based surface-exposure proxy

Extracted hotspot-like fragments can be used as TARGETS for peptide design.

Important terminology:

```text
PDB hotspot extraction uses a SASA-like surface-exposure proxy.
It is not a formal SASA calculation and is not a binding-site predictor.
```

---

### 5. Hotspot and motif are different

This distinction is central to the engine.

```text
HOTSPOT = automatically extracted target-derived reference
MOTIF   = user-defined sequence to insert or lock into the peptide
```

Hotspot Only Mode keeps them separated:

```text
AUTO_HOTSPOT = ON
HOTSPOT_REPLACE_TARGETS = ON
HOTSPOT_LOCK_AS_MOTIF = OFF
MOTIF_LOCK = OFF
```

This means extracted hotspots guide candidate generation but are not forcibly inserted into every peptide.

---

### 6. Motif-position control

User-defined motifs can be placed using:

```text
FREE
N_TERM
CENTER
C_TERM
```

Example:

```text
KLVFF:CENTER
HHHHHH:C_TERM
RGD:N_TERM
```

---

### 7. Docking-readiness classification

Candidates are classified into downstream modeling routes.

| Level | Meaning |
|---|---|
| DIRECT_LFORM_DOCKING_READY | standard L-form peptide suitable for direct docking workflows |
| PARAMETERIZED_DOCKING_READY | requires residue/linker/chemistry parameterization |
| PARAMETERIZATION_HEAVY | requires more complex topology/modeling |
| BLOCKED_UNSUPPORTED_TOKEN | contains unsupported tokens |

---

### 8. Structured outputs

Typical outputs include:

```text
results_top.csv
results_full.csv
docking_ready_candidates.csv
docking_modeling_manifest.json
docking_surrogate_sequences.fasta
extracted_hotspots.csv
pseudodocking_index.csv
```

Hotspot-specific interpretability columns include:

```text
target_hotspot_sequences
target_hotspot_source
hotspot_used_as_targets
hotspot_peptide_map
best_hotspot
```

---

## Run in Google Colab

Preconfigured notebook:

https://colab.research.google.com/drive/1QOrzWUR6AK0MoTtk7WnPzVv3F2sJIiVR

### GitHub Colab Launcher

```python
from getpass import getpass
import os
import shutil
import subprocess
import sys

USERNAME = "SanghunWoo-23"
REPO = "peptide-design-engine"
BRANCH = "main"
LOCAL_DIR = "/content/peptide-design-engine"

token = getpass("GitHub token: ")

if os.path.exists(LOCAL_DIR):
    shutil.rmtree(LOCAL_DIR)

repo_url = f"https://oauth2:{token}@github.com/{USERNAME}/{REPO}.git"

print("Cloning repository...")
result = subprocess.run(
    ["git", "clone", "--depth", "1", "--branch", BRANCH, repo_url, LOCAL_DIR],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    safe_error = result.stderr.replace(token, "[TOKEN_HIDDEN]")
    print("Clone failed.")
    print(safe_error)
    raise RuntimeError("GitHub clone failed")

os.chdir(LOCAL_DIR)

requirements_path = os.path.join(LOCAL_DIR, "requirements.txt")

if os.path.exists(requirements_path):
    print("Installing requirements...")
    install_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", requirements_path],
        capture_output=True,
        text=True
    )

    if install_result.returncode != 0:
        print("Requirements installation failed.")
        print(install_result.stderr)
        raise RuntimeError("pip install failed")
else:
    print("requirements.txt not found. Skipping installation.")

print("Loading Colab engine...")
exec(open("Colab/Ultimate_Peptide_Final_Engine.py", encoding="utf-8").read(), globals())
exec(open("Colab/Ultimate_Peptide_Final_UI.py", encoding="utf-8").read(), globals())
exec(open("Colab/Ultimate_Peptide_Final_Run.py", encoding="utf-8").read(), globals())

print("Peptide Design Engine loaded.")
```

---

## Optional Colab analysis cell

After running the design pipeline, paste and run the code in:

```text
Colab_Analysis_Cell.py
```

It generates:

```text
score_distribution.png
length_distribution.png
docking_readiness_category.png
hotspot_match_distribution.png
top_hotspots.png
analysis_results.zip
```

---

## Python CLI

Basic run:

```bash
python Python/peptide_cli.py --target EGFR --top-n 10
```

Hotspot-only preset with protein sequence:

```bash
python Python/peptide_cli.py \
  --preset hotspot_only \
  --hotspot-sequence "YOUR_PROTEIN_SEQUENCE"
```

PDB hotspot mode:

```bash
python Python/peptide_cli.py \
  --preset hotspot_only \
  --hotspot-source PDB \
  --hotspot-pdb-file target.pdb
```

Target mode:

```bash
python Python/peptide_cli.py \
  --target-mode SINGLE
```

Available target modes:

```text
SINGLE
MULTI
BRIDGE
```

---

## Recommended experiments

For manuscript-oriented comparison:

```text
1. Hotspot OFF baseline
2. Sequence hotspot design
3. PDB hotspot design
```

Compare:

- peptide length distribution
- total score distribution
- docking-readiness categories
- hotspot-peptide matching
- top candidate chemistry composition

---

## Scope and limitations

This tool is designed for:

- peptide candidate generation
- target-derived design bias
- chemistry-aware peptide representation
- motif and linker design
- docking-readiness classification
- downstream validation preparation

This tool does not perform:

- molecular docking
- binding affinity prediction
- formal SASA calculation
- molecular dynamics simulation
- experimental validation

---

## Publication Status

A manuscript describing this framework is currently in preparation. Publication may require additional benchmarking and validation.

---

## License

MIT License


## Hotspot output note

When `Auto hotspot` is enabled, extracted target hotspot sequences are reported in the output.

Important output columns/files:

```text
target_hotspot_sequences
hotspot_source_sequence_used
hotspot_peptide_map
best_hotspot
hotspot_peptide_pairs.csv
```

If `ProteinSeq` is empty in the Colab UI, the engine can use the sequence pasted in `Targets` as the sequence source for hotspot extraction.


## Length UI stability

The Colab UI includes synchronized slider/number controls for peptide length.

In `FIX` mode:

```text
MIN_LENGTH = MAX_LENGTH = FIX_LENGTH
```

This prevents conflicting UI values during fixed-length peptide generation.


## RESIDUE length mode

Default length mode is now `RESIDUE`.

This means:

```text
FIX_LENGTH = amino-acid residue count
C-terminal NH2 = terminal modification, not an amino acid
```

Example:

```text
FIX_LENGTH = 12
USE_CTERM_NH2 = True
```

Output should contain 12 amino-acid residues plus optional `NH2`.

Additional output columns:

```text
residue_length
expanded_length
token_length_sum
```


## Final length and chemistry semantics

Default length mode is `TOKEN`.

```text
TOKEN   = amino-acid residues + selected chemical/linker/tag/label tokens
RESIDUE = amino-acid residues only
EXPANDED = expanded peptide-like length where available
```

`NH2` is treated as a C-terminal modification and is excluded from length counting.

Chemical, linker, label, and tag features are only introduced when the corresponding UI option is enabled. They are not hard-forced by default. The optional enrichment setting is a soft design bias, not a mandatory insertion rule.


## Terminal topology rules

Default final topology:

```text
chemical / tag / label = N-terminal only
linker = internal / middle only
NH2 = C-terminal modification
```

`Soft-enrich selected chem` is not a hard forcing mode. It only helps selected chemical/linker/tag/label options appear and remain in ranked candidates when those options are enabled.


## PDB file upload and hotspot output

Colab supports PDB hotspot extraction through a `.pdb` file upload widget in the `Hotspot/Position` tab.

When `Auto hotspot` is enabled, the top results include explicit target-hotspot mapping columns:

```text
binding_target_hotspot
peptide_to_target_hotspot
all_target_hotspots_used
hotspot_status
target_hotspot_sequences
hotspot_peptide_map
best_hotspot
```

If `HOTSPOT_SOURCE = PDB` but no PDB file/text is provided, the engine falls back to sequence-based hotspot extraction when a protein sequence is available.


## Hotspot debug mode

If `AUTO_HOTSPOT` is ON but no hotspots are extracted, enable `Hotspot debug fallback`.

This produces diagnostic hotspot windows and saves:

```text
hotspot_debug_visualization.csv
hotspot_peptide_pairs.csv
```

These files show the hotspot sequence, source, start/end residue positions, and peptide-hotspot relationship.

## Long-target chemistry balance

For long protein sequence targets, target/hotspot scoring may dominate and chemical/label features may disappear from top candidates. The engine includes long-target chemistry balancing so selected chemical/linker/tag/label options are less likely to be lost during ranking.

This is not hard forcing.


## Hotspot region output

Top results include the target-derived hotspot region used as design reference:

```text
binding_target_hotspot_sequence
binding_target_hotspot_start
binding_target_hotspot_end
binding_target_hotspot_range
binding_target_hotspot_chain
binding_target_hotspot_source
```

Example:

```text
binding_target_hotspot_sequence = ACDEFG
binding_target_hotspot_range = A:125-132
```

This is a design-referenced hotspot region, not proof of physical binding.

---

## Desktop GUI / EXE UI 추가

이 패키지에는 Colab식 데스크톱 UI가 추가되어 있다.

```bash
python Python/desktop_gui.py
```

Windows에서는 다음 파일을 실행할 수 있다.

```bat
run_desktop_gui.bat
```

GUI EXE 빌드는 다음 스크립트를 사용한다.

```bat
build\build_desktop_gui_exe.bat
```

생성 파일:

```text
dist\PeptideDesignEngine_GUI.exe
```

자세한 내용은 `DESKTOP_GUI_EXE_MANUAL_KR.md`를 참고한다.


## Final Branded Installer

See `START_HERE_FINAL_BRANDED_INSTALLER_KR.md` for Windows installer build instructions.
