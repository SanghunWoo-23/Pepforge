# Peptide Design Engine — Conda Research Version Guide

이 패키지는 EXE 고정판과 별개로, 연구 확장/개발/ML 재학습을 안정적으로 수행하기 위한 conda 버전입니다.

## 1. 언제 conda 판을 쓰는가?

다음 작업은 EXE보다 conda 환경이 더 적합합니다.

- AF3 / PRODIGY / 실험 데이터 계속 누적
- `training_data.csv` 유지보수
- surrogate ML 재학습
- scikit-learn / xgboost / torch / ESM 등 패키지 추가
- parser/engine/GUI 코드 수정
- GitHub 개발 및 버전 관리
- 논문/포트폴리오용 실험 로그 생성

권장 운영 방식:

```text
연구/개발/데이터 누적: conda
시연/배포/고정판: EXE
```

---

## 2. 포함된 conda 환경 파일

### 기본 연구용

```text
environment.yml
```

포함:

- Python 3.11
- numpy
- pandas
- scipy
- scikit-learn
- matplotlib
- pyyaml
- joblib
- xgboost
- pyinstaller

### 최소 실행용

```text
environment_minimal.yml
```

GUI/CLI 기본 실행 중심입니다. 무거운 ML 패키지를 줄이고 싶을 때 사용합니다.

### GPU / PyTorch 확장용 선택 파일

```text
environment_gpu_optional.yml
```

PyTorch CUDA 환경이 필요한 경우의 예시입니다. GPU/드라이버/CUDA 버전에 따라 조정이 필요합니다.

---

## 3. 가장 쉬운 설치 방법

Windows에서 **Anaconda Prompt**를 열고, 압축 푼 폴더로 이동한 뒤:

```bat
setup_conda_env.bat
```

또는 직접:

```bat
conda env update -f environment.yml --prune
conda activate peptide_engine
python Python\desktop_gui.py
```

---

## 4. GUI 실행

환경 설치 후:

```bat
run_gui_conda.bat
```

또는:

```bat
conda activate peptide_engine
python Python\desktop_gui.py
```

---

## 5. CLI fast test

```bat
run_cli_conda_fast_test.bat
```

직접 실행:

```bat
conda activate peptide_engine
python Python\peptide_cli.py --preset fast --target DELIKFVRWA --outdir outputs\conda_fast_test --no-use-optional-ml
```

---

## 6. AF3 / PRODIGY 샘플 파싱

```bat
parse_af3_prodigy_conda_example.bat
```

직접 실행:

```bat
python Python\peptide_cli.py ^
  --parse-af3-folder data\sample_external_outputs\af3_output_example ^
  --candidate-map data\templates\candidate_mapping_template.csv ^
  --training-db data\training_data.csv ^
  --no-run
```

```bat
python Python\peptide_cli.py ^
  --parse-prodigy data\sample_external_outputs\prodigy_output_example ^
  --candidate-map data\templates\candidate_mapping_template.csv ^
  --training-db data\training_data.csv ^
  --no-run
```

---

## 7. ML 학습 예시

```bat
train_ml_conda_example.bat
```

직접 실행:

```bat
python Python\peptide_cli.py ^
  --train-ml ^
  --training-db data\training_data_template.csv ^
  --ml-label experimental_binding ^
  --models-dir models ^
  --no-run
```

실제 연구에서는 `data\training_data.csv`를 사용하는 것을 권장합니다.

---

## 8. 실제 연구 데이터 관리 권장 구조

공개 GitHub에 포함 가능:

```text
data/templates/
data/sample_external_outputs/
Python/external_parsers.py
Python/data_manager.py
Python/ml_trainer.py
```

비공개 권장:

```text
data/training_data.csv
models/surrogate_model.json
실제 AF3 output
실제 PRODIGY output
실제 실험 결과 CSV
```

`.gitignore`에 이미 output/cache 계열은 제외되어 있으며, 실제 연구 데이터는 추가로 private 관리하는 것을 권장합니다.

---

## 9. Conda 환경이 꼬였을 때

환경을 새로 만들고 싶으면:

```bat
conda deactivate
conda env remove -n peptide_engine
conda env create -f environment.yml
conda activate peptide_engine
```

---

## 10. EXE 빌드는 conda 환경에서 해도 됨

```bat
conda activate peptide_engine
build\build_desktop_gui_exe.bat
```

또는 직접:

```bat
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name PeptideDesignEngine_GUI ^
  --paths Python ^
  --hidden-import peptide_engine ^
  --hidden-import data_manager ^
  --hidden-import ml_trainer ^
  --hidden-import external_parsers ^
  --add-data "data;data" ^
  --add-data "example_results;example_results" ^
  Python\desktop_gui.py
```

---

## 11. AF3/PRODIGY 자체 실행에 대한 주의

이 패키지는 AF3나 PRODIGY 자체를 내장 실행하지 않습니다.  
외부에서 계산된 결과를 파싱/import하여 ML 학습 DB에 누적하는 구조입니다.

즉:

```text
AF3/PRODIGY 계산
→ 결과 파일/폴더 생성
→ GUI 또는 CLI에서 parse/import
→ training_data.csv 누적
→ ML 재학습
→ 다음 후보 reranking
```

이 흐름을 기본으로 합니다.
