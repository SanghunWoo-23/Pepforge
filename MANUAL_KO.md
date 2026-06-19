# Pepforge v2.0.0 사용 매뉴얼

## 1. 개요

Pepforge v2.0.0은 peptide 연구 흐름을 하나의 desktop workbench로 묶은 public research package다.

포함 흐름:

1. sequence hotspot 분석,
2. SPPS-aware peptide design,
3. production-style SPPS planning,
4. modified peptide PyMOL 구조 생성,
5. docking/MD/external validation bridge reporting.

이 도구는 계획, screening, export, report를 위한 것이다. 생물학적 효능, 최종 결합력, 최종 합성 QC, 논문급 MD 검증을 단독으로 증명하는 도구가 아니다.

## 2. 실행

통합 실행:

```bash
python main_launcher.py
```

Windows source 실행:

```text
RUN_PEPFORGE_SOURCE.bat
RUN_SPPS_PLANNER_SOURCE.bat
```

CLI 확인:

```bash
python pepforge_cli.py version
python pepforge_cli.py validate-runtime --output-dir outputs/runtime_validation
```

## 3. Sequence notation

예시:

```text
EEMQRR-NH2
Ac-EEMQRR-NH2
FITC-Ahx-EEMQRR-NH2
Biotin-Ahx-EEMQRR-NH2
Pal-dG-dH-dK-NH2
Caf-EEMQRR-NH2
Gal-EEMQRR-NH2
Caffeic acid-EEMQRR-NH2
```

해석 기준:

- 일반 알파벳 residue는 표준 amino acid.
- `dX`는 지원되는 D-form residue.
- `NH2`는 C-terminal amide.
- linker는 amino-acid-like coupling unit.
- label/cap/tag/terminal chemical은 chemical modifier.

## 4. SPPS Planner

### 4.1 목적

SPPS Planner는 합성 plan, material usage, project table, checklist, log, transfer/export table을 만든다.

### 4.2 마지막 wash 로직

v2.0.0에서는 마지막 deprotection 또는 terminal chemical/label/tag/cap coupling 이후 다음 흐름을 사용한다.

```text
final Fmoc removal
DMF wash x6
terminal reaction
final wash DMF x3
final wash DCM x3
```

마지막 반응 뒤에 `post-coupling wash DMF x2`가 중복으로 붙지 않는다.

### 4.3 linker와 label 구분

- Linker: 아미노산처럼 coupling unit으로 취급. 예: `Ahx`, `AEEA`, `PEG`.
- Label/chemical/tag/cap: terminal 또는 side-chain chemical modifier로 취급. 예: `Ac`, `Pal`, `Caf`, `Gal`, `FITC`, `FAM`, `Biotin`, `DOTA`, `His6`, `FLAG`, `HA`.

### 4.4 MW 기준

`Reagent MW`와 `Product MW contribution`은 다르다.

- `Ac`: acetic anhydride 사용량 MW와 acetyl contribution 분리.
- `Caf`: caffeic acid 180.16 g/mol과 caffeoyl residue contribution 분리.
- generic dye/tag는 vendor form이 불명확하면 manual-required.

새 물질 추가는 다음 파일을 기준으로 한다.

```text
apps/spps_planner_app/data/new_compound_template.csv
```

## 5. Docking Workbench

### 5.1 목적

Docking Workbench는 target/peptide 정보, target summary, contact screening, affinity-style table, MD-style table, external validation export/import를 정리한다.

### 5.2 화면 공간 문제 해결

Input이 커서 Target summary가 안 보이면:

```text
Collapse Input / Expand Input
```

전체 데이터 확인:

```text
Input data full
Results data full
MD data full
```

### 5.3 PRODIGY/GROMACS/MD-style data

이 표들은 외부 검증 결과와 비교하기 쉽게 정리한 screening/reporting table이다. 실제 PRODIGY/GROMACS/OpenMM/AMBER 실행 결과라고 주장하면 안 된다. 외부 실행 결과를 import한 경우에는 파일/조건/메타데이터를 같이 보존해야 한다.

## 6. PyMOL Structure Builder

권장 순서:

```text
Analyze
Build SDF/PDB/PML
Open Output
token_map.csv 확인
필요 시 Bridge export
```

Bridge는 외부 docking/MD 실행 버튼이 아니라 hand-off package 생성 기능이다. Vina, Gnina, Smina, PRODIGY, GROMACS, OpenMM, AMBER는 별도로 실행해야 한다.

## 7. GitHub 업그레이드 절차

1. 기존 저장소 내용을 백업.
2. 이 v2.0.0 패키지로 파일 교체 또는 병합.
3. local output, project, build, exe, cache는 commit하지 않음.
4. 버전 확인:

```bash
python pepforge_cli.py version
```

5. commit/tag:

```bash
git add .
git commit -m "Release Pepforge v2.0.0"
git tag v2.0.0
git push origin main --tags
```
