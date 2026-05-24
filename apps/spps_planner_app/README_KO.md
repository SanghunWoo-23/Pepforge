# SPPS Python Planner 사용 안내

이 버전은 기존 Excel planner의 계산 로직을 Python으로 옮긴 유지보수형 버전입니다. Excel은 결과 확인/출력용으로 쓰고, 계산과 DB 관리는 Python이 담당합니다.

## 핵심 기능

- `Ac-EEMQRR-NH2` 같은 sequence 자동 parsing
- 보호기 표기 `(OtBu)`, `(Trt)`, `(Pbf)` 제거 후 core sequence 계산
- Amide / CTC-Trityl resin별 loading logic 분기
- Deprotection = 20% piperidine + 80% DMF
- wash-by-wash synthesis form 생성
- raw material use table 생성
- `CSV` / `XLSX` export
- compound DB를 `data/compounds.csv`로 계속 추가/수정 가능
- 실제 run 데이터를 `data/actual_runs.csv`에 계속 누적 가능
- ML-ready 구조 포함

## 실행 방법

### 1) 설치

```bash
python -m pip install -r requirements.txt
```

### 2) 앱 실행

```bash
streamlit run app.py
```

Windows에서는 `run_app.bat`을 더블클릭해도 됩니다.

## CLI 사용 예시

```bash
python cli.py --seq Ac-EEMQRR-NH2 --resin Amide --mmol 400 --outdir outputs/std_400mmol
```

STD 검산값:

```text
DMF = 304,800 mL
Piperidine = 11,200 mL
DCM = 12,000 mL
Product MW = 889.02 g/mol
```

## 데이터 추가 방식

### compound / AA / label / linker 추가

`data/compounds.csv`에 행을 추가합니다.

중요 컬럼:

- `Token`
- `Class`
- `Reagent/protected form`
- `Reagent MW (g/mol)`
- `Product MW contribution (g/mol)`
- `Counts as coupling unit?`
- `Chemistry profile`
- `Applied reagent logic`

앱의 `DB Editor` 탭에서도 직접 수정 후 저장할 수 있습니다.

### 실제 run 데이터 추가

`data/actual_runs.csv`에 기록하거나, 앱의 `Data Log` 탭에서 CSV/XLSX를 업로드합니다.

추천 컬럼:

- `run_id`
- `date`
- `sequence`
- `resin`
- `scale_mmol`
- `planned_dmf_mL`
- `actual_dmf_mL`
- `planned_piperidine_mL`
- `actual_piperidine_mL`
- `planned_dcm_mL`
- `actual_dcm_mL`
- `yield_percent`
- `purity_percent`
- `failed`
- `issue_note`

## ML 사용 시점

지금부터 데이터 누적과 이상치 탐지는 가능합니다. 실제 ML 예측은 `yield_percent`, `purity_percent`, `actual_dmf_mL`, `failed` 같은 target 컬럼이 누적되면 바로 사용할 수 있습니다.

권장 순서:

1. Python 계산 엔진으로 Excel 계산값 검산
2. 실제 run log 누적
3. planned vs actual 사용량 비교
4. 이상치 탐지
5. yield / purity / failure 예측 ML 적용

## 출력 파일

앱 또는 CLI를 실행하면 output 폴더에 다음 파일이 생성됩니다.

- `summary.csv`
- `step_matrix.csv`
- `synthesis_form_wash_by_wash.csv`
- `raw_material_use.csv`
- `spps_plan.xlsx`

CSV는 Excel에서 바로 열 수 있습니다.
