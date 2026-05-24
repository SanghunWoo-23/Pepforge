# Peptide Design Engine — Desktop GUI / EXE 준비판 사용 설명서

이 버전은 기존 Colab/Python 엔진, 문서, 예시 결과, 지속학습용 데이터 템플릿을 유지한 상태에서 `Python/desktop_gui.py`를 추가한 Desktop GUI 준비판이다.

## 핵심 방향

- 기존 엔진 파일 `Python/peptide_engine.py`는 유지한다.
- 기존 CLI 파일 `Python/peptide_cli.py`도 유지한다.
- Desktop UI는 `Python/desktop_gui.py`에서 실행한다.
- GUI에서 직접 설정하기 어려운 고급 기능은 `Advanced CONFIG` 탭의 JSON Override에 넣어 기능 유실을 막는다.
- AF3 / PRODIGY / docking / experimental CSV는 `Data / ML` 탭에서 누적 import할 수 있다.
- 누적된 training CSV로 surrogate model을 학습하고, 다음 후보 설계에서 reranking에 사용할 수 있다.

## 바로 실행

Windows에서 Python이 설치되어 있으면 루트 폴더에서 아래 파일을 실행한다.

```bat
run_desktop_gui.bat
```

또는 직접 실행한다.

```bash
python Python/desktop_gui.py
```

## EXE 빌드

Windows에서 루트 폴더 기준으로 실행한다.

```bat
build\build_desktop_gui_exe.bat
```

성공하면 다음 파일이 생성된다.

```text
dist\PeptideDesignEngine_GUI.exe
```

기존 CLI EXE 빌드는 그대로 유지되어 있다.

```bat
build\build_exe.bat
```

## GUI 탭 구성

### 1. Basic / Run

- Target sequences: 쉼표 또는 줄바꿈으로 여러 target 입력
- Preset: custom / fast / paper / exploration / hotspot_only
- Target Mode: SINGLE / MULTI / BRIDGE
- Design Mode: SINGLE_TARGET / MULTI_TARGET_BINDER / BRIDGE_LINKER
- Length Mode: RANDOM / FIX
- Length Count: TOKEN / RESIDUE / EXPANDED
- Output directory: 결과 저장 위치

### 2. Chemistry / Constraints

- D-form residue 사용 여부
- Non-natural residue 사용 여부
- Linker / Tag / Base chemical / Label 사용 여부
- Motif lock
- Locked motifs
- Motif position mode
- Bridge anchor length

Label 기본값은 기존 기능을 유지한다.

```text
BIOTIN, FITC, Cy5
```

Base chemical 기본값도 유지한다.

```text
Pal, Myr, Nic, Caf, Gal, Ac
```

Linker 기본값도 유지한다.

```text
Ahx, PEG4, PEG8, bAla, gAla
```

### 3. Hotspot / Docking

- Auto hotspot
- Hotspot source: SEQUENCE / PDB
- PDB file import
- Hotspot window / top K
- Docking stage / docking engine
- Docking-ready mode
- Pseudo-docking Colab input export

### 4. Data / ML

- AF3 / PRODIGY / docking / 실험 CSV import
- `training_data.csv` 누적 관리
- surrogate ML 학습
- 학습된 `surrogate_model.json`으로 reranking

권장 데이터 운영 방식은 다음과 같다.

```text
공개 repo:
- template CSV
- demo CSV
- GUI / CLI / 엔진 코드

비공개 로컬:
- 실제 AF3 output
- 실제 PRODIGY output
- 실제 실험 결과
- 실제 training_data.csv
- 학습된 models/surrogate_model.json
```

### 5. Advanced CONFIG

UI에 노출되지 않은 모든 고급 기능은 이 탭에서 JSON으로 덮어쓸 수 있다.

예시:

```json
{
  "MAX_LINKERS": 2,
  "TAG_TYPES": ["His6", "FLAG", "HA"],
  "BASE_CHEM_TYPES": ["Pal", "Myr", "Nic", "Caf", "Gal", "Ac"],
  "LABEL_TYPES": ["NONE", "BIOTIN", "FITC", "Cy5"],
  "LINKER_TYPES": ["Ahx", "PEG4", "PEG8", "bAla", "gAla"]
}
```

이 구조 때문에 GUI에 버튼이 없더라도 기존 엔진 CONFIG의 기능을 유지할 수 있다.

## 출력 파일

실행 후 output directory 아래에 날짜별 run 폴더가 생기고, 기존 엔진 출력물이 유지된다.

```text
results_full.csv
results_top.csv
hotspot_peptide_pairs.csv
top_structural_clustering.csv
research_report.md
methods_config_snapshot.json
*.zip
```

Optional ML이나 pseudo-docking export를 켜면 추가 파일이 생성되고, ZIP도 다시 빌드된다.

## 주의

- AF3 자체를 EXE 내부에 넣는 구조가 아니라, AF3 결과를 CSV로 import하는 구조다.
- PRODIGY도 마찬가지로 결과 CSV를 import하는 방식이 안전하다.
- 대형 모델 weight, 실제 실험 데이터, private training DB는 GitHub 공개 repo에 넣지 않는 것을 권장한다.
