# Pepforge 완전 사용자 매뉴얼

**제품 버전:** Pepforge V3.0.0  
**내장 합성 모듈:** SPPS Planner V4.0.0  
**문서 기준일:** 2026-08-13  
**대상:** 처음 설치하는 사용자부터 결과를 검토·내보내는 연구 사용자까지

Pepforge는 peptide sequence 분석, 후보 설계, peptide-only 구조 생성, SPPS 계획, docking-oriented screening, 외부 검증용 파일 준비를 하나의 데스크톱 workflow로 연결합니다. 이 매뉴얼은 버튼을 누르는 순서뿐 아니라 입력 문법, 결과의 의미, 적용하면 안 되는 주장까지 설명합니다.

> Pepforge 결과는 연구 가설과 우선순위 자료입니다. 구조, score, contact, 합성 조건은 실험 측정값이나 임상·의료 판단이 아닙니다.

## 목차

1. [버전과 기능 범위](#1-버전과-기능-범위)
2. [설치](#2-설치)
3. [실행과 화면 구성](#3-실행과-화면-구성)
4. [15분 빠른 시작](#4-15분-빠른-시작)
5. [Peptide sequence 입력 문법](#5-peptide-sequence-입력-문법)
6. [Hot Spot Finder](#6-hot-spot-finder)
7. [Peptide Design Engine](#7-peptide-design-engine)
8. [Peptide Structure Builder](#8-peptide-structure-builder)
9. [SPPS Planner V4](#9-spps-planner-v4)
10. [Docking Workbench](#10-docking-workbench)
11. [External Validation](#11-external-validation)
12. [결과 폴더와 파일 관리](#12-결과-폴더와-파일-관리)
13. [과학적 해석과 검증](#13-과학적-해석과-검증)
14. [문제 해결](#14-문제-해결)
15. [CLI와 개발자 검증](#15-cli와-개발자-검증)
16. [공개·인용·버그 보고](#16-공개인용버그-보고)

## 1. 버전과 기능 범위

### 1.1 버전 표기

| 항목 | 표기 | 의미 |
| --- | --- | --- |
| 전체 프로그램 | Pepforge V3.0.0 | launcher와 통합 workflow의 배포 버전 |
| 합성 계획 모듈 | SPPS Planner V4.0.0 | Pepforge 안에 내장된 SPPS component 버전 |
| 구조 엔진 내부 계보 | 일부 파일에 v1.x/v2.x 표기 가능 | 해당 component의 역사적 구현 계보이며 전체 제품 버전이 아님 |

두 숫자를 합쳐 `Pepforge V4`라고 부르면 안 됩니다. 배포와 인용에는 **Pepforge V3.0.0 with SPPS Planner V4.0.0**을 사용합니다.

### 1.2 모듈별 역할

| 단계 | 모듈 | 하는 일 | 하지 않는 일 |
| --- | --- | --- | --- |
| 1 | Hot Spot Finder | sequence window의 후보 영역 우선순위화 | 실제 결합부위 증명 |
| 2 | Peptide Design Engine | canonical/modified peptide 후보 생성과 필터링 | 효능·독성·Kd 보증 |
| 3 | Peptide Structure Builder | peptide conformer를 생성하고 상위 5개 대표 구조 출력 | 생체 내 단일 native 구조 확정 |
| 4 | SPPS Planner V4 | 편집 가능한 합성 계획·재료량·checklist·근거 검토 | 검증된 실험실 SOP 자동 확정 |
| 5 | Docking Workbench | pose/contact 중심의 내부 screening과 외부 결과 정리 | Vina, MD, affinity assay 대체 |
| 6 | External Validation | Vina/GROMACS hand-off 폴더 준비 | 외부 프로그램 자체 실행 |

### 1.3 공개본의 데이터 원칙

- 실제 연구실 이력, 개인 정보, credential, 비공개 모델은 포함하지 않습니다.
- `actual_runs.csv`는 header/schema만 제공합니다.
- 예제와 template은 사용법 확인용이며 실험 사실로 해석하지 않습니다.
- 내장 ML이 근거 없이 affinity를 예측하지 않습니다. PDE reranking은 사용자가 검토한 CSV 또는 사용자 데이터가 있을 때만 활성화됩니다.

## 2. 설치

### 2.1 권장 환경

- Windows 10/11 64-bit
- Python 3.10 이상
- Tk/Tcl을 포함한 Python 설치
- 8 GB RAM 이상 권장
- 구조 생성에는 RDKit 필요
- PyMOL, AutoDock Vina, Open Babel, GROMACS는 선택적 외부 프로그램

GPU는 기본 desktop workflow에 필수가 아닙니다. 고비용 외부 docking/MD를 실행하려면 별도 환경이 필요합니다.

### 2.2 ZIP을 받은 경우

1. ZIP을 짧고 쓰기 가능한 경로에 풉니다. 예: `C:\Pepforge_V3.0.0`.
2. OneDrive 동기화 폴더, 읽기 전용 폴더, 한글과 공백이 매우 많은 경로는 처음 확인할 때 피하는 편이 안전합니다.
3. Windows Terminal 또는 명령 프롬프트를 해당 폴더에서 엽니다.

### 2.3 virtual environment 설치

Windows:

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

macOS/Linux source 실행:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

Tk가 없는 Linux에서는 OS package manager로 Tk를 별도 설치해야 할 수 있습니다. Pepforge의 주 UI 검증 대상은 Windows입니다.

### 2.4 설치 확인

```bash
python -c "import tkinter; print('Tk OK')"
python -c "import rdkit; print('RDKit OK')"
python pepforge_cli.py version
```

마지막 명령은 `3.0.0`을 출력해야 합니다. SPPS 창 제목에는 `SPPS Planner V4.0.0`이 표시되는 것이 정상입니다.

### 2.5 선택 dependency

| 파일 | 용도 |
| --- | --- |
| `requirements.txt` | 기본 desktop runtime |
| `requirements-ml.txt` | 사용자 데이터 기반 ML 확장 |
| `requirements-research.txt` | 추가 연구 분석 도구 |
| `requirements-web.txt` | 선택 web 관련 구성 |

처음에는 `requirements.txt`만 설치하십시오. 오류 원인을 줄이기 위해 필요한 profile만 추가합니다.

## 3. 실행과 화면 구성

### 3.1 통합 launcher

```bash
python main_launcher.py
```

launcher는 `Modern / Classic Hybrid Workspace`를 표시합니다. 왼쪽 `WORKFLOW`에서 모듈을 선택하면 가운데에 목적·workflow·출력 설명과 실제 실행 버튼이 나타나고, 오른쪽 `CONTEXT`에서 선택 도구와 격리된 workspace 경로를 확인할 수 있습니다.

1. Hot Spot Finder
2. Peptide Design Engine
3. Peptide Structure Builder
4. SPPS Planner
5. Docking Workbench
6. External Validation

상단 메뉴의 `File`에서 project folder와 runtime logs를 열 수 있고, `View > Display Density`에서 Compact/Standard/Comfortable을 선택할 수 있습니다. `Tools`에는 고급 `Workflow Mode`와 현재 선택 도구 실행 명령이 있습니다. Docking Workbench는 왼쪽 WORKFLOW의 5단계에 한 번만 표시되는 것이 정상입니다.

### 3.2 모듈 직접 실행

```bash
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

문제가 특정 모듈에서만 발생하면 직접 실행이 재현과 log 확인에 유리합니다.

### 3.3 공통 UI 원칙

- `Browse`는 파일 또는 폴더를 선택합니다.
- `Analyze`는 입력 해석과 warning 확인 단계입니다.
- `Apply`는 화면에서 바꾼 설정을 명시적으로 확정합니다.
- `Generate`, `Build`, `Run`은 실제 계산 또는 산출물 생성을 시작합니다.
- `Open Output Folder`는 생성 결과 위치를 엽니다.
- 진행 중 창이 잠시 응답하지 않는 것처럼 보여도 임의로 여러 번 클릭하지 마십시오.

## 4. 15분 빠른 시작

처음에는 검증하기 쉬운 canonical peptide로 전체 흐름을 확인한 뒤 modification을 추가하십시오.

### 4.1 Hot Spot Finder 확인

1. `Hot Spot Finder`를 엽니다.
2. `Protein or Peptide Sequence`에 canonical one-letter sequence를 붙여 넣습니다.
3. 기본값 `Window 15`, `Overlap 5`, `Top N 30`을 유지합니다.
4. `Analyze Sequence`를 누릅니다.
5. `Candidate Table`과 `Log`를 확인합니다.

### 4.2 PDE 후보 생성

1. `Peptide Design Engine`을 엽니다.
2. `Target sequences`와 원하는 length 범위를 입력합니다.
3. 설정을 바꾼 뒤 반드시 `1. Apply Settings`를 누릅니다.
4. 상태가 적용됨으로 바뀌면 `2. Generate Candidates`를 누릅니다.
5. 결과 CSV와 ZIP을 열어 sequence와 chemistry column을 확인합니다.

### 4.3 PSB Top 5 생성

1. `Peptide Structure Builder`를 엽니다.
2. `Peptide sequence`에 후보 하나를 넣습니다.
3. `Physiological aqueous`와 `Fast Top 5 (recommended)`를 선택합니다.
4. `Analyze`로 token 해석표를 확인합니다.
5. `Build Top 5 Structures`를 누릅니다.
6. rank 1만 보지 말고 5개 family와 warning을 함께 봅니다.

### 4.4 SPPS 계획

1. `SPPS Planner`를 엽니다.
2. sequence, scale, resin, loading, terminal chemistry를 입력합니다.
3. `Generate`를 누릅니다.
4. Plan과 Materials를 수정했으면 `Apply Change`를 눌러 연동 표를 갱신합니다.
5. cleavage와 evidence status를 확인한 후 export합니다.

### 4.5 Screening과 hand-off

1. `Docking Workbench`에서 target/peptide 입력 방식을 선택합니다.
2. `Analyze` 후 `Run Screening`을 실행합니다.
3. contact와 geometry를 후보 비교용으로만 해석합니다.
4. 정량 docking이나 MD가 필요하면 `External Validation`에서 hand-off 폴더를 만듭니다.

## 5. Peptide sequence 입력 문법

### 5.1 기본 residue

Canonical peptide는 one-letter sequence로 입력할 수 있습니다.

```text
EEMQRR
WKWLKK
```

개별 residue를 명시하려면 하이픈을 사용합니다.

```text
A-C-D-E
P-A-L
```

공백, FASTA header, 번호, 주석이 섞이면 모듈별 허용 방식이 다를 수 있습니다. 가장 안전한 입력은 sequence만 넣는 것입니다.

### 5.2 terminal chemistry

```text
Ac-EEMQRR-NH2
Pal-AEEA-KKLL-NH2
Biotin-GGGK-NH2
FITC-KKLL-NH2
```

| 입력 | 기본 해석 |
| --- | --- |
| `Ac-`, `AC-`, `ac-` | N-terminal acetyl modifier |
| `Pal-`, `PAL-`, `pal-` | N-terminal palmitoyl modifier |
| `FITC-`, `Fitc-`, `fitc-` | 지원되는 경우 N-terminal FITC modifier |
| `Biotin-`, 대소문자 변형 | 지원되는 경우 N-terminal biotin modifier |
| `-NH2` | C-terminal amidation |

중요한 규칙은 **수식어 이름 뒤의 `-`**입니다.

- `AC-EEMQRR`는 `AC-` modifier alias로 인식됩니다.
- `ACEEMQRR`처럼 구분자 없이 이어 쓰면 canonical residues `A-C-E-E-M-Q-R-R`로 해석됩니다.
- `PAL-EEMQRR`는 `PAL-` palmitoyl alias로 인식됩니다.
- `PALEEMQRR`처럼 이어 쓰면 `P-A-L-E-E-M-Q-R-R` residue sequence입니다.
- 실제 Ala-Cys 또는 Pro-Ala-Leu를 명확히 쓰려면 `A-C-...`, `P-A-L-...`로 입력하십시오.

### 5.3 linker, tag, non-natural unit

```text
Pal-AEEA-dab(KKEK)-dG-NH2
Gal-GH-dab(EEEK)-NH2
Ac-K(AEEA-Biotin)-KLL-NH2
```

`AEEA`는 지원 registry에 있는 linker token이면 한 단위로 처리됩니다. `-AEEA-`처럼 경계를 표시하는 방식이 가장 안전합니다. 괄호는 side-chain branch 또는 치환 위치를 나타내는 지원 문법에 사용됩니다.

모든 모듈이 모든 token을 같은 수준으로 계산하지는 않습니다.

| 상태 | 의미 | 사용자가 할 일 |
| --- | --- | --- |
| recognized + graph supported | 이름과 실제 구조 graph를 모두 지원 | 출력 atom/bond와 mass를 확인 |
| recognized, planning only | SPPS catalog에는 있으나 3D graph가 없음 | PSB에서는 구조 생성 불가 또는 차단됨 |
| manual required | 정확한 reagent form/MW/attachment가 모호함 | CoA와 실제 시약을 입력·확인 |
| unsupported | parser 또는 계산 계약에 없음 | surrogate로 대체하지 말고 token 정의 필요 |

PSB는 모르는 화학구조를 임의의 glycine이나 탄소 사슬로 바꾸지 않습니다. 이름은 알아도 curated graph가 없으면 실제 3D 생성이 차단될 수 있습니다. 이것이 정상적인 안전 동작입니다.

### 5.4 권장 입력 습관

1. terminal modifier와 residue 경계를 `-`로 구분합니다.
2. multi-letter token은 registry 표기와 대소문자를 사용합니다.
3. branch 위치를 괄호로 명시합니다.
4. 먼저 `Analyze` 또는 parser preview를 확인합니다.
5. token table의 `raw`, `token`, `class`, `note`, `warning`을 읽습니다.
6. 경고가 남은 sequence를 그대로 다음 단계로 넘기지 않습니다.

## 6. Hot Spot Finder

### 6.1 입력 영역

- `Sequence file (optional)`: FASTA 또는 지원되는 sequence 파일을 선택합니다.
- `Output folder`: 결과 저장 폴더입니다.
- `Protein or Peptide Sequence`: sequence를 직접 붙여 넣습니다. 파일 없이도 분석할 수 있습니다.

직접 입력 기능이 기본 계약입니다. 파일을 선택하지 않았다는 이유로 직접 입력이 무시되면 정상 동작이 아닙니다.

### 6.2 설정

| 설정 | 의미 | 권장 시작값 |
| --- | --- | --- |
| `Use ESM (optional, slower)` | 선택적 embedding 기반 보조 정보 | 먼저 끔 |
| `Window` | 후보 구간 길이 | 15 |
| `Overlap` | 인접 window 중첩 길이 | 5 |
| `Top N` | 표시할 후보 수 | 30 |
| `Min score` | 결과에 남길 최소 score | 0.0 |

Window보다 Overlap이 지나치게 크면 중복 후보가 많아집니다. 짧은 peptide는 window를 sequence 길이에 맞게 줄입니다.

### 6.3 실행과 출력

1. sequence를 직접 입력하거나 파일을 선택합니다.
2. output folder를 확인합니다.
3. `Analyze Sequence`를 한 번 누릅니다.
4. progress와 `Log`를 확인합니다.
5. `Candidate Table`에서 rank, hotspot residues, center, score, 근거 설명을 검토합니다.

`Export Display XLSX`, `Export PyMOL PDB`, `Export Motif Hints`, `Open output folder`, `Load Example` 버튼을 사용할 수 있습니다. 높은 score는 결합 실험이나 실제 interface 분석을 대체하지 않습니다.

## 7. Peptide Design Engine

### 7.1 6개 탭

1. `Design Settings`
2. `Chemistry / Constraints`
3. `Hot Spot / Docking`
4. `Data / ML`
5. `Expert Override`
6. `Log / Results`

### 7.2 Apply 계약

PDE 아래쪽 버튼 순서는 `1. Apply Settings`, `2. Generate Candidates`입니다. 설정을 변경하면 상태가 `Settings changed — click Apply Settings`로 바뀝니다. `Peptide Length Mode`, 길이 범위, preset, chemistry를 바꾼 뒤에는 먼저 Apply하십시오. 이 구조는 숨은 자동 변경을 방지합니다.

### 7.3 Design Settings

| 항목 | 설명 |
| --- | --- |
| `Target sequences` | 설계 기준 target sequence |
| `Preset` | 기본값 묶음 |
| `Target Mode` | single/multi-target 목적 |
| `Design Mode` | 설계 전략 |
| `Binder Mode` | 후보 균형/성향 |
| `Population` | 한 세대 후보 수 |
| `Generations` | 탐색 반복 수 |
| `Final Top K` | 최종 저장 후보 수 |
| `Random Seed` | `Lock seed for exact repeat`를 켰을 때 사용할 재현 seed |

기본값은 seed 잠금 해제입니다. `Generate Candidates`를 누를 때마다 새로운 난수 seed를 만들고, 실제 사용 seed를 log와 config snapshot에 기록합니다. 동일 결과를 재현하려면 `Lock seed for exact repeat`를 켜고 seed를 입력합니다. `Repeat Last Run`은 직전 설정과 seed 전체를 그대로 재실행합니다. 공개 UI는 target과 RGD/KLVFF locked motif가 빈 상태로 시작하며, 예시는 사용자가 명시적으로 선택할 때만 적용됩니다.

최종 Top K는 normalized sequence-distance 기준으로 먼저 다양성을 확보하고, 후보가 부족한 경우에만 기준을 완화합니다. 따라서 새 seed에서는 후보가 달라지는 것이 정상이나, 강한 target/motif constraint가 있으면 일부 핵심 sequence가 겹칠 수 있습니다.
| `Peptide Length Mode` | fixed/범위 길이 규칙 |
| `Fixed/Min/Max Length` | 길이 제한 |
| `Length Measurement` | residue/token 중 계산 기준 |
| `Trim to length` | 초과 후보 처리 |

처음에는 작은 Population/Generations로 입력과 출력 계약을 확인한 뒤 확장하십시오.

### 7.4 Chemistry / Constraints

- terminal chemistry, D-residue, selected non-natural residue, linker/tag 사용 여부를 선택합니다.
- locked motif는 유지되어야 하는 residue pattern입니다.
- cyclization/disulfide/branch constraint는 위치와 chemistry가 일치해야 합니다.
- length가 residue 기준인지 token 기준인지 확인합니다. linker/tag를 residue로 세면 의도한 길이와 달라질 수 있습니다.

### 7.5 Hot Spot / Docking

- Hot Spot Finder 결과 또는 직접 지정 motif를 사용할 수 있습니다.
- PDB 기반 영역은 chain과 residue numbering을 확인합니다.
- detected region과 locked motif가 충돌하지 않는지 봅니다.
- sequence-only complex input은 docking 준비 자료이지 확정 pose가 아닙니다.

### 7.6 Data / ML

- 내장된 미학습 reranker는 사용하지 않습니다.
- 사용자가 제공한 label과 feature가 있는 데이터만 학습 근거가 됩니다.
- CSV prior는 사용자가 출처와 column을 검토한 경우에만 사용합니다.
- 모델 score를 Kd, ΔG, IC50 또는 성공 확률로 바꾸어 말하면 안 됩니다.
- 표본이 작거나 target이 다르면 모델을 끄고 rule-based 결과와 외부 검증을 우선합니다.

### 7.7 Expert Override와 결과

Expert JSON은 일반 UI 설정 뒤에 마지막으로 적용됩니다. override 없이 먼저 실행하고, 작은 JSON부터 추가하며, Apply 후 log와 config snapshot을 확인하십시오. 최종 score 하나만 보지 말고 sequence, modifications, charge, solubility, aggregation warning, chemical stability, SPPS feasibility, motif retention을 함께 봅니다.

## 8. Peptide Structure Builder

### 8.1 목적과 입력

PSB는 peptide sequence와 지원 chemistry를 해석하고 다양한 backbone family에서 conformer를 생성합니다. 공개 Top-5 build가 성공하려면 실제 좌표 후보 5개를 생성·순위화·저장해야 하며, 5개를 확보하지 못하면 일부 결과를 완성으로 표시하지 않고 worker 실패와 원인을 보여줍니다. AlphaFold 같은 protein native-structure predictor가 아니며 in-vivo population을 계산하지 않습니다.

입력은 `Peptide sequence`, `Output name`, `Output folder`, pH, temperature, ionic strength, environment, condition preset, build preset입니다. 과거 `Peptide notation` 대신 `Peptide sequence`를 사용합니다.

### 8.2 조건 preset

| preset | 기본 조건 | 의미 |
| --- | --- | --- |
| `Physiological aqueous` | pH 7.4, 37 °C, 150 mM | 생리적 수용액 metadata |
| `Neutral room temp` | pH 7.0, 25 °C, 100 mM | 중성 실온 metadata |
| `Membrane-mimetic metadata` | pH 7.4, 37 °C, 150 mM | 막 유사 해석 표시 |
| `Custom` | 사용자 입력 | 사용자 조건 기록 |

조건은 해석/export metadata입니다. explicit solvent, membrane simulation, constant-pH MD를 수행하지 않습니다.

### 8.3 계산 preset

| preset | 주요 설정 | 사용 시점 |
| --- | --- | --- |
| `Fast Top 5 (recommended)` | 초기 conformer 5, 반복 80, adaptive retry 2회, evidence-fast profile | 입력 확인과 일반 시작 |
| `Balanced` | 초기 conformer 12, 반복 200, adaptive retry 3회, evidence-balanced profile | family/RMSD 탐색을 넓힐 때 |
| `Thorough` | 초기 conformer 30, 반복 500, adaptive retry 4회, evidence-thorough profile | 최종 후보를 더 넓게 탐색할 때 |

세 preset 모두 정확히 5개를 출력하는 계약은 같습니다. 실제 sampling 수, retry 예산, RMSD 기준, 논문 근거 기반 family 우선순위가 달라집니다. Thorough가 더 참된 구조를 보장하지 않으며 탐색량만 늘립니다.

### 8.4 Analyze와 Build

1. sequence를 넣고 `Analyze`를 누릅니다.
2. `Chemistry interpretation`의 position, raw, token, class, note, warning을 확인합니다.
3. `Open Token Map`으로 지원 registry를 확인합니다.
4. unknown/ambiguous/planning-only token을 해결합니다.
5. output name/folder와 preset을 선택합니다.
6. `Build Top 5 Structures`를 한 번 누릅니다.
7. 별도 worker 계산을 기다린 뒤 `Open Output`으로 확인합니다.

속도가 느리면 Fast preset, 짧은 canonical sequence, 로컬 쓰기 가능 폴더로 먼저 확인하십시오. antivirus가 worker를 차단하거나 RDKit이 잘못 설치되면 실패할 수 있습니다.

### 8.5 구조 family와 특수 backbone

탐색 후보에는 α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, coil/mixed가 포함될 수 있습니다. helix propensity coverage, i/i+3·i/i+4 charge spacing, amphipathic moment, turn-compatible window, β alternation, Pro/PPII context, α/β/γ backbone pattern을 이용해 감사 가능한 family 우선순위를 만들고, 선택한 build preset이 실제 탐색 폭을 결정합니다. 초기 torsion seed는 family를 놓치지 않기 위한 시작점이지 population의 증거가 아닙니다.

BH3 helical domain을 모사하는 α/β/γ-peptide처럼 backbone pattern과 residue substitution이 helicity를 크게 바꾸는 경우를 일반 α-peptide 규칙으로 단순 환산하면 안 됩니다. 지원 pattern은 별도 guidance/limitation을 표시하며, 미지원 unit은 실제 graph와 parameter 없이 3D 확정값으로 대체하지 않습니다. CD, NMR, crystallography, 적합한 force field/MD와 비교하십시오.

### 8.6 대표 출력

```text
*_top5_conformers.sdf
*_top5_conformers.csv
*_top5_rank1.pdb ... *_top5_rank5.pdb
*_top5_compare.pml
*_conformer_families.csv
*_backbone_torsions.csv
```

rank는 실행 내부 상대 순위이고 relative energy는 서로 다른 chemistry나 affinity 비교값이 아닙니다. 생성 fraction도 평형 population이 아닙니다. atom/bond, chirality, terminal group을 직접 확인하십시오.

## 9. SPPS Planner V4

### 9.1 통합 범위와 입력

Pepforge에는 SPPS Planner V4.0.0의 single-plan, material, checklist, cleavage, evidence workflow가 통합되어 있습니다. **LOT Number와 Batch Manager는 active interface에서 제외**되었습니다.

시작 전에 peptide sequence, scale, resin/linker, resin loading, coupling/deprotection chemistry, loading/cleavage time, tag/linker/non-natural building block을 확인합니다. generic 이름만으로 MW와 당량을 확정할 수 없는 물질은 manual-required 상태가 정상입니다.

### 9.2 Generate와 Apply Change

`Generate`는 현재 입력으로 Plan, Materials, Total Materials, Checklist, cleavage, risk/evidence 표를 만듭니다. cell을 수정한 뒤에는 `Apply Change`를 눌러야 연결된 표와 합계에 반영됩니다. 선택만 하거나 cell을 편집 중인 상태로 두는 것은 적용이 아닙니다.

### 9.3 검토 순서

1. **Plan:** 단계, 위치, reagent, eq, 반복, 시간
2. **Materials:** 단계별 사용량과 단위
3. **Total Materials:** 중복 reagent 합산과 cleavage 포함
4. **Checklist:** 실제 작업 순서
5. **Cleavage:** cocktail, 비율, 시간, sequence 위험
6. **Evidence:** 추천 출처와 status
7. 수정 후 `Apply Change`
8. export 파일과 화면 값 재확인

### 9.4 Evidence status

| status | 의미 | exact-condition Apply |
| --- | --- | --- |
| `verified` | source와 주요 조건 검토됨 | 조건 일치 시 가능 |
| `parsed` | 문서에서 구조화했으나 검증 전 | 사용자 명시 확인 필요 |
| `incomplete` | 필수 field 누락 | 불가 |
| `excluded` | 제외 규칙 해당 | 불가 |

추천은 하나의 coherent historical record에서 가져옵니다. 서로 다른 논문의 성분, 시간, 온도를 합쳐 새로운 최적 조건처럼 만들지 않으며 모델이 만든 가상 optimum도 Apply하지 않습니다.

### 9.5 Cleavage와 modified peptide

- sequence가 첫 번째 matching key이고 product name은 metadata입니다.
- cocktail 성분/비율이 불완전하거나 unknown이면 exact Apply를 차단합니다.
- loading time과 cleavage time은 독립 공정 시간이며 stoichiometry를 바꾸지 않습니다.
- `Pal-`, FITC, Biotin, chelator, lipid, PEG/AEEA는 정확한 reagent form을 확인합니다.
- protected/unprotected form과 branch/terminal 위치를 구분합니다.
- difficult sequence, aggregation, aspartimide, diketopiperazine, oxidation, disulfide/cyclization 위험을 검토합니다.

Regression contract인 `Ac-EEMQRR-NH2`의 30 eq 및 `TFA 95% / water 5% / TIS 없음` 조건은 코드 검증 대상으로 포함되어 있지만 사용자 연구실의 validated SOP를 뜻하지 않습니다.

### 9.6 Export 전 checklist

- [ ] sequence와 terminal chemistry가 최종 주문서와 같다.
- [ ] resin loading/scale 단위가 맞다.
- [ ] manual-required reagent의 정확한 form/MW를 확인했다.
- [ ] repeat count와 eq를 검토했다.
- [ ] cleavage 합계와 시간 단위가 맞다.
- [ ] Total Materials에 cleavage reagent가 포함됐다.
- [ ] 수정 후 Apply Change를 눌렀다.
- [ ] export와 화면 값이 일치한다.

## 10. Docking Workbench

### 10.1 입력과 준비

구조 입력은 `Protein/complex PDB or mmCIF`, `Peptide PDB or peptide chain file`, `Result file`을 사용합니다. Sequence mode는 `Protein sequence`, `Peptide sequence`, `Output folder`를 사용합니다.

RCSB 기능은 `Search RCSB`, `Fetch selected to Target`, `Open RCSB page`입니다. 받은 구조의 chain, missing residue, mutation, ligand, biological assembly를 원본 entry에서 확인하십시오.

Target Prep에서 chain과 water/ion/ligand 유지 여부를 정한 뒤 `Prepare Target`을 실행합니다. metal/cofactor와 protonation은 실제 binding mechanism에 맞게 검토합니다. Complex Builder의 `Build Initial Complex`는 초기 가설이지 최적 pose가 아닙니다.

### 10.2 Screening

1. 입력을 넣습니다.
2. `Analyze`로 validation과 작업량을 봅니다.
3. `Run Screening`을 한 번 누릅니다.
4. progress/log를 기다립니다.
5. contact, clash, geometry, ranking을 비교합니다.
6. `Export` 또는 `Open Folder`로 결과를 확인합니다.

`Input data full`, `Results data full`, `Advanced`는 상세 table과 고급 workflow를 엽니다. 외부 결과 import, session, dashboard, experimental import, run comparison, calibration/evidence 도구도 있습니다.

내부 screening은 local geometry/contact hypothesis입니다. score를 Vina energy, PRODIGY affinity, ΔG, Kd, Ki, IC50로 부르지 마십시오. 정량 주장은 실제 docking engine, peptide parameter, convergence/control, 필요 시 MD와 실험 assay가 필요합니다.

## 11. External Validation

`Check again`은 PATH에서 AutoDock Vina, Open Babel, GROMACS, WSL을 확인합니다. 표시되지 않으면 별도 설치 또는 PATH 설정이 필요합니다.

### 11.1 Vina package

1. output, receptor, ligand/peptide 파일을 지정합니다.
2. `Export Vina Package`를 누릅니다.
3. guide와 입력 파일을 확인합니다.
4. charge, PDBQT, box, exhaustiveness를 외부 workflow에서 정합니다.

### 11.2 GROMACS prep

1. peptide PDB를 선택합니다.
2. `Export GROMACS Prep Folder`를 누릅니다.
3. `README_GROMACS.txt`를 읽습니다.
4. force field가 modification/D-residue/linker/lipid/tag를 지원하는지 확인합니다.
5. topology부터 production/analysis까지 GROMACS에서 실행합니다.

hand-off 폴더 생성은 docking이나 MD를 수행했다는 뜻이 아닙니다.

## 12. 결과 폴더와 파일 관리

Source 실행은 저장소 또는 선택 output folder를 사용하고 설치형 build는 사용자 쓰기 가능한 app data 위치를 사용할 수 있습니다. `Open project folder`와 `Open runtime logs`로 실제 위치를 확인하십시오.

권장 구조:

```text
project_name/
  01_input/
  02_hotspot/
  03_design/
  04_structure/
  05_spps/
  06_screening/
  07_external_validation/
  08_experimental/
  config_and_notes/
```

run별로 sequence, target accession, config snapshot, seed, software version, 날짜를 기록합니다. 공개 전에는 실제 연구실 history, 미공개 sequence/structure, credential, local model/training data, 개인정보, 재배포 권한 없는 문서, log의 개인 경로를 제거합니다.

## 13. 과학적 해석과 검증

안전한 표현:

- “Pepforge로 후보를 computationally prioritized했다.”
- “다섯 representative starting conformers를 생성했다.”
- “내부 contact-oriented screening을 수행했다.”
- “외부 docking/MD 검증용 package를 준비했다.”

피해야 할 표현:

- “Pepforge가 native structure를 예측했다.”
- “rank 1이 체내 유일 구조다.”
- “내부 score가 nM Kd를 증명한다.”
- “Pepforge가 Vina/GROMACS를 실행·대체했다.”
- “SPPS recommendation이 최적 SOP다.”

권장 검증 순서는 parser/chemistry 확인 → Top 5 비교 → external docking → 필요 시 parameterized MD → CD/NMR/crystallography → binding/functional assay → synthesis purity/identity 확인입니다.

## 14. 문제 해결

| 증상 | 먼저 확인 | 다음 조치 |
| --- | --- | --- |
| launcher가 안 열림 | Python/Tk, virtual env | terminal에서 직접 실행 |
| 모듈 창 즉시 종료 | runtime log | 해당 `--tool` 실행 |
| ModuleNotFoundError | environment | requirements 재설치 |
| RDKit import 실패 | 같은 Python인지 | executable 경로 확인 |
| Hot Spot direct input 무반응 | 빈칸/문자 | Analyze와 Log 확인 |
| PDE Generate 비활성 | 설정 미적용 | Apply Settings 클릭 |
| PDE 길이 오류 | Length Measurement | residue/token 기준 확인 |
| PSB token 오인식 | 경계/대소문자 | `A-C-`, `P-A-L-`, `-AEEA-` 사용 |
| PSB 느림/종료 | preset, memory, path | Fast/짧은 sequence/local folder |
| SPPS 수정 미반영 | cell/Apply | 편집 종료 후 Apply Change |
| SPPS Apply 차단 | incomplete/unknown | source/component 보완 |
| Docking 결과 없음 | mode/file/chain | Analyze와 log 확인 |
| 외부 도구 미탐지 | 설치/PATH | 설치 후 terminal 재시작 |
| PyMOL 안 열림 | 별도 설치 | PDB/PML 수동 열기 |

좋은 버그 보고에는 버전, OS/Python, source/installer, 모듈, 공개 가능한 최소 sequence, 버튼 순서, 예상/실제 결과, log, screenshot을 넣고 비공개 데이터는 제거합니다.

## 15. CLI와 개발자 검증

```bash
python pepforge_cli.py --help
```

| command | 목적 |
| --- | --- |
| `version` | suite version |
| `init-workflow`, `run-workflow` | workflow 초기화/실행 |
| `experimental-template`, `import-experimental` | 실험 데이터 template/import |
| `dashboard`, `evidence-autoscan`, `compare-runs` | 결과·근거 비교 |
| `validate-runtime` | runtime 진단 |
| `audit-package`, `regression-audit` | package/regression 감사 |
| `release-integrity`, `verify-matrix`, `release-gate` | 공개 전 검증 |

```bash
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

자동 검증은 native Windows rendering, 실제 PyMOL, 외부 docking/MD, 실험 타당성을 대신하지 않습니다. 배포 전 Windows에서 6개 모듈을 직접 smoke test하십시오.

## 16. 공개·인용·버그 보고

GitHub 공개 전 `PUBLIC_DATA_POLICY.md`를 읽고 credential/private data를 검색하며 release gate를 통과시킵니다. `VERSION.txt`, `CITATION.cff`, README, release filename은 `3.0.0`으로 맞추고 SPPS component는 `4.0.0`으로 별도 표기합니다. runtime output, cache, backup, local model은 source ZIP에 넣지 않습니다.

인용 metadata는 `CITATION.cff`에 있습니다. 이 저장소는 custom **Pepforge Public Academic Citation License**를 사용하며 OSI-approved open-source license로 표시되지 않습니다. 재배포와 상업적 이용 전에 `LICENSE`를 읽으십시오.

최종 확인:

- [ ] suite/SPPS version을 구분했다.
- [ ] token warning을 모두 읽었다.
- [ ] PDE에서 Apply Settings를 눌렀다.
- [ ] PSB Top 5를 비교했다.
- [ ] SPPS에서 Apply Change를 눌렀다.
- [ ] docking score를 affinity로 표현하지 않았다.
- [ ] 외부 도구 실행 여부를 정확히 기록했다.
- [ ] 실험·구조 검증 계획을 세웠다.
- [ ] 공개 파일에서 비공개 데이터를 제거했다.

관련 문서: [README_KO.md](README_KO.md), [과학적 범위](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md), [sequence grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md), [SPPS parser contract](docs/SPPS_PARSER_CONTRACT.md), [SPPS V4 evidence workflow](docs/SPPS_V4_EVIDENCE_WORKFLOW.md), [Docking guide](docs/DOCKING_WORKBENCH_USER_GUIDE.md).
