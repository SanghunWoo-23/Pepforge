# Pepforge

**서열 기반 Hot Spot 분석, 제약 조건 기반 Peptide Design, SPPS 합성 계획을 통합한 peptide 연구 플랫폼**

---

## 개요

**Pepforge**는 peptide 연구에서 필요한 세 가지 핵심 단계를 하나의 로컬 데스크톱 환경에서 연결하기 위해 개발된 통합 연구 소프트웨어이다.

1. **Hot Spot Finder**  
   단백질 서열에서 hotspot 후보 residue 또는 local hotspot region을 탐색하는 sequence-based 분석 모듈이다.

2. **Peptide Design Engine**  
   motif, chemistry option, linker, label, tag, D-amino acid, non-natural amino acid, bridge-style constraint, optional lightweight ML-prior 등을 활용하여 peptide candidate를 생성하는 설계 모듈이다.

3. **SPPS Planner**  
   입력한 peptide sequence를 바탕으로 C-terminal에서 N-terminal 방향의 SPPS 합성 계획표, coupling cocktail, material usage, operation form, printable checklist, branch mode, ML-ready log를 생성하는 합성 계획 모듈이다.

Pepforge는 단순한 peptide sequence generator가 아니라, **단백질 서열 분석 → peptide 후보 설계 → SPPS 합성 계획 → 사용량 계산 → checklist 및 실험 기록**으로 이어지는 design-to-synthesis workflow를 지원하는 것을 목표로 한다.

본 공개판은 연구 프리뷰 및 포트폴리오 목적의 open-source edition으로 설계되었다. 코드를 검토하고, 로컬에서 실행하고, 기능을 확장할 수 있도록 투명성과 재현성을 중심으로 구성되어 있다.

---

## 핵심 개념

일반적인 peptide design workflow는 후보 sequence 생성에서 끝나는 경우가 많다. 그러나 실제 연구에서는 후보 peptide가 합성 가능한지, 어떤 resin과 coupling 조건이 필요한지, modifier나 label이 들어가는지, 시약 사용량이 얼마나 되는지, 실험 기록을 어떻게 남길 것인지까지 고려해야 한다.

Pepforge는 이 문제를 해결하기 위해 다음 기능을 하나의 workflow로 연결한다.

```text
protein sequence
→ hotspot analysis
→ motif 또는 region selection
→ constrained peptide design
→ SPPS planning
→ material usage
→ checklist
→ ML-ready experimental logging
```

Pepforge는 docking engine, molecular dynamics platform, LIMS, 또는 완전 자동 합성 시스템을 대체하려는 도구가 아니다. 대신 peptide 연구자가 **서열 분석, 후보 설계, 합성 계획, 사용량 계산, 실험 기록**을 더 투명하고 일관되게 수행할 수 있도록 돕는 연구용 플랫폼이다.

---

## 주요 모듈

## 1. Hot Spot Finder

Hot Spot Finder는 protein sequence를 입력받아 candidate hotspot residue 또는 local hotspot region을 탐색한다.

### 목적

Hot Spot Finder는 다음 작업을 지원한다.

- peptide design에 사용할 후보 region 탐색
- motif 추출을 위한 residue 후보 선정
- local residue cluster 우선순위화
- 구조 분석 또는 docking 전 sequence-level hypothesis 생성
- Peptide Design Engine에 전달할 motif 또는 constraint 후보 준비

### 출력 형식

Hotspot residue는 N-terminal 기준 1부터 세는 residue number와 amino acid letter를 함께 표시한다.

예:

```text
(14K), (17Y), (19R)
```

의미:

- `14`는 N-terminal 기준 1-based residue position이다.
- `K`는 해당 위치의 amino acid이다.

Local hotspot region은 여러 대표 residue를 함께 표시할 수 있다.

```text
(158W), (161Y), (163Y), (167R), (168R)
```

이는 해당 local window 안에 hotspot-like sequence context를 가진 residue들이 모여 있다는 뜻이다.

### 해석

Hot Spot Finder score는 **상대적 우선순위 신호**이다. 실험적으로 검증된 binding residue나 절대적인 결합 확률로 해석하면 안 된다.

권장 해석:

- 높은 score의 region은 motif 후보 또는 peptide seed로 검토할 수 있다.
- aromatic, charged, polar residue가 모인 local cluster는 interaction 후보 region일 수 있다.
- 구조 정보, docking, conservation, AlphaFold/PDB, 실험 결과와 함께 해석하는 것이 바람직하다.

### 역할 분리

Pepforge에서는 Hot Spot Finder를 독립된 전용 모듈로 유지한다. Peptide Design Engine 내부에 hotspot 계산기를 중복해서 넣기보다는, Hot Spot Finder 결과를 motif 또는 constraint input으로 전달하는 구조가 더 명확하다.

---

## 2. Peptide Design Engine

Peptide Design Engine은 사용자가 지정한 constraint와 chemistry setting을 바탕으로 peptide candidate를 생성한다.

### 주요 기능

- fixed length 또는 random length peptide generation
- multi-target sequence input
- motif constraint
- fixed 또는 random motif placement
- motif preset
- bridge-style constraint
- D-amino acid option
- non-natural amino acid option
- amino-acid-like residue handling
- linker / spacer logic
- N-terminal modifier / label / tag logic
- optional lightweight ML-prior scoring
- full result 및 top-ranked candidate export
- SPPS-ready metadata export

### Motif constraint

Motif는 생성되는 peptide 안에 반드시 포함시키고 싶은 sequence pattern이다.

예:

```text
RGD
EEMQR
KLV
PXXP
```

#### Fixed placement

예:

```text
RGD@1, EEMQR@4
```

12-mer peptide 기준 의미:

```text
position 1-3 = RGD
position 4-8 = EEMQR
```

position은 N-terminal 기준 1부터 센다.

#### Random placement

예:

```text
RGD, EEMQR
```

이 경우 motif는 반드시 포함되지만, 가능한 위치는 자동으로 선택된다.

### Motif hide/show behavior

Motif constraint를 체크 해제하면 다음 UI가 숨겨진다.

- motif preset
- motif input
- motif placement mode
- motif position input
- motif guide text

중요하게, UI만 숨기는 것이 아니라 내부 CONFIG에서도 motif constraint가 꺼진다. 따라서 motif option이 off이면 candidate generation에 motif가 적용되지 않는다.

### Chemistry option behavior

각 chemistry option은 checkbox로 명확히 제어된다. 체크 해제된 option은 candidate generation에 적용되지 않는다.

예:

- linker off: linker-only token이 삽입되지 않는다.
- label off: FITC, Biotin, dye label 등이 적용되지 않는다.
- non-natural off: non-natural residue token이 제외된다.
- D-form off: D-amino acid variant가 제외된다.
- motif off: motif constraint가 제외된다.

### N-terminal modifier와 linker 구분

N-terminal modifier로 허용되는 예:

```text
Ac
Pal
Myr
Biotin
FITC
FAM
TAMRA
CY dyes
```

N-terminal modifier로 랜덤 배치하지 않는 linker-only unit 예:

```text
PEG4
PEG8
AEEA
Ahx
G4S
SMCC
DSS
```

`bAla`와 `gAla`는 linker-only가 아니라 amino-acid-like 또는 non-natural residue 성격으로 볼 수 있으므로, 설정에 따라 core residue pool에서 사용될 수 있다.

### Lightweight ML-prior scoring

Pepforge에는 candidate prioritization을 위한 lightweight ML-prior scaffold가 포함될 수 있다. 이는 validated binding-affinity predictor가 아니라 후보 우선순위화를 돕는 ranking aid이다.

가능한 feature 예:

- peptide length
- charge-related feature
- hydrophobicity-related feature
- aromatic residue content
- motif indicator
- residue composition
- interface-inspired heuristic feature

ML-prior score는 실험적 affinity나 biological activity로 해석하면 안 된다.

---

## 3. SPPS Planner

SPPS Planner는 peptide notation과 synthesis condition을 입력받아 editable SPPS synthesis plan을 생성한다.

예:

```text
Ac-EEMQRR-NH2
```

Core sequence:

```text
EEMQRR
```

Synthesis direction:

```text
R → R → Q → M → E → E → Ac
```

SPPS Planner는 다음 출력을 생성할 수 있다.

- editable synthesis table
- process-ordered material usage table
- operation form
- printable synthesis checklist
- ML-ready log
- CSV/XLSX export

---

## SPPS sequence parsing

지원 notation 예:

```text
EEMQRR
EEMQRR-NH2
-EEMQRR-NH2
Ac-EEMQRR-NH2
AcEEMQRR-NH2
FITC-EEMQRR-NH2
Biotin-EEMQRR-NH2
```

parser는 다음을 분리한다.

- N-terminal modifier
- core peptide sequence
- C-terminal modifier
- synthesis direction
- SPPS unit

중요하게 `EEMQRR-NH2`는 앞에 인위적인 `-`를 붙이지 않아도 core peptide로 인식되어야 한다.

---

## Resin-dependent synthesis logic

### 2-CTC / Trityl resin

2-CTC 또는 trityl-type resin에서는 다음 기본 로직을 사용한다.

- swell solvent = DCM
- loading은 regular coupling과 분리
- loading amino acid는 loading solution으로 준비
- default loading cocktail solvent = DCM-rich condition
- practical default = 90% DCM / 10% DMF
- DIPEA/DIEA는 base로 처리
- resin 자체에 대한 initial Fmoc deprotection은 필요하지 않음

### Amide / Rink / Wang resin

Amide, Rink, Wang 계열 Fmoc resin에서는 다음 기본 로직을 사용한다.

- swell solvent = DMF
- Fmoc resin logic 적용
- initial Fmoc deprotection 가능
- regular Fmoc cycle은 DMF 중심
- row별 조건은 사용자가 editable table에서 수정 가능

---

## Coupling cocktail concept

Pepforge는 coupling을 각각 따로 녹여 넣는 방식이 아니라 **하나의 coupling cocktail**로 취급한다.

Coupling step 구성:

```text
amino acid 또는 modifier
+ coupling reagent 1
+ coupling reagent 2 / catalyst / additive
+ coupling base
+ coupling cocktail solvent
→ one coupling solution/cocktail
→ add to resin
```

따라서 planner는 다음 field를 중심으로 사용한다.

```text
Coupling cocktail solvent
Coupling cocktail volume (mL)
```

Material Usage에서는 각 material 사용량을 따로 계산한다.

- amino acid amount
- coupling reagent amount
- additive/catalyst amount
- base amount
- coupling cocktail solvent volume

즉 실험 동작은 하나의 cocktail로 표현하고, 사용량 계산은 각 시약별로 분리한다.

---

## Standard Fmoc cycle

일반 intermediate Fmoc-AA cycle:

```text
deprotection ×2
→ DMF wash ×6
→ coupling cocktail
→ DMF wash ×2
→ next cycle
```

---

## Last Fmoc-AA coupling

마지막 unit이 Fmoc-protected amino acid라면:

```text
pre-coupling deprotection
→ DMF wash ×6
→ last Fmoc-AA coupling cocktail
→ DMF wash ×2
→ final Fmoc deprotection
→ final wash: DMF ×3 / DCM ×3
→ optional MeOH wash
```

Final deprotection 이후에는 DMF wash ×6 cycle을 다시 추가하지 않는다.

---

## Final non-Fmoc modifier logic

Ac, chemical modifier, tag, label은 non-Fmoc final operation으로 취급한다.

예:

```text
Ac
FITC
Biotin
FAM
TAMRA
CY dyes
Pal
Myr
DOTA
NOTA
```

이 경우:

```text
modifier coupling
→ no post-modifier Fmoc deprotection
→ final wash: DMF ×3 / DCM ×3
→ optional MeOH wash
```

Modifier를 붙이기 전에 Fmoc 제거가 필요하다면, 그 deprotection은 modifier row가 아니라 직전 Fmoc-AA step에 귀속된다.

---

## N-terminal acetylation

표시 unit:

```text
Ac
```

실제 사용 시약:

```text
Acetic anhydride / Ac2O
```

기준값:

```text
MW = 102.09 g/mol
density = 1.08 g/mL
```

계산식:

```text
Ac2O volume (mL) = resin scale (mmol) × Ac eq × 102.09 / 1000 / 1.08
```

---

## Branch mode

Pepforge는 linear mode를 기본으로 유지하면서 branch mode를 지원한다.

기본값:

```text
Branch mode OFF
```

Branch mode ON 시 설정 가능 항목:

- branch point
- branch arm sequence
- protecting group
- branch deprotection condition

예:

```text
main sequence: Ac-EEMQKRR-NH2
branch point: K5
branch arm: RGD
protecting group: Mtt
```

Branch mode는 Mtt, ivDde, Dde, Alloc 등 orthogonal protecting group을 사용하는 side-chain branching workflow를 지원하기 위한 기능이다.

---

## Output files

Pepforge는 다음과 같은 output을 생성할 수 있다.

```text
hotspot_top_display_only.csv
candidate_results_full.csv
candidate_results_top.csv
spps_editable_plan.csv
material_usage_table.csv
operation_form.csv
printable_synthesis_checklist.csv
spps_ml_ready_log.csv
spps_plan.xlsx
```

실제 파일명은 module과 configuration에 따라 일부 달라질 수 있다.

---

## Repository Structure

권장 public GitHub repository structure는 다음과 같다.

```text
Pepforge/
├── README.md
├── LICENSE
├── requirements.txt
├── environment.yml
├── INSTALL_BUILD_TOOLS_AND_BUILD.bat
├── RUN_SOURCE_DEV.bat
├── main_launcher.py
├── assets/
│   ├── Pepforge_Icon.png
│   └── Pepforge_Icon.ico
├── apps/
│   ├── hotspot_finder/
│   ├── peptide_design_engine/
│   └── spps_planner_app/
├── suite_gui/
├── peptiforg_core/
├── docs/
│   ├── HOTSPOT_METHOD.md
│   ├── PEPTIDE_ENGINE_METHOD.md
│   ├── SPPS_METHOD.md
│   ├── SPPS_PROCESS_RULES.md
│   ├── SPPS_COUPLING_COCKTAIL_RULE.md
│   ├── SPPS_BRANCH_MODE.md
│   ├── INSTALLATION_GUIDE.md
│   └── RELEASE_NOTES.md
├── tests/
│   ├── test_spps_parser_contract.py
│   ├── test_spps_cycle_contract.py
│   └── test_peptide_engine_constraints.py
├── installer/
│   └── Pepforge_Setup.iss
├── examples/
│   ├── example_hotspot_input.txt
│   ├── example_peptide_design_config.csv
│   ├── example_spps_sequence.txt
│   └── example_outputs/
├── MANUAL_KO.txt
├── MANUAL_EN.txt
└── FEATURE_DIFFERENTIATION_ANALYSIS.txt
```

### Directory Description

- `main_launcher.py`  
  Hot Spot Finder, Peptide Design Engine, SPPS Planner를 실행하기 위한 main desktop launcher이다.

- `apps/hotspot_finder/`  
  Sequence-based hotspot analysis module이다.

- `apps/peptide_design_engine/`  
  Motif, chemistry, constraint, optional ML-prior logic을 포함한 peptide candidate generation module이다.

- `apps/spps_planner_app/`  
  Editable SPPS planning, material usage calculation, coupling cocktail handling, branch mode, checklist export, ML-ready logging을 담당하는 module이다.

- `suite_gui/`  
  공통 desktop GUI component와 module-level GUI wrapper를 포함한다.

- `peptiforg_core/`  
  module 간 공유되는 core utility, data structure, reusable logic을 포함한다.

- `assets/`  
  icon, visual asset, installer-related graphical resource를 포함한다.

- `docs/`  
  module별 method note와 technical documentation을 포함한다.

- `tests/`  
  parser, SPPS cycle, peptide design constraint test를 포함한다.

- `installer/`  
  Windows installer configuration file을 포함한다.

- `examples/`  
  public-safe example input과 output을 포함한다.

- `MANUAL_KO.txt`, `MANUAL_EN.txt`  
  한글 및 영어 사용자 매뉴얼이다.

- `FEATURE_DIFFERENTIATION_ANALYSIS.txt`  
  Pepforge의 기능, 용도, 기존 tool category와의 차이점, limitation을 정리한 비교 분석 문서이다.

### Repository Notes

1. README의 repository structure는 실제 업로드된 project structure와 가능한 한 일치해야 한다.
2. README에 적힌 파일이 실제로 없다면 placeholder file을 만들거나 README에서 해당 항목을 제거하는 것이 좋다.
3. private data, protected beta file, password hash, API key, token, raw synthesis log, internal laboratory record는 public GitHub에 업로드하지 않는다.
4. public GitHub repository에는 GitHub Public version을 사용한다.
5. Protected Beta version은 내부 installer 생성 및 laboratory/team distribution 용도로만 사용한다.

---

## Installation

Pepforge root folder에서 다음 파일을 실행한다.

```text
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

성공하면 installer가 다음 위치에 생성된다.

```text
installer/output/Pepforge_Setup_v0.1.0.exe
```

Development mode에서는 다음을 사용할 수 있다.

```text
RUN_SOURCE_DEV.bat
```

또는:

```text
python main_launcher.py
```

---

## GitHub upload recommendation

Public GitHub에는 다음을 업로드한다.

- source code
- README.md
- MANUAL_KO.txt
- MANUAL_EN.txt
- docs/
- examples/
- tests/
- build scripts
- installer script

Public GitHub에 업로드하지 말아야 할 것:

- protected beta files
- password hash
- private dataset
- internal synthesis logs
- API keys
- GitHub tokens
- build artifacts
- runtime logs

---

## Limitations

1. Hotspot result는 sequence-derived prioritization signal이며 실험적으로 검증된 binding residue가 아니다.
2. ML-prior scoring은 validated binding predictor가 아니라 candidate ranking aid이다.
3. SPPS calculation은 실험 전 반드시 trained user가 검토해야 한다.
4. Reagent form, salt form, hydrate state, concentration, purity, density는 vendor와 lot에 따라 달라질 수 있다.
5. 실험실 protocol은 기관과 연구실에 따라 달라질 수 있으며, Pepforge의 조건은 editable planning default이다.
6. Branch mode planning은 orthogonal protecting group compatibility에 대한 expert review가 필요하다.
7. Pepforge는 synthesis success, yield, purity, solubility, biological activity를 보장하지 않는다.

---

## Author

Woosanghun Woo  
Department of Biochemical Engineering  
Tech University of Korea

---

## Disclaimer

Pepforge는 research, education, planning purpose로 제공된다. 본 소프트웨어는 biological activity, binding affinity, synthesis success, yield, purity, experimental safety를 보장하지 않는다. 사용자는 모든 design, calculation, reagent condition, experimental procedure를 기관 및 실험실 안전 기준에 따라 직접 검증해야 한다.
