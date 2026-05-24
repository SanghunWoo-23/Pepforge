# Peptide Design Engine — EXE 준비 안정화판 + 지속학습 구조

## 목적

이 버전은 기존 Colab/Python 기능과 데이터를 유지하면서, 나중에 Windows `.exe`로 묶기 전에 문제가 될 수 있는 부분을 먼저 정리한 안정화판이다.

핵심 방향은 단순 실행 파일이 아니라 다음 구조다.

```text
Peptide Design Engine.exe
→ 후보 생성
→ AF3 / PRODIGY / docking / experimental CSV import
→ training_data.csv 누적
→ lightweight surrogate ML 재학습
→ 다음 후보 reranking에 반영
```

## 이번 안정화에서 고친 부분

1. `peptide_cli.py`의 preset 덮어쓰기 문제 수정
   - 기존 구조에서는 `--preset fast/paper/exploration/hotspot_only`를 적용한 뒤 바로 기본 CONFIG가 다시 덮어써질 수 있었다.
   - 이제 적용 순서는 `engine default → preset → config file → CLI override`이다.

2. `args.target_mode` 미정의 참조 수정
   - `--target-mode SINGLE/MULTI/BRIDGE` 옵션을 정식 추가했다.
   - `SINGLE → SINGLE_TARGET`, `MULTI → MULTI_TARGET_BINDER`, `BRIDGE → BRIDGE_LINKER`로 매핑된다.

3. optional ML / pseudo-docking 출력 ZIP 누락 방지
   - 기존에는 일부 선택 출력이 ZIP 생성 뒤에 추가될 수 있었다.
   - 이제 후처리 파일 생성 후 출력 ZIP을 다시 빌드한다.

4. 지속학습용 파일 추가
   - `Python/data_manager.py`: AF3/PRODIGY/실험 CSV를 `data/training_data.csv`로 누적.
   - `Python/ml_trainer.py`: 누적 CSV 기반 lightweight ridge surrogate 학습.
   - `data/templates/*.csv`: 입력 템플릿.

5. exe 빌드 스크립트 추가
   - `build/build_exe.bat`
   - `build/build_exe.ps1`

## 유지된 핵심 기능

기존 엔진 데이터와 기능은 삭제하지 않았다.

- GA/NSGA-II 스타일 진화 탐색 구조
- multi-target binder / bridge linker mode
- hotspot extraction 및 hotspot-region output
- motif lock / motif position semantics
- linker / tag / base chemistry / label system
- D-form / non-natural residue handling
- Hyp 포함 non-natural residue list
- Ahx, PEG 계열, bAla/gAla, amino-acid linker library
- terminal topology rule
- length semantics: TOKEN / RESIDUE / EXPANDED
- docking-ready classification
- docking surrogate FASTA export
- full results / top results / validation / report CSV 저장
- Colab용 UI / Engine / Run 분리 파일 유지

## 추천 실행 예시

### 빠른 후보 생성

```bash
cd Python
python peptide_cli.py --preset fast --target DELIKFVRWA --outdir outputs_fast
```

### bridge mode 후보 생성

```bash
python peptide_cli.py --target-mode BRIDGE --target "DELIKFVRWA,YYERWFCAA" --preset paper --outdir outputs_bridge
```

### AF3/PRODIGY/실험 데이터 누적

```bash
python peptide_cli.py --import-training-data ../data/templates/af3_import_template.csv ../data/templates/prodigy_import_template.csv --training-db ../data/training_data.csv --no-run
```

### 누적 데이터로 ML surrogate 학습

```bash
python peptide_cli.py --train-ml --training-db ../data/training_data_template.csv --ml-label experimental_binding --models-dir ../models --no-run
```

### 학습 모델로 생성 후보 reranking

```bash
python peptide_cli.py --preset exploration --target DELIKFVRWA --trained-model ../models/surrogate_model.json --trained-ml-weight 0.25 --outdir outputs_ml_rerank
```

## 중요한 해석 주의

- 이 ML은 후보 우선순위를 보조하는 surrogate model이다.
- AF3, PRODIGY, docking, 실험값을 넣어도 그 자체로 결합 검증이나 활성 검증이 완료되는 것은 아니다.
- 공개 repo에는 example/template만 넣고, 실제 실험 데이터와 private model은 비공개로 관리하는 것을 권장한다.

## EXE 빌드

Windows에서:

```bat
build\build_exe.bat
```

빌드 결과:

```text
Python\dist\PeptideDesignEngine.exe
```

실행 예시:

```bat
Python\dist\PeptideDesignEngine.exe --preset fast --target DELIKFVRWA --outdir outputs_exe
```
