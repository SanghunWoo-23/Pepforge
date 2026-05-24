# Pepforge

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Python-lightgrey)
![Status](https://img.shields.io/badge/Status-Research%20Prototype-orange)
![License](https://img.shields.io/badge/License-MIT-green)

**Pepforge**는 peptide 관련 작업을 위해 만든 모듈형 연구 지원 프로그램이다. 핵심 흐름은 다음 세 가지다.

```text
Hot Spot Finder
Peptide Design Engine
SPPS Planner
```

Pepforge는 각 기능을 따로 실행하는 **Standalone Mode**와, 분석 결과를 설계와 합성 계획으로 이어주는 **Workflow Mode**를 모두 지원하도록 구성되어 있다.

```text
Standalone Mode
- 각 기능을 독립 실행

Workflow Mode
- Hot Spot Finder → Peptide Design Engine → SPPS Planner
- project.json + CSV 기반 추적
```

현재 Pepforge는 연구 지원 및 포트폴리오 목적의 오픈소스/베타 프로젝트다. 실험적으로 검증된 peptide discovery platform이 아니라, peptide 분석·설계·SPPS 계획을 구조화해서 돕는 computational workflow suite로 보는 것이 정확하다.

---

## 1. 프로젝트 목적

Peptide 연구는 보통 한 단계로 끝나지 않는다.

실제 흐름은 대략 다음과 같다.

```text
어느 서열 구간이 중요할까?
      ↓
어떤 peptide 후보를 만들 수 있을까?
      ↓
그 후보를 실제로 합성하려면 어떻게 계획해야 할까?
      ↓
시약과 solvent는 얼마나 필요할까?
      ↓
결과를 어떻게 기록하고 다음 실험/ML에 활용할까?
```

Pepforge는 이 흐름을 하나의 프로그램 구조로 묶기 위해 만들었다.

```text
Input sequence or target information
        ↓
Hot Spot Finder
        ↓
Peptide Design Engine
        ↓
SPPS Planner
        ↓
CSV/XLSX output, synthesis log, future ML-ready record
```

---

## 2. 주요 모듈

### 2.1 Hot Spot Finder

Hot Spot Finder는 peptide 또는 protein-like sequence에서 잠재적으로 중요한 구간을 탐색하는 모듈이다.

용도:

- hotspot-like region 탐색,
- motif 중심 서열 확인,
- local window scoring,
- downstream design에 사용할 후보 구간 선정,
- 가설 생성용 sequence inspection.

이 결과는 실험적 증명이 아니라 computational indicator로 해석해야 한다.

---

### 2.2 Peptide Design Engine

Peptide Design Engine은 constraint-aware peptide candidate generator 및 optimizer 성격의 모듈이다.

지원 방향:

- fixed/random length candidate generation,
- multi-target design concept,
- bridge/linker-oriented design,
- D-form residue option,
- non-natural amino acid option,
- linker/tag/label/terminal chemical option,
- candidate ranking,
- diversity-aware final selection,
- CSV export.

이 모듈은 structure predictor가 아니며, binding affinity나 biological activity를 보장하지 않는다.

---

### 2.3 SPPS Planner

SPPS Planner는 solid-phase peptide synthesis 계획을 정리하기 위한 모듈이다.

지원 방향:

- peptide sequence parsing,
- resin type별 planning,
- resin scale 입력,
- reagent estimation,
- solvent estimation,
- wash-by-wash synthesis form,
- cleavage-related planning field,
- CSV/XLSX export,
- future ML-ready synthesis log.

실험실 SOP, 안전 지침, 전문가 검토를 대체하지 않는다.

---

## 3. Standalone Mode

각 기능은 독립적으로 실행할 수 있다.

```text
Pepforge
├── Hot Spot Finder
├── Peptide Design Engine
└── SPPS Planner
```

Standalone Mode가 필요한 경우:

```text
서열 분석만 하고 싶을 때
이미 target region이 있어서 설계만 하고 싶을 때
이미 peptide sequence가 있어서 SPPS planning만 하고 싶을 때
```

---

## 4. Workflow Mode

Workflow Mode는 각 모듈을 project/session 단위로 연결한다.

```text
Pepforge_Project_YYYYMMDD_HHMM/
├── project.json
├── input/
├── hotspot/
├── design/
├── spps/
└── logs/
```

목적은 단순 자동화가 아니라 **추적성(traceability)**이다.

예시:

```text
Original sequence
      ↓
selected hotspot region
      ↓
design candidate list
      ↓
selected candidate
      ↓
SPPS synthesis plan
```

이 구조 덕분에 나중에 “왜 이 후보를 합성하려 했는지”를 project 폴더 안에서 다시 확인할 수 있다.

---

## 5. 실행 방법

### Python 버전

```bash
git clone https://github.com/YOUR_USERNAME/Pepforge.git
cd Pepforge
pip install -r requirements.txt
python main_launcher.py
```

### Windows 테스트 실행

```text
RUN_PEPTIFORG.bat
```

### EXE 빌드

```text
BUILD_EXE.bat
```

결과:

```text
dist/Pepforge/Pepforge.exe
```

### 설치 파일 빌드

Inno Setup 6 설치 후:

```text
BUILD_RELEASE.bat
```

결과:

```text
installer/output/Pepforge_Setup_v0.1.0.exe
```

---

## 6. 추천 GitHub 구성

```text
Pepforge/
├── README.md
├── README_KO.md
├── MANUAL_EN.txt
├── MANUAL_KO.txt
├── FEATURE_DIFFERENTIATION_ANALYSIS.txt
├── main_launcher.py
├── RUN_PEPTIFORG.bat
├── BUILD_EXE.bat
├── BUILD_RELEASE.bat
├── assets/
├── apps/
├── peptiforg_core/
├── suite_gui/
├── docs/
├── projects/
└── installer/
```

GitHub에는 소스코드와 문서, 예시 데이터를 올리고, 빌드된 EXE/설치 파일은 Releases에 올리는 것이 가장 깔끔하다.

---

## 7. 출력 파일 예시

```text
hotspot_regions.csv
selected_hotspots_for_design.csv
peptide_design_full_results.csv
peptide_design_top10.csv
selected_candidates.csv
spps_summary.csv
spps_step_matrix.csv
synthesis_form_wash_by_wash.csv
raw_material_use.csv
spps_plan.xlsx
project.json
```

CSV/XLSX 중심으로 구성한 이유는 Excel 확인, 실험 기록, 후속 ML 데이터셋 구성에 유리하기 때문이다.

---

## 8. 개발 상태

```text
Status: Beta / research prototype
Distribution: Python source + Windows EXE/installer-ready scripts
Main value: integrated workflow structure
Validation level: computational demonstration, not experimental validation
```

향후 개선 방향:

- 통합 GUI 개선,
- project/session 관리 강화,
- candidate-to-SPPS handoff 개선,
- ML-ready synthesis outcome logging,
- AF3/PRODIGY output parser,
- 자동 report generation,
- protected beta distribution.

---

## 9. 한계

Pepforge는 다음을 보장하지 않는다.

```text
biological activity
binding affinity
peptide stability
cell permeability
toxicity profile
synthesis success
purification success
experimental reproducibility
```

모든 결과는 실험 전 반드시 검토해야 한다.

---

## 10. 공개용 설명 문장

> Pepforge는 sequence hotspot 분석, constraint-aware peptide 후보 설계, SPPS 기반 합성 계획을 하나의 workflow로 연결하는 모듈형 peptide 연구 지원 suite입니다. 각 모듈은 독립적으로 사용할 수 있으며, 필요할 경우 project/session 기반으로 분석 결과를 설계와 합성 계획 단계까지 연결할 수 있습니다.

---

## 11. Disclaimer

Pepforge는 연구 지원, 교육, 포트폴리오 목적의 프로그램이다. 의료 소프트웨어, 임상 판단 도구, 실험 SOP 대체 도구가 아니며, 모든 계산 및 계획 결과는 적절한 전문가 검토가 필요하다.
