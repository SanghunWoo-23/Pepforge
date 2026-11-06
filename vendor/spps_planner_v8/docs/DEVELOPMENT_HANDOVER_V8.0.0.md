# SPPS Planner V8.0.0 — 개발·검증·배포 인수인계서

> 기준: 2026-10-28 / Public: GitHub 배포용 소스 / Private: 내부 보관·개발용 소스  
> 이 문서의 목적: 후속 개발자 또는 ChatGPT 세션이 **기존 앱을 파괴하지 않고** V8.0.0을 이어 개발하고, README 및 GitHub Release를 검증 가능한 사실만으로 작성·배포하도록 하는 것.  
> **소스 기반 검사와 실제 Windows 설치 검증은 다르다.** 확인하지 않은 기능을 `PASS`, `Final verified` 또는 실험적으로 검증된 프로토콜로 표시하지 않는다.

## 1. 기준 버전과 산출물

- 기준 소스: `SPPS_Planner_V8.0.0_PUBLIC_GITHUB_HANDOVER_2026-10-28.zip`와 `SPPS_Planner_V8.0.0_PRIVATE_INTERNAL_HANDOVER_2026-10-28.zip`에서 각각 분기. 이번 변경은 **Project Manager 버튼 배치·색상**, **Lab History 실험 진행 순서** 및 문서/테스트 한정이며, 화학 계산 엔진은 변경하지 않음.
- 앱 표기: **SPPS Planner V8.0.0**. 실제 Project Manager 버튼 문구는 **`Auto Plan (Optional)`**. `— 오른쪽 끝`은 위치 설명일 뿐 실제 버튼 라벨이 아니다.
- 배포: **Public ZIP만 GitHub 공개**. Private ZIP은 실험 자료와 내부 코드를 포함하므로 공개 금지.
- GitHub Release 본문은 영어 Markdown 서식의 `.txt`로 외부 제공하고, 소스 ZIP에는 간결한 `RELEASE_NOTES_V8.0.0.txt`를 유지한다.
- 버전 확인 위치: `VERSION`, `VERSION.txt`(둘 다 `V8.0.0`), `apps/spps_planner_app/spps_planner/version.py`(`VERSION_NUMBER="8.0.0"`), `installer/SPPS_Planner_Setup.iss`, `installer/version_info.txt`, 창 제목, `CITATION.cff`, README, Release Notes.
- 내부 스키마 식별자 `SPPS data v6.0.0`은 과거 저장 자료 호환용이며 V8 앱 버전 오류가 아니다. 임의 변경 금지.

### 현재 확인한 소스 상태 (이전 배포 검증 기록)

| 항목 | Public | Private |
|---|---|---|
| 이번 Linux/headless 전체 회귀시험 | **474 passed / 48 skipped / 0 failed** | **476 passed / 46 skipped / 0 failed** |
| 배포 소스 정적 검사·컴파일 | 통과 기록 | 통과 기록 |
| Linux 가상 디스플레이 Tkinter 기본 UI 확인 | 통과 기록 | 통과 기록(범위는 개별 로그 확인) |
| Windows 실제 GUI 및 EXE·Installer 설치·업그레이드·제거 | 미검증 | 미검증 |

이번 테스트는 2026-10-29 Treeview 스타일 격리 회귀시험을 포함한 독립 Public/Private 소스 기준이며, 코드 및 문서 재포장 뒤 최종 산출물은 별도로 무결성을 확인한다. 테스트 건너뜀을 PASS로 해석하지 말고 Windows 실행 검증과 구분한다. 새 기능/코드 변경 시 이 숫자를 재사용하지 않는다.


**2026-10-29 검증 업데이트:** 일반 headless 전체 테스트는 Public **474 passed / 48 skipped**, Private **476 passed / 46 skipped**. 새 `test_v8_recommendations_style_isolation.py`는 디스플레이 없는 전체 실행에서는 GUI 테스트 1건을 skip하며, **Linux Xvfb에서는 Public·Private 각각 2 passed**. Python 문법 검사와 `tools/verify_windows_release.py` 정적 검사는 양쪽 통과. 이는 Windows 설치 검증이 아니다.

## 2. 사용자가 정한 개발 원칙

1. **기존 Windows/Tkinter GUI 유지**: Project Manager Add/Edit, Batch Manager, Step 1/Step 2, Generate, Apply Change 및 editable Plan 유지. HTML 프로토타입이나 새로운 Quick Synthesis 중심 화면으로 대체하지 않음.
2. **편집성 우선**: 옵션을 숨겨 간결하게 보이게 하기보다 중요 작업의 접근성과 조작성 보존.
3. **단일 계산 권위**: `apps/spps_planner_app/spps_planner/engine.py` 및 현재 계산 흐름이 기준. 다른 페이지에 유사 계산을 복제하지 말 것. 단순 UI/패키징 수정 중 엔진 해시 변경 금지.
4. **과학적 근거 구분**: Chemistry default / Rule-based / Operator-approved anchor / Experimental observation / Insufficient evidence를 구별. 데이터가 저장되었다고 검증된 추천·ML 결과가 되는 것이 아님.
5. **Private 자료 보호**: Public에 Private 실험 시드, SQLite DB, 프로젝트 기록, 민감 서열, 사진, 내부 모델 아티팩트를 복사하지 말 것. 수동 DB import를 지원하는 것과 Private 데이터 자동 포함은 별개.
6. **검증 사실만 보고**: pytest PASS, skip, static check, 가상 GUI, Windows native GUI, EXE build, Installer install 각각 독립 상태로 기록.
7. **최종 산출물**: Public ZIP, Private ZIP, 별도 GitHub Release TXT, 외부 SHA256SUMS 파일. README EN/KO와 사용자 매뉴얼을 함께 정리하되 비슷한 과거 개발 보고서를 루트에 계속 늘리지 않음.

## 3. 실제 프로그램 구조 및 수정 위치

| 역할 | 기준 위치 |
|---|---|
| 앱 시작/윈도우 | `main_launcher.py`, `suite_gui/release.py`, `suite_gui/controller.py` |
| Project Manager 및 버튼 | `suite_gui/classic_base.py`, `suite_gui/modules/project_manager_panel.py`, 관련 workflow |
| Auto Plan | `suite_gui/classic_base.py`의 `open_auto_plan_option` 호출, `tests/test_v8_optional_auto_plan.py` |
| Recommendations & Lab History | `suite_gui/modules/experimental_data_panel.py`, `suite_gui/recommendation/` |
| Sequence Risk | `suite_gui/sequence_risk_ui_v8.py`, `suite_gui/risk_workflow.py`, `suite_gui/sequence_risk_map_v8.py` (실제 import 경로 확인) |
| 프로젝트 저장/복구 | `suite_gui/persistence_workflow.py`, `suite_gui/state_persistence.py` |
| 화학 계산 엔진 | `apps/spps_planner_app/spps_planner/engine.py` |
| 공개/비공개 데이터 경계 | `PUBLIC_DATA_POLICY.md`, Private의 `PRIVATE_DATA_POLICY.md`, `DO_NOT_PUBLISH_PRIVATE_BUILD.md` |
| Windows 빌드 | **유일한 BAT** `INSTALL_BUILD_TOOLS_AND_BUILD.bat`, `SPPS_Planner.spec`, `installer/SPPS_Planner_Setup.iss` |
| 검증 | `tests/`, `tools/verify_windows_release.py`, `tools/verify_release.py`, `tools/verify_packaged_runtime.py` |

### 현재 Project Manager 버튼의 정확한 구성

- 좌측에서 오른쪽 순서: `Generate` → `Apply Change` → **`Auto Plan (Optional)`** → `Recommendations & Lab History` → `Sequence Risk Map` → `Save Session Now`.
- Auto Plan은 **Apply Change 바로 뒤**이며 `pack(side='left')`, `style='Accent.TButton'` (Generate와 같은 파란색 계열). `— 오른쪽 끝`을 텍스트에 붙이지 않는다.
- **Recommendations & Lab History** 실험 버튼 순서: `Preflight` → `Start Experiment` → `Add Result` → `Add Issue` → `Final Result` → `Finish` → `Repeat Run`. 이후 관리 버튼: `Refresh` → `Data Store` → `Backup DB`. `Add Issue`는 필요할 때만 사용하는 선택형 기록이며, 버튼 순서를 바꾼다고 Run 상태/기록 처리 코드를 변경하지 않는다.
- 워크플로우 단계와 버튼의 실제 표시 순서가 일치하도록 `suite_gui/modules/experimental_data_panel.py`에서 레이아웃만 편집한다. `test_v8_project_manager_ui_compact.py`로 버튼 순서를 회귀 검증한다.
- `Loading Advice`, `Cleavage Advice`, `Record Lab Data`는 **메인 단축 버튼만 제거**했으며, 통합 Recommendations 창의 Loading/Cleavage 탭과 Advanced/History 및 Add Result/Final Result/Add Issue 기능은 보존해야 한다.
- Auto Plan은 선택형 미리보기·승인 경로. 미리보기만 열어도 레진/계산 조건을 몰래 바꾸거나 근거 없는 cleavage cocktail/time을 확정하지 말 것.

### 2026-10-29 UI 회귀 수정: 추천 창 열기 시 Plan 헤더 굵기 유지

- **증상:** `Recommendations & Lab History`를 열면 Project Manager의 `Unit name`, `MW`, `Density` 등 `Treeview` 열 머리글의 굵은 글씨와 표 행 높이가 달라짐. 추천 창을 닫아도 변경이 유지될 수 있음.
- **원인:** `suite_gui/modules/experimental_data_panel.py`의 `_configure_styles()`가 공통 `ttk.Style`의 `Treeview` 및 `Treeview.Heading`을 재설정함. `ttk.Style`은 창별이 아니라 하나의 `Tk` 인터프리터에 공유되는 스타일 레지스트리임.
- **수정:** 추천/실험기록 표에만 `SPPS.History.Treeview` 및 `SPPS.History.Treeview.Heading` 스타일을 정의하고 `_tree()`에서 `style="SPPS.History.Treeview"`로 적용. 앱 전체 `Treeview` 스타일은 여기서 변경하지 않음.
- **재발 방지:** `Toplevel`/다이얼로그에서 `style.configure("Treeview", ...)`, `style.configure("Treeview.Heading", ...)` 및 전역 `ttk.Style().theme_use()`를 호출하지 않는다. 필요할 때는 **창 이름이 포함된 스타일 이름**을 지정하고 해당 창 위젯에 명시적으로 할당한다. 단, 공통 테마 전환은 별도 합의 없이 변경 금지.
- **회귀시험:** `tests/test_v8_recommendations_style_isolation.py`는 추천 창 스타일 설정 전후의 공통 스타일 font/rowheight 불변성과 추천 창 고유 스타일 적용을 검사. 실제 Windows 화면에서 글꼴 렌더링은 별도 검증 필요.
- 이 수정은 시각적 스타일 분리만이며 `engine.py`, 시약 계산, 실험 DB 로직은 변경하지 않는다.

## 4. 화학 규칙과 데이터 안정성 불변 조건

- 현재 `engine.py` 기준 SHA-256: `5cf59ad71ea1637df4768d812612a86635b31c691efc153f93ef328d736108de` (이번 문서 작업 시작 시 양 분기에서 직접 확인).
- 2-CTC 직접 loading 기본: resin 1 eq, amino acid 2 eq, DIEA 4 eq; 이미 loaded resin은 옵션 off. 다른 레진에 자동 적용하지 않음.
- Cys 보유 서열의 cleavage TFA 기준은 **Cys 수 × 100 eq**이며 기존 길이 기준과 중복 더하지 않음. 계산법 변경은 과학적 근거·회귀 테스트가 필요.
- NMM은 base(N-methylmorpholine), NMP는 solvent(N-methyl-2-pyrrolidone). 이름이 비슷하다고 동종 시약으로 매핑 금지.
- Gly는 무키랄; D/L 잔기별 실제 실험 근거는 구분. 근거 범위 밖의 무근거 보간을 실제 관측으로 표현하지 않음.
- Met만 있다는 이유로 NH4I 자동 투입 금지, TIS 무조건 자동 추가 금지. Cleavage cocktail과 post-cleavage ether/n-hexane workup을 별도로 계산.
- 권고 근거는 시퀀스·잔기 위치·조건·lot·날짜·검토 상태·원자료가 추적 가능해야 함. 생성·저장과 검증 승격을 구분.
- 프로젝트 JSON은 유효성 확인 후 읽고, 원자 저장·백업 보존·동시 저장 충돌 감지 정책을 유지. 다른 프로세스/클라우드/백신/전원 장애에 대한 절대 무결성 보장은 아님.

## 5. 이후 코드를 수정할 때의 필수 순서

1. **Public·Private ZIP을 별도 폴더에 clean unzip**. 서로의 소스를 덮어쓰기 금지. 변경 전 코드와 `engine.py` SHA-256을 기록.
2. 사용자 요청을 화면 변화 / 계산 규칙 / I/O / 데이터 보안 / 배포 형식으로 나눠 영향 파일을 식별.
3. 가장 좁은 범위의 코드 수정 후 새 테스트 작성. UI 버튼 수정 시 실제 위젯 텍스트와 Command, 다른 탭으로의 접근성까지 확인. 중복 버튼 제거 시 **기능 자체가 보존되는지** 테스트.
4. 기존 화학 엔진 결과 스냅샷이 의도치 않게 바뀌지 않았는지 확인. 정량 수율·확률·모델 성능을 근거 없이 발명하지 말 것.
5. Public·Private를 **각각** 정적 검사·전체 테스트·컴파일; GUI가 핵심이면 가상 디스플레이 스모크 테스트, Windows 전용 기능은 Windows 머신에서 별도 확인.
6. Release 문서와 README EN/KO를 **실제로 구현·검증한 사실** 기준으로 갱신. README는 사용설명, Release는 변경사항·검증 중심.
7. Public에는 Private 전용 파일이 전혀 없는지 ZIP 내부 경로·파일 내용을 점검. `.db`/`.sqlite`/`.sqlite3`, `experimental_seed` 등뿐 아니라 수동 포함된 프로젝트/CSV를 확인.
8. 필수 빌드 파일을 보존하면서 ZIP 파일 수 최소화. 테스트와 매뉴얼·의존성·아이콘·라이선스를 파일 수만 줄이려고 삭제하지 말 것.
9. `SOURCE_MANIFEST.sha256`을 최종 파일 바이트 기준으로 재생성(자기 자신 제외), ZIP을 생성한 뒤 **외부에서 ZIP SHA-256** 계산.
10. GitHub Release TXT에 **정확한 새 Public ZIP 이름·외부 체크섬** 기입. 체크섬을 ZIP 안의 Release에 박아 자기참조 순환을 만들지 말 것.
11. 최종 다운로드 링크는 컨테이너에서 해당 경로의 파일 존재·크기·압축 무결성을 확인한 후 제공.

### 기본 검증 명령

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=.:apps/spps_planner_app python -m pytest -q
PYTHONPATH=.:apps/spps_planner_app python tools/verify_windows_release.py
python -m compileall -q main_launcher.py suite_gui peptiforg_core apps/spps_planner_app/spps_planner
sha256sum apps/spps_planner_app/spps_planner/engine.py
```

Windows CMD에서는 `PYTHONPATH`를 `set PYTHONPATH=.;apps\spps_planner_app`로 지정하고, Windows 전용 항목은 Windows에서 직접 검증한다. 설치·제거·업그레이드·GUI 스크롤 등은 Linux 정적 검사와 별도 체크리스트로 관리한다.

### Windows 실제 배포 검증(미완료 → 후속 필수)

- Windows 10/11 x64 격리 환경, Python 3.11 또는 3.12와 Inno Setup 6/7 확인.
- 깨끗한 ZIP 해제 → `INSTALL_BUILD_TOOLS_AND_BUILD.bat` 실행 → `dist\SPPS_Planner\SPPS_Planner.exe` 및 `installer\output\SPPS_Planner_Setup_V8.0.0.exe` 생성 확인.
- 새 설치·바로가기·실행·종료·재설치·업그레이드·제거·사용자 데이터 보존 확인.
- Project Manager → Generate / Apply Change / Auto Plan / Batch Manager / Save·Open / V7 프로젝트 가져오기 확인. Recommendations & Lab History에서는 Preflight → Start Experiment → Result / Issue → Final Result → Finish → Repeat Run → Data Store / Backup DB의 표시 순서, 활성화 상태, 실제 동작 확인.
- 낮은 화면 높이, 스크롤바 드래그, 마우스 휠, 한글·OneDrive 경로, 읽기 전용 파일, 손상된 JSON 및 backup 복구 확인.
- 결과를 'Pass / Fail / Skip / Not tested'로 분리하고 실행 환경·증거 로그를 기록.

## 6. README 작성·수정 방법 (중요)

README는 **처음 다운로드한 사람이 실제로 실행하고 기능을 이해할 수 있는 안내서**다. Release Notes를 복사해 중복 설명을 늘어놓지 않는다. 코드와 배포 구조가 바뀔 때 같이 갱신한다.

### 파일과 언어

- **`README.md`**: GitHub 기본 페이지, 영어, 공개 사용자 대상.
- **`README_KO.md`**: 동일 정보의 한국어판. 영문 내용과 수치, 기능 범위, 미검증 항목 일치.
- **`docs/USER_MANUAL_EN.md`, `docs/USER_MANUAL_KO.md`**: 화면별 상세 사용법·단계별 설명. README에는 요약과 링크만.
- Private README: 내부 보관용임을 명시. Public README에서 Private 실험 자료나 내부 자료 존재를 상세 홍보하지 않음.

### README 권장 목차 및 작성 순서

1. 상단: `assets/SPPS_Planner_Icon.png` 이미지, `# SPPS Planner V8.0.0`, 간결한 영어 한 줄 설명, 주요 기능 키워드, **실제 버전·Python·Windows 배지**.
2. `README_KO.md`·영문/한글 매뉴얼 링크와 올바른 Repository URL.
3. **Release status**: Public **source ZIP**인지 설치형 EXE인지 정확하게 기술. Windows native 미검증이라면 바로 상단에 알림.
4. `Overview`: 프로그램 목적과 V7 → V8 실제 차이. 허위 autonomous protocol optimizer 표현 금지.
5. `Workflow` 코드 블록: Sequence/Scale/Resin/Loading → Generate **또는** Auto Plan (Optional) 검토 → Plan/Materials/Checklist/Total Materials/Cleavage/Workup → Risk/Recommendation/History.
6. `Highlights`: Project Manager, Auto Plan, Sequence Risk Map, Recommendations & Lab History, Batch Manager, 로컬 레시피, 저장/복구. 실제 UI 이름을 **코드에서 확인**하고 정확히 표기.
7. `Chemistry & Workup`: 사용자 설정과 규칙 기반 계산의 경계, 2-CTC/Cys·근거 등급·주의사항.
8. `Quick start`: Windows 요구사항, Python venv, `requirements.txt`, `main_launcher.py`; 명령은 해당 ZIP에서 동작하는지 확인.
9. `Windows build`: **단일 BAT** `INSTALL_BUILD_TOOLS_AND_BUILD.bat`와 필요 도구, EXE/Installer 예상 산출 경로, 실제 Windows 검증 여부.
10. `Public data policy`: Private 자료·실험 DB 미포함 정책 및 import 책임.
11. `Verification / limits`: **실제 측정한** pytest pass/skip/fail, 정적 검사, GUI/설치 미검증, 과학적 한계.
12. `Documentation, License and Citation`: README/매뉴얼/인수인계서 링크, **CUSTOM LICENSE** 고지, `CITATION.cff`, 버전 정확히 일치.

### README 작성 절대 규칙

- GitHub 내부 상대 링크 (`README_KO.md`, `docs/...`, `assets/...`)가 ZIP에서 실제 존재하는지 검사.
- `V7`이 등장한다고 무조건 삭제하지 말고, **이전 버전 비교·이전 프로젝트 가져오기** 문맥인지 구별. 현재 앱의 제목·배지·설치 파일명이 V8인지 별도 확인.
- UI에서 버튼 라벨은 정확히 `Auto Plan (Optional)`이다. **현재는 Apply Change 바로 옆**이다. 이전의 `— 오른쪽 끝`은 버튼 이름이 아니었으며 위치 또한 변경됐다.
- `RELEASE_NOTES_V8.0.0.txt` 등 근거 파일에 없는 테스트 숫자를 생성하지 말 것.
- 과학적 자동 추천을 'validated best condition', 'guaranteed yield', 'production-grade SOP'라고 표현하지 말 것.
- `LICENSE`의 실제 조건을 확인; 저장소의 **커스텀 학술 인용 라이선스를 OSI 승인 오픈소스라고 표현 금지**.
- 사용자가 요청한 README 중심 기록을 우선하고, 매번 루트에 임시 설명 TXT를 추가하지 말 것.

## 7. GitHub Release TXT 작성·배포 방법 (매우 중요)

GitHub Release는 **새 버전의 변화, 주요 사용 흐름, 검증 결과, 과학적 한계, 정확한 다운로드 파일**을 전달하는 문서다. 사용자가 제공한 **Pepforge V5.0.0 Release 형식**을 본보기로 사용한다. GitHub 입력란은 Markdown을 렌더링하므로 **파일 확장자는 `.txt`여도 내용은 영어 Markdown**으로 작성한다.

### GitHub Release 권장 구성

1. **한 줄 개요**: `Integrated SPPS project planning, optional Auto Plan, sequence risk screening, and evidence-aware recommendations` 같은 검증 가능한 표현.
2. `# SPPS Planner V8.0.0 — GitHub Public Source Release`: 현재 버전·공개 분기 명시.
3. 2~3문장 overview: V7 대비 달라진 점, 기존 UI/계산 엔진 보존 및 사용자가 얻는 가치.
4. `## Highlights`와 기능별 소제목: Optional Auto Plan / Project Manager & Batch / Sequence Risk & Recommendations / UI/UX / Persistence & Public boundary.
5. `## Workflow`로 실제 앱 흐름을 텍스트 트리로 표시.
6. `## Verification` **표**: PASS/SKIP/FAIL을 각각 분리, headless/static/virtual GUI/Windows 실제 검증을 혼동하지 않음.
7. `## Scientific scope`: 무엇을 지원하고 무엇을 보장하지 않는지 분리.
8. `## Requirements`: Windows 목표 버전, Python/Tk, 설치 도구, source vs installer 차이.
9. `## Source`: `https://github.com/SanghunWoo-23/SPPS-PLANNER`, README EN/KO 및 매뉴얼 링크.
10. `## Release asset`: **실제 최종 Public ZIP 파일명**과 정확한 **외부 SHA-256**. 마지막 한 줄 슬로건.

### 영문 Release 최소 템플릿 (값 검증 후 교체)

````markdown
Integrated SPPS planning, optional Auto Plan, sequence risk review, and evidence-aware laboratory recommendations

# SPPS Planner V8.0.0 — GitHub Public Source Release

SPPS Planner V8.0.0 extends the V7 workflow with [verified changes].
The editable Tkinter workflow and established chemistry engine are retained.

## Highlights
### Optional Auto Plan
[Describe actual review-and-confirm behavior; do not claim automatic optimization.]
### Sequence Risk and Recommendations
[Explain rule-based results, provenance, and operator review.]
### UI / UX and Project Data Integrity
[Describe changes actually implemented.]

## Workflow
```text
Project Manager → Sequence + setup → Generate OR Auto Plan review
  → Plan / Materials / Checklist / Total Materials / Cleavage / Workup
  → Risk Map / Recommendations & Lab History / Export
```

## Verification
| Check | Result |
| --- | --- |
| Public regression | [actual passed / skipped / failed] |
| Python compilation | [actual result] |
| Windows native GUI / installer | [actual result, or Not verified] |

## Scientific Scope
[Planning and evidence support, not guaranteed synthesis results or validated SOPs.]

## Requirements
[Real environment and dependencies.]

## Source
https://github.com/SanghunWoo-23/SPPS-PLANNER

## Release asset
[EXACT_PUBLIC_ZIP_FILENAME.zip]
SHA-256: [HASH_CALCULATED_AFTER_FINAL_ZIP]

**SPPS Planner V8.0.0 — [short accurate tagline].**
````

위 템플릿의 중첩 코드 블록은 인수인계서 내 **서식 예시**이며, 실제 Release TXT를 작성할 때는 바깥쪽 Markdown fence 없이 각각의 제목·코드 블록을 출력한다.

### Release 제작 순서와 해시 관리

1. 먼저 README·매뉴얼·인수인계서·코드·테스트·내부 Release Notes를 수정한다.
2. `VERSION` / CFF / Installer / EXE version resource / 실제 UI 이름을 교차 검증한다.
3. Public와 Private을 독립적으로 배포용 ZIP으로 만든다. ZIP 안에는 **별도 배포용 ZIP 자신의 해시를 넣지 않는다**.
4. 최종 ZIP이 완전히 생성된 다음 `sha256sum <Public ZIP>` (Windows PowerShell: `(Get-FileHash '<ZIP>' -Algorithm SHA256).Hash`)으로 체크섬을 계산한다.
5. 실제 파일명과 계산한 Public SHA-256만 **외부 GitHub Release TXT** 및 `SHA256SUMS.txt`에 적는다. Private 해시는 내부 체크섬에만 기재해도 된다.
6. ZIP을 1바이트라도 다시 만들면 **기존 해시 무효**. Release TXT와 체크섬도 재작성한다.
7. GitHub에 올리는 건 **Public ZIP + Public Release 내용**. Private ZIP은 절대 업로드 금지.

### 최종 검수 문구 체크

- `[ ]` V8.0.0 정확히 표기했는가?
- `[ ]` 기능·버튼·파일명은 실제 소스에서 확인했는가? Auto Plan 위치/색상 및 실험 버튼 순서가 README·매뉴얼·Release TXT와 일치하는가?
- `[ ]` 이전 버전 회귀시험 숫자를 새 기능의 테스트 통과로 재활용하지 않았는가?
- `[ ]` Windows Native 검증이 없다면 Not verified로 적었는가?
- `[ ]` Public 실험 시드·비공개 데이터가 없는가?
- `[ ]` Release asset과 외부 SHA256SUMS의 파일명·해시가 완전히 같은가?
- `[ ]` README의 링크·라이선스·의존성·버전이 실제 ZIP과 같은가?
- `[ ]` 다운받을 ZIP과 TXT가 실제 생성됐고 압축파일 검사가 성공했는가?


### UI 변경 시 README / Release 작성 원칙 (2026-10-28 업데이트)

- **README 영어/한국어:** 사용자가 실제 누르는 버튼 순서와 화면 위치를 설명한다. 본 릴리스의 Project Manager 순서는 `Generate → Apply Change → Auto Plan (Optional) → Recommendations & Lab History → Sequence Risk Map → Save Session Now`; Auto Plan은 파란색이다. Recommendations의 기록 순서는 `Preflight → Start Experiment → Add Result → Add Issue → Final Result → Finish → Repeat Run`; 후속 관리 버튼은 `Refresh → Data Store → Backup DB`이다.
- **Release TXT:** UI / UX improvements 항목에 이전 버전 대비 **어떤 버튼이 어디로 이동했고 기능은 보존되는지**를 간단히 쓴다. 시퀀스 계산/실험 근거/화학 조건이 바뀌지 않았다면 그렇게 명시한다.
- **개발 인수인계서:** 변경된 위젯 변수·파일·`pack()` 방향, 테스트 및 Windows 미검증 범위를 기술한다. 단순 버튼 재배치로 실제 실험 데이터가 새로 생성되거나 검증된 것처럼 기술하지 않는다.
- 최종 파일이 바뀌면 **GitHub Release의 ZIP 파일명과 SHA-256을 마지막으로 다시 계산**하고, ZIP 내부에는 자기 ZIP의 SHA를 고정하지 않는다.

## 8. 단일 BAT 및 꼭 남겨야 할 파일

삭제하면 안 되는 최소 파일은 다음과 같다.

- `INSTALL_BUILD_TOOLS_AND_BUILD.bat`: **유일한 Windows build entry point**. 기존 `BUILD_EXE_ONLY.bat`/`BUILD_INSTALLER.bat`을 무심코 복구하거나 단순 삭제·분리하면 계약 테스트가 어긋난다.
- `requirements.txt`, `requirements-dev.txt`, `apps/spps_planner_app/requirements.txt`: 서로 다른 사용처의 의존성 정의.
- `VERSION`, `VERSION.txt`, `installer/version_info.txt`, `SPPS_Planner.spec`, `installer/SPPS_Planner_Setup.iss`: 버전·빌드 자원.
- `CITATION.cff`, `LICENSE`, `README.md`, `README_KO.md`, `RELEASE_NOTES_V8.0.0.txt`, 매뉴얼, 필수 Python/CSV 및 테스트 코드.
- `SOURCE_MANIFEST.sha256`: 현재 소스 파일을 검증하는 내부 무결성 목록. 문서를 1개 추가해도 다시 생성해야 하며 **자기 자신은 목록에서 제외**.

단일 BAT은 Python/winget/Inno Setup 확인·의존성 설치 시도 → source contract → PyInstaller → EXE self-test → Inno Setup → 아티팩트 검증을 수행하도록 설계되어 있다. **완성된 설치 프로그램이 ZIP에 들어 있다는 뜻이 아니다.** BAT을 Windows에서 실제 실행하기 전 성공을 보장하거나 설치 성공으로 표현 금지.

## 9. 공개·비공개 분기별 인수인계

**Public:** 공개 자료·규칙과 코드 및 테스트만 배포. `apps/spps_planner_app/data/experimental_seed/` 안의 비공개 시드는 Public ZIP에 포함하지 않음. 기본 경로 분리와 사용자가 명시적으로 import하는 기능을 혼동하지 않음. GitHub에는 이 분기만 올라간다.

**Private:** 내부 전용 자료 6개(`Cleavage_Report_seed.xlsx` 및 여러 CSV 시드)와 내부 정책 파일이 추가되어 있다. Private의 실험 근거·시드·자료를 Public 기본값 또는 테스트 샘플로 붙여 넣지 말 것. 공개 배포 전 파일 전체 경로와 내용의 누출을 재검사.

공통 코드를 수정할 때는 Public에서 먼저 회귀시험을 진행할 수 있으나 Private은 Public을 무작정 덮어쓰지 말고 동일 패치를 독립 적용·비교한다. Private 분석/기록 원자료는 절대 공개 Release 설명에 사용하지 않는다.

## 10. 다음 작업 우선순위 / 미검증 항목

1. Windows 11 x64 실제 EXE/Installer build, 시작, 저장, 열기, 재실행, 업그레이드/제거.
2. 화면별 스크롤바 및 마우스 휠, 작은 창/저해상도 환경, Apply Change 옆 파란색 Auto Plan 버튼과 Recommendations & Lab History의 실험 진행순서 실사용.
3. 실제 다양한 서열과 레진에서 Plan → Materials → Checklist → Cleavage/Workup의 수량 일치 및 과학적 근거 표시 검증.
4. 빈 프로젝트/구버전 프로젝트/손상 JSON/파일 동시 저장/OneDrive 충돌 실환경 확인.
5. 상기 검증 결과가 달라지면 README/Release 및 Release manifest를 함께 갱신.

**핵심 요약:** 기존 V8 계산·UI를 보존하고, Public만 공개하며, README는 사용자 안내서·Release TXT는 변화와 검증·인수인계서는 개발/배포 절차로 역할을 분리한다. 소스 테스트 통과와 Windows 설치 검증, 규칙 기반 계산과 실험적 검증을 혼동하지 않는다.
