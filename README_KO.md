<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge" width="150">

# Pepforge

### 비천연·D-form 펩타이드 설계부터 구조 생성, Docking, MD/ABFE 분석, SPPS 계획까지

**Pepforge V6.0.0 · Public Research Source Release**

[![Release](https://img.shields.io/badge/release-V6.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/desktop-Windows-0078D4?style=for-the-badge)](#빠른-시작)
[![Status](https://img.shields.io/badge/status-research%20source-64748B?style=for-the-badge)](docs/RELEASE_STATUS_V6.0.0.md)

**[English](README.md) · [주요 기능](#주요-기능) · [비천연-펩타이드](#비천연-펩타이드와-입체화학) · [빠른 시작](#빠른-시작) · [검증 상태](#검증-상태) · [매뉴얼](MANUAL_KO.md)**

</div>

---

## 소개

**Pepforge**는 Windows 중심의 펩타이드 연구용 데스크톱 프로그램입니다. Hot Spot Finder → Peptide Design Engine(PDE) → Structure & Docking Studio → SPPS Planner를 하나의 연구 흐름으로 연결합니다.

V6.0.0은 V5의 구조·Docking 작업 흐름에 **지원 가능한 D-form/비천연 아미노산 및 chemical/linker, conformer ensemble, 유연 구조 후보 탐색, 선택형 MD·ABFE 계산 도구, SPPS Planner V8.0.0 Public 연결**을 추가한 소스 릴리스 후보입니다.

> **기본 원칙:** 계산 결과·모델 기반 점수·자유에너지 추정값과 실험 증거는 명확하게 구분합니다.

```text
Target 서열 또는 단백질 구조
            ↓
      Hot Spot Finder
            ↓
  Peptide Design Engine
            ↓
 Structure & Docking Studio
   ├─ 비천연/D-form/chemical 토큰
   ├─ 3D Conformer 및 MMFF94s
   ├─ Receptor/Peptide 파일 준비
   ├─ Native / Ensemble Docking
   ├─ 상호작용 / Interface Refinement
   └─ 선택형 MD / ABFE / PyMOL 검토
            ↓
   SPPS Planner V8.0.0 Public
            ↓
 합성 계획 · 결과 검증 및 Evidence Export
```

구조와 Docking 포즈는 **검증할 수 있는 가설**이지 실험적으로 확인된 결합 구조 자체가 아닙니다.

---

## 주요 기능

| 모듈 | 역할 |
| --- | --- |
| **Hot Spot Finder** | 표적 서열·구조 기반 후보 영역 검토 |
| **PDE** | 서열 후보 생성, 설계 목표 선택, chemistry-aware 토큰 취급 |
| **Structure & Docking Studio** | 3D 구조 생성, Docking, 상호작용 검토 및 결과 해석 |
| **Modified Peptide** | 지원되는 D-form·비천연 AA·말단 수식·linker·tag의 명시적 취급 |
| **MMFF94s / Conformer** | ETKDG, 구조 최적화, 입체화학 검사, energy·RMSD 다양성 선별 |
| **Native / Ensemble Docking** | 구조 후보별 포즈 탐색, clash/contact 분석, interface refinement |
| **PyMOL** | 구조 검토 및 비표준 화학 토큰용 선택형 별도 패널 |
| **선택형 Science Engines** | OpenMM·OpenFE·OpenFF·GAFF·PyMBAR 연동 및 계산 감사 기능 |
| **SPPS Planner V8.0.0 Public** | Pepforge에서 독립된 정상 창으로 실행되는 V8 원본 합성 계획·자재·체크리스트·절단 검토 |
| **검증 및 Provenance** | SHA-256, 구조 RMSD, 계열별 벤치마크, 실행 증빙 |

PDE 설계 모드: **Interaction Only · Interaction First · Balanced · Structure Guided · Structure Exploration**.

---

## Structure & Docking Studio

Docking & Simulation 탭은 **Receptor(소스·PDB/mmCIF·서열)** 와 **Peptide(소스·PDB/mmCIF/SDF/MOL·서열)** 입력을 각각 한 구역에 모으고, 하단에 결합 및 Docking 설정을 배치했습니다. Peptide 서열은 Structure Builder 탭과 동일한 값을 공유하며 탭을 바꿔도 유지됩니다.

Receptor에 PDB/mmCIF 구조 파일을 사용하고, 지원되는 peptide PDB/mmCIF/SDF/MOL 입력 또는 서열 기반 구조 생성 경로를 사용할 수 있습니다. Native Docking은 blind/manual/hotspot 모드와 다중 Conformer 후보 탐색 경로를 포함합니다.

Conformer는 α-helix, 3₁₀-helix, β-extended, β-hairpin-like, PPII, turn, coil/mixed 계열 등을 시작 구조 가설로 다룰 수 있습니다(해당 화학종에 적용 가능한 범위).

**중요:** Native Docking 점수는 내부의 **무차원 포즈 탐색 지표**입니다. 결합 자유에너지 ΔG_bind, Kd, 실제 결합 친화도나 생물학적 활성으로 해석해서는 안 됩니다. Conformer별 탐색 및 경험적 접촉 항을 이용한 refinement가 완전 유연한 protein–peptide Docking을 입증하지도 않습니다.

상호작용 분석은 수소결합, 소수성 접촉, 이온성 상호작용, π 상호작용, van der Waals 충돌/접촉, 금속 배위, disulfide geometry 등의 **구조 기반 후보 신호**를 제시합니다.

---

## 비천연 펩타이드와 입체화학

Pepforge는 서열에서 잔기와 말단 수식, linker/tag 토큰을 구별합니다. 다음은 **표기 예시**이며 모든 조합의 3D·Force Field 지원을 의미하지는 않습니다.

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

| 화학 구성요소 | 취급 방식 |
| --- | --- |
| Ac, Pal | 등록된 N-terminal 수식 토큰 |
| dK 등 D-form | 지원 범위 내 입체화학 확인 및 구조화 |
| Aib, Dab 등 | 등록된 비천연 잔기. 구조/FF 지원은 화학종별 확인 |
| AEEA, Ahx, PEG | 등록된 Linker 성분 |
| FITC, Biotin | Chemical/label 토큰. 실제 원자 구조 지원 별도 확인 |

입력 문자열을 해석할 수 있다고 해서 그 화학종의 전하·원자 타입·파라미터가 검증됐다는 뜻은 아닙니다. 미지원 화학 구조를 표준 아미노산으로 몰래 치환하지 않습니다.

**PyMOL:** 전체 chemical 이름은 기본 상단 시퀀스 창 자체를 고치는 대신 선택형 **독립 토큰 패널**로 표시하고 원자/잔기 대응표를 보존합니다. PyMOL 실제 배포판에서 정상 표시되는지는 별도 확인이 필요합니다.

---

## 선택형 MD·ABFE 및 Force Field

지원되는 RDKit/MMFF94s 경로에서는 펩타이드 내부 conformer 에너지와 최적화를 계산합니다. 연구용 환경에서는 GAFF/OpenMM 수용액 MD, OpenFE ABFE, PyMBAR·Replica 진단 및 실험 Kd 비교 도구를 선택적으로 사용할 수 있습니다.

- **OpenFE 공식 ABFE 프로토콜**의 전체 결합 자유에너지 추정값을 우선하며, OpenFE가 이미 포함한 Boresch 보정값을 수동으로 다시 합산하지 않습니다.
- 실제 ΔG_bind 계산에는 검증된 noncanonical force-field 파라미터, 충분한 샘플링, 여러 독립 Replica, λ overlap, 구조 수렴, 외부 실험값 비교가 필요합니다.
- 코드·결과 JSON이나 OpenFE 설치만으로 **실제 ΔG_bind 예측 정확도가 검증됐다고 주장하지 않습니다**.

**Windows:** 기본 GUI는 Windows를 대상으로 하지만 OpenFE와 같은 선택형 과학 엔진은 **WSL2/Linux의 격리된 Conda 환경**을 권장합니다. [과학 엔진 설치 가이드](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md).

---

### Studio 탭 화면 개선 (V6.0.0)

Structure & Docking Studio는 하나의 긴 화면 대신 **같은 창 안에서 전환되는 3개 탭**으로 구성했습니다.

| 탭 | 기능 |
| --- | --- |
| **1. Structure Builder** | 서열·조건 입력, Conformer 생성, Token Map, 출력 폴더 |
| **2. Docking & Simulation** | Receptor·Binding site·Docking 설정, Mechanics 및 선택형 MD |
| **3. Results & Analysis** | 토큰/화학 분석, Ensemble 근거, Native Docking 통합 결과 |

별도 창이 열리는 것이 아니라 같은 Studio 창에서 탭 클릭 또는 `Ctrl+1/2/3`으로 전환하며, 분석 후에는 결과 탭이 자동 선택됩니다. 또한 각 탭의 **독립 세로 스크롤바**를 사용합니다. 긴 설명 문구는 UI에서 빼고 README·`MANUAL_KO.md`에 기재했습니다.

## SPPS Planner V8.0.0 Public

Pepforge 메인 런처에서 **SPPS Planner**를 선택한 뒤 **Open**을 누르면 PDE·Structure Builder와 마찬가지로 **독립된 정상 데스크톱 창**으로 SPPS Planner V8이 열립니다. Pepforge 창에 강제로 끼워 넣는 Win32 `SetParent` 방식은 사용하지 않습니다. 창 크기·DPI·모달 입력 및 키보드 포커스 문제를 줄이는 목적입니다.

- 원본 V8 Project Manager / Batch Manager / Plan / Materials / Checklist / Cleavage / Recommendations 기능을 보존합니다.
- 기존에 제거한 중복 상단 버튼은 복구하지 않습니다.
- 프로그램 본체는 **Pepforge V6.0.0**, 별도 합성 계획 모듈은 **SPPS Planner V8.0.0**으로 관리합니다.
- 소스 실행: `python -m pip install -r vendor/spps_planner_v8/requirements.txt` 이후 `python main_launcher.py --tool spps`.
- Windows 설치판: Pepforge.exe와 함께 `SPPS_Planner/SPPS_Planner.exe`를 설치해야 합니다.
- 오류 추적: `spps_v8_launch.log`.

SPPS Planner의 계산값은 합성 계획 보조 자료이며 실험 수율·순도·반응 완료를 보증하지 않습니다.


### V8 Recommendations / Plan 표 스타일 유지 개선

첨부한 최신 **SPPS Planner V8.0.0 Treeview Style Fixed** 소스를 적용했습니다. 이제 **Recommendations & Lab History** 창을 열어도 Tk 전역 `Treeview` 스타일을 바꾸지 않고, 해당 창의 표에만 `SPPS.History.Treeview` / `SPPS.History.Treeview.Heading`을 사용합니다. 따라서 **Project Manager Plan/Materials의 굵은 열 제목과 기본 행 높이**가 유지되도록 했습니다. 기존 V8의 계산 엔진·Project/Batch 기능은 변경하지 않았습니다.

소스에서 확인하려면 SPPS 모듈 폴더에서 다음 테스트를 실행합니다.

```bat
cd vendor\spps_planner_v8
python -m pytest -q tests/test_v8_recommendations_style_isolation.py
```

SPPS 요구 패키지와 `pytest` 설치가 필요합니다. Windows 실제 GUI에서 Recommendations를 열고 닫은 뒤 Plan 열 제목의 굵기와 행 높이가 유지되는지도 확인해 주세요.

## 빠른 시작

**기본 환경:** Windows 10/11 권장, Python 3.10 이상(64비트), Tk, RDKit 및 [`requirements.txt`](requirements.txt)의 필수 패키지.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

또는 의존성을 설치한 뒤 `RUN_PEPFORGE_SOURCE.bat` 실행.

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool docking
python main_launcher.py --tool spps
python main_launcher.py --tool workflow
```

### Windows 통합 설치·빌드

**`INSTALL_BUILD_TOOLS_AND_BUILD.bat` 하나만 실행**하면 메뉴에서 선택할 수 있습니다.

| 메뉴 | 실행 내용 |
| --- | --- |
| **1 — 기본 빌드** | Pepforge EXE와 Inno Setup 설치 파일 생성. 과학 엔진 미설치 |
| **2 — 전체 구성** | Windows 빌드 후 Ubuntu/Miniforge 자동 준비 시도 및 Science 설치·검증 |
| **3 — Science만** | Ubuntu/Miniforge 준비 후 `pepforge-science` 환경에 설치 또는 업데이트 |
| **4 — 설치 검사** | OpenFE CLI, OpenMM, OpenFF, PyMBAR 등 import 검사 |
| **5 — 종료** | 메뉴 종료 |

명령행에서는 `--build`, `--all`, `--science`, `--verify-science`를 선택할 수 있습니다. **Science 설치(메뉴 2·3)는 Ubuntu가 없으면 `wsl --install -d Ubuntu`를 시도하고, WSL2에 Miniforge가 없으면 공식 설치 파일의 SHA-256을 확인하여 자동 설치합니다.** Windows 관리자 승인, 재부팅, Ubuntu 최초 사용자 설정이 필요한 경우에는 진행을 멈추고 재실행을 안내합니다. 메뉴 4는 설치 작업 없이 상태만 검사합니다. OpenFE는 Windows EXE에 포함되지 않으며 실패를 성공으로 처리하지 않습니다. [상세 설명](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md).

SPPS V8: `python main_launcher.py --tool spps`.

자세한 내용은 [한국어 매뉴얼](MANUAL_KO.md)과 [영문 매뉴얼](MANUAL_EN.md)을 참고하세요.

---

## 검증 상태

| 항목 | 이번 V6.0.0에서 확인된 결과 |
| --- | --- |
| 설치기·버전·SPPS 연동 등 집중 테스트 | **42개 통과 / 실패 0** (2026-10-27) |
| Pepforge Release Gate | **25 / 25 통과** |
| Release Gate Python 컴파일 검사 | **779개 파일 / 컴파일 오류 0** |
| 문서 참조·설치기 버전·BAT/TXT 정적 감사 | **통과** |
| Pepforge 전체 회귀 검사 | **완료되지 않음** (대규모 검사 제한 시간 초과) |
| Windows GUI/EXE/Installer 및 Ubuntu/WSL2 실제 설치 | **실기 검증 미완료** |
| OpenFE ABFE 실제 MD 및 실험 ΔG_bind 정확도 | **미검증** |

레거시 V3 Docking 메뉴명 불일치를 호환성 경로에서 수정했지만, 이를 전체 테스트 통과로 간주하지 않습니다.

로컬 확인 명령:

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

단위 테스트 통과와 화학·물리 계산의 실험 정확도 입증은 서로 다릅니다. [검증 현황 문서](docs/RELEASE_STATUS_V6.0.0.md), [공개 체크리스트](PUBLICATION_CHECKLIST.md)를 참고하세요.

---

## 과학적 사용 범위

**적합:** 후보 우선순위, 지원 화학종의 구조 가설, Docking·상호작용 스크리닝, 실험을 위한 SPPS 계획, Provenance 및 재현성 분석.

**입증하지 않는 것:** 실제 Kd/Ki, 검증된 결합 자유에너지, 생체 내 천연 구조, 생물학적 효능, 실험 수율·순도, 모든 비천연 화학종의 FF 지원, 장시간 MD 수렴 여부, AF3·ESMFold보다 우수한 구조 예측 정확도.

외부 구조 예측 서비스를 사용하는 경우 미공개 서열·회사 자료의 전송 여부를 반드시 확인하세요.

---

## 저장소 및 문서

주요 경로: `main_launcher.py`, `pepforge_cli.py`, `suite_gui/`, `peptiforg_core/`, `pepforge_structure_tool/`, `apps/`, `vendor/spps_planner_v8/`, `tests/`, `docs/`, `installer/`.

- [영문 README](README.md) / [English Manual](MANUAL_EN.md) / [한국어 매뉴얼](MANUAL_KO.md)
- [SPPS V8 연결 안내](SPPS_V8_INTEGRATION_README_KO.md)
- [과학 엔진 설치](SCIENCE_ENGINE_INSTALL_GUIDE_KO.md)
- [GitHub 공개 데이터 정책](PUBLIC_DATA_POLICY.md)
- [인용 정보](CITATION.cff) / [LICENSE](LICENSE)
- [개발 이력](CHANGELOG.md) / [기여 안내](CONTRIBUTING.md) / [보안 문의](SECURITY.md)

런타임 결과물, 비공개 서열·실험 기록, 키·인증 정보, 미공개 학습 데이터는 공개 저장소에 넣지 않습니다.

**라이선스:** 기존 사용자 정의 학술 인용 라이선스를 유지합니다. OSI 승인 오픈소스 라이선스가 아니며, 제3자 구성요소는 각자의 라이선스를 따릅니다. 문서 수정은 법적 공개 승인을 의미하지 않습니다.

---

<div align="center">

**Pepforge V6.0.0**  
*비천연 펩타이드 설계부터 구조 생성, Docking, SPPS V8, 과학적 검증까지.*

</div>


## V6.0.0 Docking 입력·결과 개선

- **수용체 파일:** `.pdb`, `.cif`, `.mmcif` 지원. mmCIF는 Biopython 기반 PDB 좌표 변환 후 검증하며 Gemmi를 보조 변환기로 사용합니다. 원본 구조를 보존하고 chain/alternate location/ligand/원자 누락을 검토하세요.
- **펩타이드 파일:** 3D 구조가 있는 PDB/mmCIF/SDF/MOL. Structure Builder와 Docking 탭은 서열 입력을 공유합니다.
- **Docking 실행:** `BUILD + DOCK + ANALYZE`는 파일 기반 입력에서 Native Pose Search를 실행하고 **검증된 Pose와 상호작용을 Results & Analysis에 바로 표시**합니다. 오류 또는 Pose 0개는 성공 처리하지 않습니다.
- **결과 화면:** 결과 열기, Pose 열기, 3D 보기, Report 저장, 해석을 기본 버튼으로 배치하고 비교·상세 도구는 `Advanced tools`에서 엽니다.
- **진행률:** 실제 탐색 시도/완료 단계를 기준으로 색이 왼쪽에서 오른쪽으로 찹니다. 실측할 수 없는 작업의 남은 시간이나 계산 비율은 임의로 생성하지 않습니다.
- **검증 범위:** 테스트용 구조의 PDB/mmCIF 실제 Docking 및 가상 디스플레이 Tk GUI 확인. 모든 사용자 구조, Windows 설치 EXE, OpenMM/ABFE 계산 정확도는 별도 검증이 필요합니다.

사용 방법과 오류 대응은 [MANUAL_KO.md](MANUAL_KO.md)를 참고하세요.
