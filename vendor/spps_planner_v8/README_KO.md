<div align="center">

<img src="assets/SPPS_Planner_Icon.png" alt="SPPS Planner" width="150">

# SPPS Planner V8.0.0

**Windows 기반 고체상 펩타이드 합성(SPPS) 계획·시약 계산·실험 근거 검토 프로그램**

Project Manager · Optional Auto Plan · Sequence Risk Map · Editable Plan · Materials · Checklist · Batch Manager · Loading/Cleavage Recommendations · Workup · Experimental History

[![Version](https://img.shields.io/badge/release-V8.0.0-2563EB?style=for-the-badge)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#빠른-시작)

**[English README](README.md) · [English Manual](docs/USER_MANUAL_EN.md) · [한국어 사용자 매뉴얼](docs/USER_MANUAL_KO.md)**

**Repository:** [SanghunWoo-23/SPPS-PLANNER](https://github.com/SanghunWoo-23/SPPS-PLANNER)

</div>

> **V8.0.0 Public 소스 배포본.** ZIP에 소스와 Windows 빌드 BAT이 포함됩니다. 빌드된 EXE 또는 Installer 자체는 포함되지 않습니다. 실제 Windows GUI 실행·설치·업그레이드·제거 검증은 아직 완료하지 않았습니다.

## 개요

SPPS Planner는 **Project Manager**를 중심으로 계산 가능한 SPPS 계획과 실험 검토를 지원합니다. V8은 기존 화학 엔진과 Tkinter Step 1·2 편집 UI를 유지하면서 선택형 Auto Plan, 서열 위험 설명, Loading/Cleavage 추천 가독성, 긴 페이지 스크롤, 프로젝트 저장 안정성을 강화합니다. **실험 절차를 자동 확정하는 최적화 프로그램은 아닙니다.**

```text
Project Manager → Peptide Add / Edit
     ↓
Sequence + Scale + Copies + Resin + Loading + 정확한 시약 bottle
     ↓
Generate   또는   Auto Plan (Optional) → 조건 검토 → Generate Full Plan
     ↓
Plan ─── Materials ─── Checklist ─── Total Materials
  └──── Cleavage Cocktail ─── Workup
     ↓
Sequence Risk Map / Loading·Cleavage Recommendation / 실험 기록
     ↓
Batch Manager · Export · 실험자 검토 · 실제 실험 검증
```

## V8.0.0 핵심 기능

### Project Manager 버튼 정리

Project Manager 버튼은 **Generate → Apply Change → Auto Plan (Optional) → Recommendations & Lab History → Sequence Risk Map → Save Session Now** 순서입니다. Auto Plan은 **Apply Change 바로 옆**에 있고 Generate와 같은 **파란색 주요 작업 버튼**입니다. Loading Advice, Cleavage Advice, Record Lab Data는 메인 화면의 중복 단축 버튼만 제거했으며, 기능은 **Recommendations & Lab History**의 Loading/Cleavage 추천 및 Advanced → History에 보존했습니다.

**Recommendations & Lab History** 상단 작업 버튼은 **Preflight → Start Experiment → Add Result → Add Issue → Final Result → Finish → Repeat Run** 순서이며, 오른쪽에 **Refresh → Data Store → Backup DB**를 배치했습니다. `Add Issue`는 문제가 발생할 때만 사용합니다. 실험 시작 이후의 실제 결과·이슈는 시작 시 고정된 Run 조건에 연결됩니다.

### Auto Plan (Optional)

선택한 펩타이드의 서열, Scale, Copies, Resin, Loading, Coupling 조건과 이론적 Resin 수요를 **미리 확인**하는 선택 기능입니다. 미리보기만 열면 입력값이 바뀌지 않습니다. **Generate Full Plan** 승인 후 기존 엔진으로 전체 계획을 생성합니다. 필수값이 없거나 잘못되면 작업자가 수정해야 합니다. 서열만으로 최적 Cleavage Cocktail·시간·수율·성공 확률을 검증하거나 확정하지 않습니다.

### Project Manager / Batch Manager

- 프로젝트/펩타이드명, 서열, Scale, Copies, Resin/Loading, LOT, Coupling Reagent, Additive, Base, Solvent 및 정확한 시약병 선택.
- **My Recipes:** 저장/불러오기/이름 변경/삭제/즐겨찾기/백업·가져오기/최근 선택.
- 기존 **Generate / Apply Change**, Plan 직접 편집, Materials, Checklist, Total Materials, Cleavage, Workup 유지.
- Batch Manager의 용액 제조 기본값은 Project Manager의 개별 시약 선택 때문에 몰래 변경되지 않습니다.

### Loading·Cleavage 및 합성 계산

- **2-CTC 직접 Loading 기본값:** Resin **1 eq**, Amino acid **2 eq**, DIEA **4 eq**. 이미 Loading된 Resin은 해당 옵션을 해제합니다.
- Resin 및 반응 조건별 계산·편집 방식은 기존 검증된 엔진과 설정을 사용합니다.
- Cleavage 시약량은 기존 서열/Cys 규칙으로 계산하며 Cocktail과 침전·Workup 용매를 구분합니다.
- Workup: Ethyl Ether, n-Hexane, Ether/n-Hexane 1:1 및 사용자 지정 부피.
- **NMM은 염기**, **NMP는 용매**로 구분합니다.

### Sequence Risk Map / Recommendation / History

- 잔기 위치, 규칙 ID, 경고 수준과 설명을 제공하는 **규칙 기반 위험도**. 실제 실패 확률이 아닙니다.
- Loading/Cleavage 요약 영역에서 조건과 근거 출처·적용 가능성·불확실성을 보다 명확히 표시합니다.
- 화학 기본값·실험 이력·사용자 승인 조건을 구분합니다. 근거 부족한 내용은 확정 SOP가 아닙니다.
- Recommendations & Lab History 긴 탭에 세로 스크롤과 마우스 휠·스크롤바 드래그 지원을 추가했습니다. Step 1·Step 2는 유지합니다.

### 저장과 공개 데이터 보호

- JSON 구조 검증, 원자적 저장, 정상 백업 및 파일 변경 감지로 일반적인 저장 사고를 줄였습니다.
- 다중 프로세스·정전·클라우드 동기화·백신·파일 권한 문제를 100% 방지하는 것은 아닙니다.
- **Public ZIP은 Private 실험 시드·회사 기록·로컬 DB·사용자 프로젝트·레시피를 포함해서는 안 됩니다.** 임의로 가져온 파일의 공개 책임은 사용자에게 있습니다. [Public 데이터 정책](PUBLIC_DATA_POLICY.md)을 참고하세요.

### 추천 창을 열어도 Plan 표 글꼴 유지

`Recommendations & Lab History`를 열 때 메인 `Plan` 표의 `Unit name`, `MW`, `Density` 등 **열 머리글의 굵은 글씨가 풀리던 문제**를 수정했습니다. 추천/실험기록 창의 표는 전용 `ttk.Treeview` 스타일을 사용하므로 메인 표의 글꼴과 행 높이를 변경하지 않습니다. 화학 계산이나 저장된 데이터는 변경하지 않았습니다.

## 빠른 시작

**권장 환경:** Windows 10/11, Python 3.11 또는 3.12 (64-bit, Tk 포함).

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

### Windows EXE / Installer — BAT 하나로 빌드

Windows 10/11에서 **전체 ZIP을 압축 해제**하고 `INSTALL_BUILD_TOOLS_AND_BUILD.bat` 파일을 더블클릭합니다. 콘솔 자동 실행에서는 `--no-pause`를 붙일 수 있습니다.

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

- **Python 3.11/3.12 64비트**, **Inno Setup 6/7**을 확인하고 없으면 `winget`으로 설치를 시도합니다.
- Python 의존성 설치 → V8 정적 검사 → 소스 self-test → PyInstaller EXE 빌드 → EXE self-test 및 보고서 확인 → Inno Setup Installer 생성 → 결과물 검증 순서입니다.
- 인터넷 연결이나 설치 권한이 없으면 실패할 수 있으며, `winget`을 사용할 수 없는 PC에서는 도구를 수동 설치한 후 다시 실행해야 합니다.

생성 파일:

- `dist\SPPS_Planner\SPPS_Planner.exe` — EXE 단독 파일만 복사하지 말고 해당 폴더 전체를 보존.
- `installer\output\SPPS_Planner_Setup_V8.0.0.exe` — Windows 설치 파일.

**BAT은 설치 파일을 만드는 스크립트이지 SPPS Planner를 직접 설치하는 파일은 아닙니다.** 이 소스 ZIP에는 완성된 EXE/Installer가 들어 있지 않습니다. 실제 Windows GUI, 설치, 업그레이드 및 제거 시험은 별도 검증이 필요합니다. [Windows 빌드 안내](docs/WINDOWS_BUILD_KO.md).

### 소스 테스트

```bat
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python tools\verify_windows_release.py
```

## 배포 파일을 최소화한 기준

- **BAT은 1개만 유지:** `INSTALL_BUILD_TOOLS_AND_BUILD.bat`이 필요한 도구 준비, EXE·Installer 빌드, self-test와 검증을 모두 수행합니다.
- **`VERSION`과 `VERSION.txt` 둘 다 유지:** 앱 버전 검사·PyInstaller 리소스에서 각자 사용됩니다.
- **내부 `SPPS data v6.0.0` 표기:** 기존 저장 데이터 호환성을 위한 스키마 식별자로, 프로그램의 실제 릴리스 버전 V8.0.0과 구분됩니다.
- **`requirements.txt`와 `requirements-dev.txt`:** 실행/빌드 및 테스트 의존성.
- **`installer/version_info.txt`:** Windows EXE의 파일 버전 리소스. 일반 설명 문서가 아니어서 필수입니다.
- **`apps/spps_planner_app/requirements.txt`:** 별도 부속 앱의 의존성 목록으로 데스크톱용 파일의 단순 중복이 아닙니다.
- **`RELEASE_NOTES_V8.0.0.txt`:** 단일 V8 소스 릴리스 노트. ZIP 파일을 다시 압축하면 SHA가 바뀌므로 자산 체크섬은 별도 제공.
- 과거 V7/Beta 개발 보고서와 중복 패키지 소개 문서는 제외하고 코드·테스트·사용자 매뉴얼·화학 참조 파일은 유지했습니다.

## 검증 현황 및 과학적 한계

최신 **소스 회귀시험 결과**와 실제 Windows **미검증 항목**은 `RELEASE_NOTES_V8.0.0.txt`를 확인하세요. Linux/headless 테스트나 정적 검사는 Windows GUI/EXE/Installer 실사용 검증과 다릅니다.

SPPS Planner의 결과는 합성 성공, Coupling 완료, Cleavage 최적 조건, 수율, 순도 또는 생물학적 효능을 증명하지 않습니다. 승인된 SOP, SDS, 안전 규정, 숙련된 실험자 검토, 검증된 분석 방법 및 필요한 GMP/GLP 문서를 대신하지 않습니다.

## 개발·배포 인수인계

후속 개발자/AI 개발 세션용 개발 절차, README·GitHub Release 작성법, 테스트와 체크섬 관리 규칙은 [개발·배포 인수인계서](docs/DEVELOPMENT_HANDOVER_V8.0.0.md)를 참고하세요. 이 문서는 일반 사용자 매뉴얼과 별도로 유지합니다.

## 문서와 인용

[영문 매뉴얼](docs/USER_MANUAL_EN.md) · [한글 매뉴얼](docs/USER_MANUAL_KO.md) · [구조 설명](docs/ARCHITECTURE.md) · [Windows 빌드 가이드](docs/WINDOWS_BUILD_KO.md) · [Public 데이터 정책](PUBLIC_DATA_POLICY.md)

[LICENSE](LICENSE)는 **사용자 정의 학술 인용 라이선스**로 OSI 승인 오픈소스 라이선스가 아닙니다. [CITATION.cff](CITATION.cff)와 실제 배포 태그를 함께 확인해 인용하세요.

> Woo, S. **SPPS Planner: Solid-Phase Peptide Synthesis Planning and Evidence-Driven Decision Support.** V8.0.0 (2026). https://github.com/SanghunWoo-23/SPPS-PLANNER
