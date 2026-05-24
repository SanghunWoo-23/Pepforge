# Peptide Design Engine — Data/ML 유지보수 강화판 안내

이 버전은 EXE GUI에서 `Data / ML` 탭을 강화한 버전입니다. 기존 Colab/Python 기능과 데이터는 유지하고, AF3/PRODIGY/실험 데이터를 계속 투입해 surrogate ML을 재학습할 수 있도록 구성했습니다.

## 1. GUI에서 추가된 기능

`4. Data / ML` 탭에서 다음을 할 수 있습니다.

- `Import prepared CSVs`: 이미 정리된 AF3/PRODIGY/실험 CSV를 `training_data.csv`에 누적
- `Parse AF3 folder → Import`: AF3 output 폴더를 선택하면 score JSON/CSV를 찾아 표준 CSV로 변환 후 누적
- `Parse PRODIGY txt/csv/folder → Import`: PRODIGY txt/csv/log 파일 또는 폴더를 표준 CSV로 변환 후 누적
- `training_data.csv preview`: 현재 누적된 학습 DB를 GUI에서 미리보기
- `ML label column`: 학습할 label 선택
- `Train model`: 누적 DB로 surrogate model 재학습
- `Model status`: 선택된 model JSON의 label, 학습 row 수, feature 수 확인
- `Candidate mapping CSV`: AF3/PRODIGY 파일명과 후보 ID/서열이 다를 때 자동 매칭

## 2. 권장 데이터 흐름

```text
Peptide Engine 후보 생성
→ 후보 CSV 보관
→ AF3 / PRODIGY / 실험 평가
→ Data / ML 탭에서 결과 import 또는 자동 parse
→ training_data.csv 누적
→ Train model
→ 다음 Run에서 trained model reranking 사용
```

## 3. 파일명 매칭 규칙

파서는 기본적으로 파일명/폴더명에서 `PDE_0001` 같은 candidate ID를 추론합니다.

예:

```text
PDE_0001_summary_confidences.json → candidate_id = PDE_0001
PDE_0001_prodigy.txt              → candidate_id = PDE_0001
```

파일명이 후보 ID와 다르면 `data/templates/candidate_mapping_template.csv`를 복사해서 사용하세요.

필수/권장 컬럼:

```csv
candidate_id,sequence,clean_sequence,target_id,source_name,file,folder,notes
```

## 4. AF3 파서

지원 형태:

- AF3 output 폴더
- JSON 파일명에 `score`, `summary`, `ranking`, `confidence`, `result`가 포함된 파일
- CSV score 파일

인식하는 대표 key:

```text
iptm, ipTM, interface_ptm
ptm, pTM
ranking_score, ranking_confidence
confidence, mean_plddt, plddt
```

출력 표준 컬럼:

```text
af3_confidence
af3_iptm
af3_ptm
af3_ranking_score
```

## 5. PRODIGY 파서

지원 형태:

- `.txt`
- `.out`
- `.log`
- `.csv`
- 폴더 전체

인식하는 대표 값:

```text
Predicted binding affinity
delta_g / dg / binding_affinity
Kd / dissociation constant
```

출력 표준 컬럼:

```text
prodigy_delta_g
prodigy_kd
```

## 6. CLI 사용 예시

AF3 폴더 파싱 + training DB 누적:

```bash
cd Python
python peptide_cli.py --parse-af3-folder ../data/sample_external_outputs/af3_output_example --candidate-map ../data/templates/candidate_mapping_template.csv --training-db ../data/training_data.csv --no-run
```

PRODIGY 폴더 파싱 + training DB 누적:

```bash
python peptide_cli.py --parse-prodigy ../data/sample_external_outputs/prodigy_output_example --candidate-map ../data/templates/candidate_mapping_template.csv --training-db ../data/training_data.csv --no-run
```

누적 DB로 ML 학습:

```bash
python peptide_cli.py --train-ml --training-db ../data/training_data.csv --ml-label experimental_binding --models-dir ../models --no-run
```

학습 모델로 후보 재랭킹:

```bash
python peptide_cli.py --preset exploration --target DELIKFVRWA --trained-model ../models/surrogate_model.json --outdir outputs_ml_rerank
```

## 7. 주의

- AF3 자체나 PRODIGY 자체를 EXE에 내장한 것은 아닙니다.
- 이 버전은 외부에서 계산된 AF3/PRODIGY 결과를 import/parse해서 ML에 누적하는 구조입니다.
- 실제 실험 데이터와 학습된 모델은 공개 GitHub에 넣지 않는 것을 권장합니다.
- 공개용 repo에는 template, parser, demo sample만 올리고 `data/training_data.csv`, `models/surrogate_model.json`은 private로 관리하세요.
