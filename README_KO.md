# Pepforge Public Research Release v2.0.0

**Hotspot 분석, peptide design, SPPS planning, modified peptide 구조 생성, docking-oriented screening, external validation bridge, publication evidence reporting을 하나로 묶은 peptide research workbench.**

**현재 기준 버전:** `v2.0.0`  
**작성자:** Sanghun Woo  
**저장소:** `https://github.com/poowsh1407/Pepforge`  
**상태:** 연구용 public package. 실험값 또는 최종 docking/MD 검증을 대체하지 않음.

---

## 1. 목적

Pepforge는 peptide 연구에서 분리되어 있던 sequence 분석, peptide design, SPPS 계획, modified peptide 구조 생성, docking/MD 외부 검증 준비, evidence report 작성을 하나의 흐름으로 연결하기 위해 만든 도구다. v2.0.0은 이전 v4.2.x 패치들을 정리하여 GitHub 업그레이드용 기준 버전으로 재정비한 릴리즈다.

주요 사용 목적은 다음과 같다.

- peptide hotspot 또는 motif 후보 정리
- D-amino acid, non-natural AA, linker, label, cap, terminal amide가 포함된 peptide notation 처리
- SPPS plan, material usage, checklist, transfer sheet 생성
- modified peptide의 SDF/PDB/PML/PyMOL 확인용 파일 생성
- target summary, contact, affinity-style, MD-style screening data 정리
- PRODIGY/Vina/Smina/Gnina/GROMACS/OpenMM/AMBER류 외부 검증으로 넘길 bridge package 생성
- publication/report용 claim-bounded evidence 정리

---

## 2. v2.0.0에서 정리된 핵심

### 2.1 SPPS Planner 안정화

- 마지막 deprotection 또는 terminal chemical/label/tag/cap coupling 이후 불필요한 `post-coupling wash DMF x2`가 붙지 않도록 수정.
- 마지막 반응 이후에는 다음으로 정리됨.

```text
final wash DMF x3
final wash DCM x3
```

- `Ahx`, `AEEA`, `PEG` 같은 linker는 amino-acid-like coupling unit으로 처리.
- `Ac`, `Pal`, `Caf`, `Gal`, `FITC`, `FAM`, `Biotin`, tag/cap류는 chemical modifier로 처리.
- reagent MW와 final peptide product contribution MW를 분리.
- `Ac`는 acetic anhydride 사용량용 MW와 acetyl contribution을 분리.
- `Caf`는 caffeic acid 180.16 g/mol 기준으로 정리.
- vendor form이 모호한 label/tag/linker는 manual-required로 표시하여 틀린 자동 계산을 피함.

### 2.2 Compound DB 정리

DB 위치:

```text
apps/spps_planner_app/data/compounds.csv
```

현재 active token 수: **212**  
manual-required active token 수: **38**  
active token 중 reagent MW blank: **85**  
active token 중 product contribution blank: **37**

blank는 무조건 오류가 아니라, vendor form이 확정되지 않은 항목에서 일부러 비워둔 경우가 있다. 예를 들어 generic `FAM`, `TAMRA`, `CY5`, `DOTA`는 acid/NHS/protected/salt form에 따라 실제 MW와 반응 조건이 달라진다. 그래서 가능한 경우 `5-FAM`, `6-FAM`, `FAM-NHS`, `DOTA-NHS`처럼 form-specific token을 사용하는 것을 권장한다.

### 2.3 Docking Workbench 보강

- Input 영역 접기/펼치기 기능 추가.
- Target summary가 화면에서 묻히는 문제 완화.
- `Input data full`, `Results data full`, `MD data full` 버튼 추가.
- PRODIGY-like, GROMACS-like, MD-style table을 Results 쪽에서 볼 수 있도록 보강.
- 이 값들은 외부 도구와 비교하기 위한 screening/reporting summary이며, 최종 Kd 또는 최종 MD 결과가 아니다.

### 2.4 PyMOL Structure Builder / Bridge

- Build SDF/PDB/PML은 modified peptide 구조 확인의 기본 경로.
- Bridge는 외부 docking/MD 실행 버튼이 아니라 hand-off package 생성 버튼.
- Bridge는 이미 생성된 구조/token map을 재사용하여 quick-safe export 방식으로 동작.
- `pal`, `PAL`, `Palmitic acid`, `caf`, `Caffeic acid`, `gal`, `Gallic acid` 등 대소문자/풀네임 alias 인식 보강.

---

## 3. 중요한 해석 경계

Pepforge는 **계획·screening·bridge export·evidence report 도구**다.

대체하지 않는 것:

- 실제 Kd/IC50/EC50 실험값
- HPLC/MS 기반 최종 QC
- AutoDock Vina/Smina/Gnina 실제 실행
- PRODIGY 실제 계산
- GROMACS/OpenMM/AMBER/NAMD production MD
- 논문급 all-atom validation

권장 표현:

```text
screening-level contact evidence
PRODIGY-like summary for external comparison
MD-style screening summary
validation bridge package generated
external validation required
```

피해야 할 표현:

```text
Pepforge가 nM binding을 증명했다
Pepforge가 PRODIGY/GROMACS를 대체한다
Pepforge가 최종 Kd를 제공한다
Pepforge 내부에서 publication-grade MD를 완료했다
```

---

## 4. 설치와 실행

### Python source 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python main_launcher.py
```

Windows에서 바로 실행:

```bash
RUN_PEPFORGE_SOURCE.bat
```

SPPS Planner만 실행:

```bash
RUN_SPPS_PLANNER_SOURCE.bat
```

Conda:

```bash
conda env create -f environment.yml
conda activate pepforge
python main_launcher.py
```

CLI 확인:

```bash
python pepforge_cli.py version
python pepforge_cli.py validate-runtime --output-dir outputs/runtime_validation
```

---

## 5. 대표 사용 흐름

### SPPS Planner

```text
Ac-EEMQRR-NH2
FITC-Ahx-EEMQRR-NH2
Pal-dG-dH-dK-NH2
Caf-EEMQRR-NH2
```

1. SPPS Planner 실행.
2. Sequence 입력.
3. Build/Rebuild.
4. Plan / Materials / Project / Checklist / Log 확인.
5. 마지막 wash가 `DMF x3 → DCM x3`인지 확인.
6. Export.

### PyMOL Structure Builder

```text
Pal-dG-dH-dK-NH2
Gal-EEMQRR-NH2
Caffeic acid-EEMQRR-NH2
FITC-Cha-AEEA-dK-NH2
```

1. Analyze.
2. Build SDF/PDB/PML.
3. Open Output.
4. token_map/report 확인.
5. 외부 docking/MD로 넘길 경우 Bridge 사용.

### Docking Workbench

1. Target PDB/mmCIF/CIF 지정.
2. Peptide sequence/notation 입력.
3. Analyze.
4. Input이 너무 크면 Collapse Input.
5. Target summary와 Results 확인.
6. 필요하면 full data 버튼으로 전체 표 확인.
7. Export.

---

## 6. GitHub 업그레이드 메모

이 패키지는 기존 v4.2.x 계열 저장소 위에 덮어 올릴 수 있도록 정리된 v2.0.0 baseline이다. 기존 output/project/runtime 결과물은 저장소에 올리지 않는 것을 권장한다. `.gitignore`는 build 결과, exe, output, project runtime 폴더, cache를 제외하도록 정리되어 있다.

---

## 7. 인용

```text
Woo, S. Pepforge: An Integrated Peptide Research Workbench. Public Research Release v2.0.0. GitHub repository.
```

```bibtex
@software{woo_pepforge_2026,
  author  = {Woo, Sanghun},
  title   = {Pepforge: An Integrated Peptide Research Workbench},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/poowsh1407/Pepforge}
}
```
