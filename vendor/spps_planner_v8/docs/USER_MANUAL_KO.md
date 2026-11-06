# SPPS Planner V8.0.0 사용자 매뉴얼

## 1. 프로그램의 역할

SPPS Planner는 펩타이드 서열과 resin·scale·loading·chemistry 조건으로
편집 가능한 합성 Plan을 만들고 Materials, Total, Checklist, Cleavage,
실행 이력, HPLC, 실제 결과 및 ML 검토를 하나의 Project에 연결하는
Windows 데스크톱 프로그램이다. 실험 승인, SOP/SDS, 장비 적합성 및
작업자의 최종 판단을 대신하지 않는다.


## V8.0.0 — 선택형 Auto Plan 및 분석 결과

Project Manager에서 **Auto Plan (Optional)**을 누르면 현재 Sequence, Scale,
Resin, Loading, Copies 및 Coupling 설정의 미리보기가 열립니다. 확인 후
**Generate Full Plan**을 누르면 기존 계산 엔진을 통해 Plan과 재료·체크리스트·Cleavage/Workup
계획을 생성합니다. 창만 여는 것은 설정을 변경하지 않습니다.

Project Manager 버튼 순서는 **Generate → Apply Change → Auto Plan (Optional) → Recommendations & Lab History → Sequence Risk Map → Save Session Now**입니다. Auto Plan은 Apply Change 바로 옆의 파란색 버튼이며 필수 단계가 아닙니다.

**Recommendations & Lab History** 상단에서는 **Preflight → Start Experiment → Add Result / Add Issue → Final Result → Finish → Repeat Run** 순으로 이용합니다. 오른쪽의 **Refresh · Data Store · Backup DB**는 관리 기능입니다. `Add Issue`는 이슈가 발생한 경우에만 누르며, Start Experiment 이후 기록은 시작 시 고정된 Run 조건에 연결됩니다.

Sequence Risk Map은 규칙 기반 경고이며 실험 실패 확률이 아닙니다. Loading/Cleavage
Recommendation의 화학 기본값과 실제 실험 근거를 구분해서 검토해야 합니다.
Cocktail과 Cleavage 시간을 서열만으로 검증 완료된 조건이라고 취급하지 마세요.


## 새 Peptide 추가 — 가장 쉬운 사용법

처음 사용하는 경우에는 **Project Manager**에서 시작합니다.

1. **Add**를 누릅니다.
2. Step 1에서 Sequence, Scale, Copies, Resin, Loading 등 기본 합성 정보를 입력합니다. 이 값들은 기본 합성 정보이므로 숨기지 않습니다.
3. Step 2에서 coupling reagent / activator, additive / catalyst, base, solvent를 선택합니다. 반복해서 쓰는 정확한 bottle 조합은 **My recipes**에 저장·불러오기·이름 변경·삭제할 수 있고, 최근 사용 recipe는 바로 다시 선택할 수 있습니다. **Find bottle**은 병 이름뿐 아니라 등록된 역할/분류/상태/메모도 함께 검색합니다.
4. Step 3에서 Project/Peptide, Sequence, Scale/Copies, Resin/Loading, exact recipe를 확인한 뒤 **Add peptide**를 누릅니다. Edit에서는 무엇이 바뀌었는지와 재계산 필요 여부도 함께 표시됩니다.
5. 기존 peptide는 선택 후 **Edit setup…**을 눌러 같은 exact-bottle 창에서 수정할 수 있으며 Batch Solution prep defaults는 바뀌지 않습니다.
6. Project Manager의 기존 **Generate / Apply Change / Recommendations & Lab History** 흐름을 그대로 사용합니다.

`NMM`은 coupling **base**, `NMP`는 **solvent**입니다. Add 창에서 선택한 project-specific coupling recipe는 해당 peptide에 저장되며 Batch Manager의 Solution prep defaults를 바꾸지 않습니다.

## 2. 화면 구성

- 상단 메뉴: File, Edit, Project, Synthesis, View, Data / ML, Help
- 기존 Classic 작업공간: resin, loading, 아미노산/시약/용매 조건과 Plan
- Work List: 여러 펩타이드 Work Item 관리
- Work Item 창: Plan/Materials/Total/Checklist/Cleavage, Run / Corrections,
  Outcome / ML, Risk Review, Data / HPLC
- View → Display Density: Compact, Standard, Comfortable

1024×680 이상의 화면에서는 창이 화면 안으로 자동 맞춰진다. 큰 화면에서도
1600×900을 기준으로 중앙 배치해 불필요한 빈 공간을 줄인다.

## 3. 기본 합성 계획

1. Work Item을 선택하거나 `Ctrl+N`으로 새 항목을 만든다.
2. Project, Peptide, Sequence, Scale, Copies, Resin, Loading, Chemistry를 입력한다.
3. 필요한 경우 Show setup에서 기존 resin·아미노산·reagent·base·solvent
   컨트롤을 조정한다.
4. `Generate` 또는 `Ctrl+G`로 Plan, Materials, Total, Checklist를 한 번에 만든다.
5. Plan 셀을 더블클릭해 eq, reagent, solvent, Repeat 등을 직접 편집한다.
6. `Apply Change` 또는 `Ctrl+Enter`로 현재 보이는 Plan을 기준으로 Materials,
   Total, Checklist, Cleavage, Export를 다시 계산한다.

Generate는 입력 서열에서 Plan, Materials, Total, Checklist를 한 번에 새로
만들며 기존 Cleavage 결과는 변경하지 않는다. Apply Change는 편집 중인
Plan을 서열에서 다시 생성하지 않고 기존처럼 Cleavage까지 반영한다.
Chemistry preset은 조건만 바꾸며 Plan을 자동 생성하지 않는다.

## 4. Resin과 서열 입력 주의사항

- `Rink Amide AM/MBHA/ChemMatrix/Tentagel`, `Sieber Amide`, `PAL resin` 등
  amide 계열과 `2-CTC`, `CTC(합성기)`, Wang, HMPB, Manual을 구분한다.
- `2-CTC` 직접 loading은 loading AA와 DIEA 조건을 보존한다.
- `CTC(합성기)`는 preloaded 운용으로 전체 입력 서열을 합성 단계에 사용한다.
- N/C 말단, D-form, 보호기, 비천연 아미노산, linker, label, branch 표기는
  Sequence parser가 해석한다. parser warning은 반드시 검토한다.
- 빈 Sequence에는 예시 펩타이드나 가짜 Plan이 자동 삽입되지 않는다.

## 5. Work List와 독립 Work Item 창

Work List 항목을 더블클릭하거나 Enter를 누르면 독립 창이 열린다. 상단의
Project/Resin/Chemistry 값은 기존 Classic 변수와 연결되어 있다.

- Selected Plan: 직접 편집 가능한 source of truth
- Selected Materials/Total Materials: 단계별·합계 재료량
- Checklist: 작업 진행용 합성 순서
- Cleavage: 선택된 cocktail과 계산량
- `Ctrl+S`: Work Item 저장
- `F5`: 현재 창 새로 고침
- `Esc`: 저장 후 창 닫기

## 6. 실시간 실행과 보정

`Run / Corrections`에서 단계 상태, 실제 투입량과 단위, 현장 수정 및
doubling을 기록한다. Plan 수정·doubling에는 사유가 필요하다. 모든 사건은
UTC timestamp, event ID, Work Item ID, 변경 전후 값, 작업자 메모를 가진
append-only 원장에 들어간다.

Revert Last는 기존 사건을 삭제하지 않고 반대 변경을 새 사건으로 기록한다.
변경 후 기존 Apply Change가 실행되어 연결 결과가 함께 갱신된다.

## 7. 실제 결과와 ML

`Outcome / ML`에서 actual yield, crude purity, failure flag, doubling required를
검토 저장한다. 값 변경은 revision으로 남는다. 잘못된 HPLC integration이나
중단 run은 exclusion reason을 입력해 학습에서 제외한다.

- target별 included/reviewed 실제 값 최소 5개 필요
- failure/doubling 분류는 실제 class 최소 2개 필요
- 결과 컬럼은 feature에서 제거해 target leakage 방지
- dataset snapshot은 fingerprint를 가진 불변 version으로 저장
- 모델 metadata에 target, task, 지표, 행 수, dataset version/fingerprint 저장

조건이 부족하면 모델 생성과 예측을 거부한다.

## 8. 합성 위험 검토

`Risk Review`는 Aspartimide 후보, hydrophobic aggregation, difficult coupling,
Cys 보호/산화, Met·Trp 산화, 초기 Pro 문맥, Plan repeat 및 Run failed/hold
기록을 검토한다. 각 finding은 위치, 근거, 영향, 검토 권고를 표시한다.

Rule score는 규칙 가중치 기반 우선순위이며 실패 확률이 아니다. 실제 검토
데이터로 학습된 유효한 failure/doubling 모델이 있을 때만 classifier 확률과
dataset fingerprint를 표시한다. 위험 검토는 Plan을 자동 변경하지 않는다.

Save Assessment Version은 내용이 바뀐 경우에만 새 revision을 만들고,
Acknowledge Selected는 사유를 포함한 별도 감사 이력을 남긴다.

## 9. Run과 HPLC 데이터

`Data / HPLC`에서 한 Work Item에 여러 Run을 만들고 활성 Run을 바꿀 수 있다.
각 Run은 Plan snapshot, 실행 원장, ML review, Risk review, HPLC와 변경 이력을
독립적으로 보존한다.

HPLC record에는 sample, acquisition time, instrument, column, method, mobile
phase, gradient, flow, wavelength, injection volume, runtime, retention time,
area/purity, analyst, note를 저장한다. data/method 파일은 경로·존재 여부·크기·
수정시각·SHA-256 metadata로 연결된다. 삭제는 soft delete와 감사 이력으로 남는다.

## 10. 저장, 복구 및 Excel 왕복

- `Ctrl+S`: 현재 Project 저장
- `Ctrl+Shift+S`: Save As
- `Ctrl+O`: Project 불러오기
- 자동저장과 원자적 JSON 저장
- 마지막 정상본 `.bak` 복구
- 외부 수정 SHA-256 충돌 시 덮어쓰기 거부
- 최근 Project 최대 12개

Data Workbook은 Project, Work Items, Runs, Plan, Execution Events, ML,
HPLC, Materials, Totals, Checklist, Cleavage, Change History, Risk review와
Column Map 시트를 왕복한다. 외부 장비 컬럼은 `Column_Map` 또는 import
mapping으로 변환한다.

## 11. 키보드 단축키

| 단축키 | 기능 |
| --- | --- |
| Ctrl+S / Ctrl+Shift+S | Save / Save As |
| Ctrl+O | Load Project |
| Ctrl+N / Ctrl+D | Work Item 추가 / 복제 |
| Ctrl+G / Ctrl+Enter | Generate / Apply Change |
| Ctrl+E | 현재 작업 Export |
| Ctrl+- / Ctrl+0 / Ctrl+= | Compact / Standard / Comfortable |
| Work Item F5 / Esc | 새로 고침 / 저장 후 닫기 |

## 12. Windows 설치와 문제 해결

설치형 EXE는 Windows 환경에서 직접 빌드하고 실행 검증해야 한다. 소스 실행은
`WINDOWS_BUILD_KO.md`를 따른다. 실행 실패 시 사용자 data 폴더의
`spps_planner_runtime_error.log`를 확인한다. 저장 충돌은 원본을 확인한 뒤
Reload 또는 Save As로 해결한다. 손상 파일은 `.bak` 복구 결과를 확인하고
원본과 병합이 필요하면 별도 파일로 보존한다.

실험에 사용하기 전에는 Sequence, resin/loading, scale 단위, Repeat,
Materials/Total, Checklist, cleavage 조성, 위험 finding과 HPLC 연결을 작업자가
최종 확인해야 한다.

## V5 Empirical Cleavage Fallback

When a complete exact-sequence historical cleavage condition is unavailable, V5 can show an explicit **EMPIRICAL ESTIMATE** rather than leaving the operator with a blank condition.

Priority:
1. Operator-approved exact sequence anchor when a local/private anchor exists.
2. Complete exact sequence historical condition / consensus.
3. Bounded similar-sequence historical adjustment.
4. Public-safe monotonic sequence-length baseline.
5. TFA / water / TIS chemistry fallback.

Default length baseline is intentionally conservative and is not presented as a universal chemical law. Short general peptides (<=5mer, without Cys/Met/Trp/Tyr) use <=20 eq and TFA/water 95:5 as the fallback. Longer or sensitive sequences use TFA/TIS/water 95:2.5:2.5 unless exact history overrides it. Similar historical sequences may adjust the length baseline only within a bounded range; distant chain lengths and Cys/non-Cys classes are not mixed.

The recommendation view shows the baseline eq, similar-history adjustment, estimated eq range, cocktail basis, and current-scale component volumes. Estimated values require operator confirmation before Apply. Observed exact history always remains higher priority.


## V6.0.0 실험 기록 및 근거 축적 흐름

- Planner가 이미 알고 있는 합성 조건은 사용자가 다시 입력하지 않습니다.
- Loading 화면의 `Measured Loading`에 실제 측정값만 입력하면 현재 Work Item/Run, resin, C-terminal AA, AA eq, base eq, time이 자동으로 함께 기록됩니다.
- `Add Result`는 Loading 또는 Cleavage/Final의 실제 측정 결과를 저장합니다. 계획만 작성한 값은 Verified ML 결과로 취급하지 않습니다.
- `Add Issue`는 자연어 특이사항을 저장하며, 당시 Planner 조건과 기존 active Run ID를 자동으로 연결합니다.
- Loading 추천은 동일 resin + 동일 C-terminal AA의 Verified 결과를 우선하며 관측 범위 밖 extrapolation을 하지 않습니다.
- 활성 모델 이후 새 Verified Loading 결과가 5개 이상 쌓이면 모델 rebuild 알림을 표시하지만 자동 재학습은 하지 않습니다.
- 새 모델은 기존 active model과 validation 성능을 비교하고, 더 나쁜 후보가 자동으로 기존 모델을 덮어쓰지 않습니다.
- Recommendations/Work Item/Result/Issue 창은 화면 크기 범위에서 내용이 보이도록 자동으로 크게 열립니다.
