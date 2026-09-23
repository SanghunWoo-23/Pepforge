# SPPS Planner V3 데이터 시스템

## 계층

```text
Project JSON
└─ Work Item (peptide / sequence / resin / loading / LOT)
   ├─ Run 001
   │  ├─ Plan / Materials / Total / Checklist / Cleavage snapshot
   │  ├─ append-only synthesis execution events
   │  ├─ ML outcome review revisions
   │  ├─ HPLC records and linked data/method files
   │  └─ append-only data change history
   └─ Run 002 ...
```

V2/V3 초기 저장 파일에 `runs`가 없으면 현재 Work Item 데이터를
`Run 001`로 자동 승격한다. 현재 활성 Run은 기존 `Apply Change`, 실행
원장, ML 경로와 동기화되므로 기존 계산 기능을 우회하지 않는다.

## JSON 안정성

- 같은 폴더의 `*.json.tmp`에 먼저 기록한 뒤 원본을 원자적으로 교체한다.
- 기존 정상 파일은 `*.json.bak`에 마지막 정상본으로 보존한다.
- 원본 JSON이 손상되면 `.bak`를 읽어 복구한다.
- 불러온 Project의 SHA-256과 저장 직전 파일 SHA-256이 다르면 저장을
  거부한다. 사용자는 새 변경을 확인한 뒤 다시 Load하거나 Save As한다.
- 최근 열고 저장한 Project는 최대 12개까지 별도 registry에 기록한다.

## XLSX 시트

- `Project`, `Work_Items`, `Runs`
- `Plan`, `Materials`, `Totals`, `Checklist`, `Cleavage`
- `Execution_Events`
- `ML_Current`, `ML_Revisions`
- `HPLC`, `Change_History`
- `Risk_Assessments`, `Risk_Findings`, `Risk_Acknowledgements`
- `Column_Map`

각 행에는 필요한 경우 `work_item_id`와 `run_id`가 포함된다. Excel에서
필터와 정렬을 바로 사용할 수 있도록 모든 시트에 header filter와 고정
header row를 설정한다.

`Column_Map`의 `sheet`, `source_column`, `canonical_column` 값을 바꾸면
외부 XLSX 컬럼명을 SPPS Planner 컬럼으로 변환해 가져올 수 있다. 코드
호출 시 전달하는 mapping은 Workbook mapping보다 우선한다.

## HPLC record

주요 필드는 sample, acquisition time, instrument, column, method, mobile
phase, gradient, flow, wavelength, injection volume, runtime, retention time,
area, purity, analyst, note이다. data file과 method file은 파일을 복제하지
않고 다음 무결성 metadata와 함께 연결한다.

- 절대 경로
- 현재 존재 여부
- byte 크기
- 수정 시각
- SHA-256

HPLC record의 생성·수정·삭제는 사유가 필수이며, 삭제는 물리적으로
지우지 않고 deleted 상태와 전후 변경 이력을 남긴다.
