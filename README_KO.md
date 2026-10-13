<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge" width="150">

# Pepforge

### 펩타이드 설계 · 구조 생성 · 도킹 · SPPS 계획 · 상호작용 분석을 하나로 연결하는 연구용 워크벤치

**Pepforge V5.0.0 · Public Research Source Release**

[![Release](https://img.shields.io/badge/release-v5.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#빠른-시작)
[![Release Gate](https://img.shields.io/badge/release_gate-25%2F25-16A34A?style=for-the-badge)](#검증)

**[English](README.md) · [빠른 시작](#빠른-시작) · [주요 기능](#주요-기능) · [Structure & Docking Studio](#structure--docking-studio) · [SPPS Planner](#spps-planner) · [과학적 범위](#과학적-범위) · [전체 매뉴얼](MANUAL_KO.md)**

</div>

---

## 개요

Pepforge는 **서열 수준 후보 탐색 → 펩타이드 설계 → 3D 구조 생성 → protein–peptide docking → 상호작용 분석 → SPPS 계획**을 하나의 흐름으로 연결하는 Windows 우선 데스크톱 연구용 워크벤치입니다.

V5.0.0은 V4의 기본 workflow를 유지하면서, 구조 생성과 docking/interaction review를 하나의 분석 흐름으로 통합한 버전입니다.

핵심 원칙은 다음과 같습니다.

> **계산 결과와 실험 근거는 반드시 구분되어야 합니다.**

Pepforge는 canonical peptide뿐 아니라 지원되는 범위에서 terminal chemistry, D-residue, non-natural residue, linker, label 및 modified-peptide notation을 보존합니다.

```text
Target / protein sequence
        ↓
Hot Spot Finder
        ↓
Peptide Design Engine (PDE)
        ↓
Structure & Docking Studio
   ├─ peptide structure generation
   ├─ receptor / peptide preparation
   ├─ native docking
   ├─ interaction analysis
   ├─ mechanics / trajectory review
   └─ result interpretation
        ↓
SPPS Planner
        ↓
Evidence export / downstream validation
```

Pepforge는 내부 docking score를 실험적 affinity로 해석하지 않으며, 지원되지 않는 chemistry를 임의로 만들어내거나 생성된 구조를 native biological state의 증거로 취급하지 않습니다.

---

## 주요 기능

| 모듈 | 기능 |
| --- | --- |
| **Workflow Mode** | Hot Spot → PDE → Structure & Docking → SPPS 흐름을 project/session 및 candidate lineage와 함께 연결 |
| **Hot Spot Finder** | protein/peptide sequence를 입력해 후보 구간을 screening하고 ranking |
| **Peptide Design Engine (PDE)** | 명시적인 design objective와 chemistry-aware 처리, candidate tracking 기반 후보 생성/평가 |
| **Structure & Docking Studio** | peptide 구조 생성, receptor 준비, native docking, interaction analysis, mechanics/trajectory review, 결과 해석을 하나의 workspace로 통합 |
| **SPPS Planner** | 합성 계획, materials, checklist, cleavage review, project 관리 및 decision-support workflow 제공 |
| **Validation / benchmark tools** | benchmark 준비, provenance 추적, calibration, release audit 및 external validation hand-off 지원 |

### Design mode

PDE는 하나의 불투명한 종합 점수만 쓰는 대신 다음과 같은 scientific-design objective를 명시적으로 유지합니다.

- **Interaction Only**
- **Interaction First**
- **Balanced**
- **Structure Guided**
- **Structure Exploration**

Structure-guided mode는 명시적인 structure intent가 있을 때 사용하며, 사용자가 지정하지 않은 target conformation을 임의로 생성해 가정하지 않습니다.

---

## Structure & Docking Studio

V5에서는 peptide structure와 docking workflow를 **Structure & Docking Studio** 하나의 주 작업공간으로 통합했습니다.

여러 개의 분리된 창을 반복해서 이동하기보다, sequence에서 구조 후보와 docking pose까지 연결되는 흐름을 유지하도록 설계했습니다.

### 기본 흐름

```text
Peptide sequence / modified construct
        ↓
Conformer generation
        ↓
Candidate structure review
        ↓
Target / receptor loading
        ↓
Native docking
        ↓
Interaction evidence
        ↓
Optional mechanics / trajectory review
        ↓
Interpretation / export
```

### Peptide 구조 생성

지원 가능한 chemistry 범위에서 다음과 같은 conformational family를 탐색할 수 있습니다.

- α-helix
- 3₁₀-helix
- β-extended / strand-like
- β-hairpin-like
- PPII
- turn-rich
- coil / mixed

생성된 conformer는 **검토와 후속 검증을 위한 starting hypothesis**이며, 실험적으로 입증된 native conformation이나 conformational population을 의미하지 않습니다.

### Native docking

Pepforge V5는 pose generation 및 structural screening을 위한 native docking 경로를 제공합니다.

Native docking score는 **Pepforge 내부의 dimensionless pose-search / ranking score**입니다.

다음과 같이 해석해서는 안 됩니다.

- ΔG
- Kd
- experimental affinity
- biological activity
- validated free-energy estimate

### Interaction analysis

Pepforge는 residue-centered structural evidence를 기준으로 다음과 같은 interaction candidate를 검토할 수 있습니다.

- hydrogen bond
- hydrophobic contact
- salt bridge / ionic interaction
- π–π interaction
- cation–π interaction
- van der Waals contact / clash
- disulfide geometry
- water-mediated contact candidate
- metal coordination
- halogen-bond geometry
- aromatic–sulfur interaction
- weak C–H···O/N interaction
- NH–π / amino–aromatic interaction

Geometry 기반 interaction evidence는 **구조적 screening 근거**이며, 그 자체로 binding strength나 biological activity를 증명하지 않습니다.

### Native Mechanics / trajectory review

V5는 exploratory structural review를 위한 native mechanics 및 trajectory-analysis 경로를 제공합니다.

다만 이를 **production-grade molecular dynamics**로 표시하지 않습니다. Production MD는 검증된 force-field parameter, timestep/ensemble control, 실제 simulation backend 및 별도 validation이 필요합니다.

---

## Modified peptide 지원

Pepforge는 terminal chemistry, residue identity, linker/tag가 서로 혼동되지 않도록 explicit tokenization을 사용합니다.

예시:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

주요 예시:

| 입력 | 해석 |
| --- | --- |
| `Ac-` / `AC-` | N-terminal acetyl modifier |
| `Pal-` / `PAL-` | N-terminal palmitoyl modifier |
| `A-C-` | Ala–Cys residue sequence |
| `P-A-L-` | Pro–Ala–Leu residue sequence |
| `FITC-` / `Biotin-` | 지원되는 label / tag token |
| `AEEA`, `Ahx`, PEG token | 지원되는 linker chemistry |
| D / non-natural residue token | canonical L-residue로 임의 변환하지 않고 별도 chemistry identity로 보존 |

지원 범위는 workflow stage마다 다를 수 있습니다.

예를 들어 construct notation은 정상적으로 parse 및 보존할 수 있지만, 해당 derivative에 대해 unique all-atom structure나 force-field parameter가 정의되지 않은 경우 좌표 생성 또는 simulation 단계는 제한될 수 있습니다.

Pepforge는 이런 경우 지원되지 않는 구조나 parameter를 임의로 생성하지 않습니다.

---

## SPPS Planner

Pepforge에는 peptide research workflow와 연결되는 SPPS planning 기능이 통합되어 있습니다.

현재 SPPS Planner integration은 다음 기능을 제공합니다.

- Project Manager workflow
- Batch-oriented project handling
- editable synthesis Plan
- step-wise Materials
- Total Materials
- Checklist
- cleavage review
- Pepforge workflow에서 sequence / construct 전달
- project/session persistence
- literature/evidence guidance
- 사용자 제공 experimental evidence 기반 decision support

SPPS Planner는 합성 계획 및 의사결정 지원 도구이며, 다음을 보장하지 않습니다.

- synthesis yield
- purity
- reaction completion
- cleavage success
- laboratory safety

Public Pepforge package에는 private laboratory history, credential, local experimental database, internal operator record를 포함하지 않습니다.

---

## Public benchmark / provenance 지원

V5에는 public protein–peptide benchmark preparation 및 validation을 위한 infrastructure가 포함되어 있습니다.

지원되는 provenance workflow에는 다음이 포함됩니다.

- public benchmark registry
- RCSB PDB coordinate retrieval / local cache
- receptor / peptide chain normalization
- SHA-256 provenance record
- UniProtKB sequence / identity metadata
- train / holdout split audit
- leakage check
- docking-score / structural-recovery calibration
- validation workspace audit
- release dossier

RCSB 또는 UniProt provenance가 존재한다고 해서 docking result 자체의 정확성이 자동으로 보장되는 것은 아닙니다.

또한 deterministic holdout split만으로 sequence-independent generalization이 입증되는 것도 아닙니다.

---

## V5 FINAL UI / workflow 개선

최종 V5 build에서는 일반적인 desktop scientific software에 가까운 조작감을 만들기 위해 UI/UX를 정리했습니다.

주요 변경 사항:

- PSB와 Docking을 별도 primary workflow로 나누지 않고 **Structure & Docking Studio**로 통합
- peptide sequence 입력 영역 확대
- 기본 작업 창 크기 확대
- 긴 분석 화면에서 **일반 마우스 휠 기반 scrolling**
- **Structure & Docking Studio와 Workflow Mode 모두 page scrolling 지원**
- scrollbar를 직접 이동할 때 layout이 비정상적으로 늘어나는 현상을 줄이기 위한 viewport width 안정화
- 페이지 끝에서 반복 wheel event가 누적되는 현상 완화
- SPPS Planner launch integration 개선
- 기존 고급 docking review 기능은 compatibility / advanced route로 유지

---

## 빠른 시작

### 요구사항

- Windows 10/11 권장
- 64-bit Python **3.10+**
- Tk 지원
- 실제 3D 구조 생성을 위한 RDKit

외부 simulation/review 프로그램은 선택 사항이며 필요한 경우 별도로 설치합니다.

### Source 실행

```bat
git clone https://github.com/SanghunWoo-23/Pepforge.git
cd Pepforge

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python main_launcher.py
```

Windows에 Python이 여러 개 설치되어 있다면 다음과 같이 실행할 수도 있습니다.

```bat
py main_launcher.py
```

### 모듈 직접 실행

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool spps
python main_launcher.py --tool workflow
python main_launcher.py --tool external
```

일부 compatibility / advanced route는 특정 review workflow를 위해 유지될 수 있지만, V5의 기본 구조 분석 경로는 **Structure & Docking Studio**입니다.

전체 UI 사용법, 입력 규칙, 출력 및 troubleshooting은 [MANUAL_KO.md](MANUAL_KO.md) 또는 [MANUAL_EN.md](MANUAL_EN.md)를 참고하십시오.

---

## 일반적인 workflow

1. **Project/session을 생성하거나 엽니다.**
2. 필요하면 **target/protein sequence를 입력하고 Hot Spot Finder**를 실행합니다.
3. **PDE에서 peptide candidate를 생성 또는 평가**합니다.
4. 선택한 candidate를 **Structure & Docking Studio**로 보냅니다.
5. peptide conformer를 생성하고 구조 후보를 검토합니다.
6. receptor / target structure를 불러옵니다.
7. native docking을 실행하고 ranked pose hypothesis를 검토합니다.
8. interaction evidence와 필요한 경우 mechanics / trajectory 결과를 확인합니다.
9. active construct를 SPPS Planner로 전달하여 synthesis planning을 진행합니다.
10. 결과를 external review, benchmark comparison 또는 downstream validation용으로 export합니다.

서로 다른 단계에서 생성된 evidence는 하나의 근거 없는 confidence score로 합쳐지지 않고 각 단계별 provenance와 의미를 유지합니다.

---

## 저장소 구조

```text
Pepforge/
├─ main_launcher.py
├─ pepforge_cli.py
├─ suite_gui/
├─ peptiforg_core/
├─ pepforge_structure_tool/
├─ apps/
├─ tests/
├─ docs/
├─ data/
├─ installer/
├─ MANUAL_EN.md
├─ MANUAL_KO.md
├─ README.md
└─ README_KO.md
```

Runtime workspace, generated output, cache, credential, private experimental history, internal handover document는 public source package에서 제외합니다.

---

## 검증

최종 V5 public build는 UI 및 packaging 정리 이후 regression test를 다시 수행했습니다.

| 항목 | 결과 |
| --- | ---: |
| V5 regression tests | **130 passed / 0 failed** |
| Legacy V4 release / verify / integrity audit | **6 passed / 0 failed** |
| Legacy full-package / regression / source-integrity audit | **7 passed / 0 failed** |
| Release Gate | **25 / 25 passed** |
| Compile errors | **0** |

대표적인 UI 검증 항목:

- Structure & Docking Studio 일반 mouse-wheel scrolling
- Workflow Mode 일반 mouse-wheel scrolling
- scrollbar 이동 중 outer canvas width 안정성
- 페이지 끝단에서 반복 wheel event 누적 방지
- SPPS Planner launch path compatibility

로컬에서 다음 검증을 실행할 수 있습니다.

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

Native Windows rendering, packaged installer/EXE, third-party simulation engine, GPU-specific path 및 외부 application 실행은 사용 환경에 따라 별도로 확인해야 합니다.

---

## 과학적 범위

Pepforge는 다음 목적을 위한 연구 지원 도구입니다.

- research prioritization
- reproducible computational preparation
- peptide-structure hypothesis generation
- docking / interaction screening
- synthesis planning
- validation hand-off

Pepforge 결과만으로 다음을 증명할 수 없습니다.

- experimental binding affinity 또는 Kd
- binding free energy
- native in-vivo peptide conformation
- biological efficacy
- synthesis yield / purity
- validated laboratory SOP
- production-grade MD validity

지원되지 않는 building block, force-field parameter, experimental result, optimum synthesis condition을 임의로 생성하지 않습니다.

---

## 문서

| 문서 | 내용 |
| --- | --- |
| [한국어 매뉴얼](MANUAL_KO.md) | 설치, workflow, 입력, 출력, troubleshooting |
| [English Manual](MANUAL_EN.md) | Complete English guide |
| [Public Data Policy](PUBLIC_DATA_POLICY.md) | Public/private data boundary |
| [Changelog](CHANGELOG.md) | 공개 개발 및 release history |
| [Contributing](CONTRIBUTING.md) | bug report 및 contribution guidance |
| [Security](SECURITY.md) | security reporting 및 public-package 주의사항 |

상세 internal handover 문서와 향후 version roadmap은 **Public GitHub source package와 분리하여 관리**합니다.

---

## Citation

학술 작업에 Pepforge 또는 Pepforge-generated workflow가 실질적으로 기여했다면 사용한 **정확한 release**를 인용하십시오.

저장소에 `CITATION.cff`가 포함되어 있다면 GitHub에서 citation metadata를 직접 표시할 수 있습니다.

권장 repository citation:

> Woo, S. *Pepforge: An Integrated Peptide Research Workbench*. Version 5.0.0, 2026. https://github.com/SanghunWoo-23/Pepforge

향후 DOI 기반 release가 제공될 경우 해당 release의 DOI citation을 우선 사용하십시오.

---

## License

Pepforge는 public repository에 포함된 license 조건을 따릅니다.

재배포, 파생 배포 또는 상업적 사용 전 [LICENSE](LICENSE)를 확인하십시오.

---

## Contributing / Security

Bug report에는 가능하면 다음 정보를 포함하십시오.

- Pepforge version
- operating system
- Python version
- launch method
- 문제가 발생한 module
- 최소 재현 입력
- 재현 절차
- confidential / unpublished information을 제거한 관련 log

자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)와 [SECURITY.md](SECURITY.md)를 참고하십시오.

---

<div align="center">

**Pepforge V5.0.0**  
Peptide sequence에서 design, structure, docking, SPPS planning, interaction review, validation hand-off까지.

</div>
