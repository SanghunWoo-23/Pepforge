# Pepforge V6.0.0 사용자 매뉴얼

**Pepforge V6.0.0 · Public Research Source Release**

## 1. 시작

```bash
python main_launcher.py
```

Windows source 실행은 `RUN_PEPFORGE_SOURCE.bat`를 사용할 수 있습니다.

## 2. 주요 도구

### Hot Spot Finder
표적 구조에서 peptide design에 참고할 interface/hotspot evidence를 준비합니다.

### Peptide Design Engine (PDE)
canonical / modified peptide candidate를 만들고 design intent와 candidate lineage를 유지합니다.

### Structure & Docking Studio
V6의 주 구조/도킹 workspace입니다.

```text
Peptide sequence
→ conformer preparation
→ receptor preparation
→ Native Docking
→ interaction review
→ optional Native Mechanics / trajectory
→ Shared Native Result Viewer
```

#### Studio 탭 구성 (V6.0.0)
- **1. Structure Builder:** 서열·조건 입력, Conformer 생성, 파일 검토.
- **2. Docking & Simulation:** Receptor/Peptide 구조, Docking, Mechanics, 선택형 MD.
- **3. Results & Analysis:** 토큰/화학 해석, Ensemble 결과, Native Docking 결과.
- **하나의 Studio 창** 내에서 상단 탭을 클릭하거나 Ctrl+1 / Ctrl+2 / Ctrl+3으로 전환합니다. 탭마다 새 창이 열리지 않습니다. 토큰 분석과 구조 생성/도킹 완료 시 결과 탭이 자동 선택됩니다.
- 탭별 **독립 세로 스크롤**로 긴 화면을 이동합니다. 탭 변경 시 입력값은 유지됩니다.
- 긴 서열·넓은 표는 해당 위젯의 가로 스크롤을 사용합니다.
- 긴 기능 설명은 GUI 대신 README·매뉴얼에 기록합니다.

### SPPS Planner V8.0.0 — 독립 창 실행

Pepforge 메인 런처의 **4 SPPS Planner**를 선택한 뒤 **Open**을 누르면, 기존 V8의 Project Manager·Batch·Materials·Checklist·Cleavage 작업 화면이 **PDE·PSB처럼 별도 정상 창**으로 실행됩니다. 기존처럼 Pepforge 창에 강제로 결합하지 않습니다. Pepforge 메인 화면을 유지하면서 V8에서 프로젝트를 저장하거나 닫을 수 있습니다.

소스: `python -m pip install -r vendor/spps_planner_v8/requirements.txt` 다음 `python main_launcher.py --tool spps` 또는 메인 런처 사용. Windows 설치판에는 `SPPS_Planner/SPPS_Planner.exe` 동반 파일이 반드시 필요합니다. 즉시 종료되면 `spps_v8_launch.log`를 확인하십시오.

Docking & Simulation은 **Receptor 파일·서열**, **Peptide 파일·서열**을 각각 가까이 묶었으며, Peptide 서열은 Structure Builder와 동기화됩니다. Pepforge V6.0.0 / SPPS Planner V8.0.0 버전을 구분합니다.

**V8 UI 개선:** Recommendations/Lab History는 전용 `SPPS.History.Treeview` 스타일을 사용하므로 Project Manager의 Plan/Materials 열 제목이 굵게 유지되고 행 높이가 변경되지 않아야 합니다. Project Manager → Plan 확인 → Recommendations 창 열기 → Plan 복귀 순서로 점검합니다. 계산 로직은 수정하지 않았습니다.

## 3. Structure & Docking Studio 입력

### Peptide sequence
긴 canonical/modified sequence를 여러 줄 크기의 editor에 입력합니다.

### Receptor
지원 workflow에 따라 PDB/mmCIF file 또는 sequence-derived preparation을 사용합니다.

### Binding mode
- blind
- hotspot
- manual residue guidance

### Native Docking
Pepforge-owned local pose search입니다. 결과 score는 measured affinity가 아닙니다.

## 4. Native follow-up

선택한 usable pose에 대해 Native Mechanics와 trajectory analysis를 실행할 수 있습니다.

기본 분석 예:
- aligned RMSD
- Rg
- RMSF
- drift
- clustering
- medoid frame

Native Mechanics는 production MD가 아닙니다.

## 5. Public benchmark / external data

Pepforge V6에는 protein–peptide benchmark 실행을 위한 registry, RCSB PDB sync, UniProt provenance, validation/tuning infrastructure가 포함됩니다.

외부 데이터가 실제로 동기화/실행되지 않은 상태를 scientific validation PASS로 표시하지 않습니다.

## 6. 결과 해석

다음을 구분하십시오.

- docking score ≠ affinity
- docking score ≠ ΔG / Kd
- contact geometry ≠ biological activity
- RMSD stability ≠ functional validation
- predicted structure ≠ experimental structure
- Native Mechanics ≠ production MD

## 7. 출력과 프로젝트

Pepforge는 candidate → structure → docking → follow-up → review의 lineage를 유지하도록 설계되어 있습니다.

결과를 공유할 때는 score만 분리해 전달하기보다 provenance / quality gate / input context를 함께 보존하는 것을 권장합니다.

## 8. 문제 해결

### Studio 아래 기능이 보이지 않을 때
일반 마우스 휠 또는 오른쪽 scrollbar로 아래로 이동합니다.

### Studio가 가로로 늘어날 때
현재 V6.0.0에서 외부 Canvas의 가로 크기 안정화 기능을 유지합니다. Pepforge V6.0.0 패키지인지 확인하십시오.

### SPPS 화면이 예전 버전처럼 보일 때
Pepforge V6.0.0을 완전히 압축 해제한 뒤 `python main_launcher.py --tool spps`로 SPPS Planner V8.0.0 Public 실행 경로를 확인하십시오.

### optional dependency가 없을 때
Native core는 가능한 범위에서 계속 실행하며 optional backend는 별도 status로 표시됩니다.

## 9. 문서

- `README_KO.md` / `README.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `CONTRIBUTING.md`

상세 개발 인수인계서는 공개 소스와 분리해 내부용으로 관리합니다.


### PDB/mmCIF 직접 Native Docking 사용법 (V6.0.0)

1. `Structure & Docking Studio → Docking & Simulation`을 엽니다.
2. Receptor에서 `file`을 선택하고 PDB/CIF/mmCIF 수용체를 선택합니다.
3. Peptide에서 `file`을 선택하고 3D PDB/mmCIF/SDF/MOL 파일을 지정합니다. Peptide Sequence는 Structure Builder 입력과 동일한 값을 공유합니다.
4. Docking backend를 `native`로 설정합니다. 첫 검증에서는 선택형 OpenMM MD를 해제해 Native Docking만 먼저 확인하세요.
5. `BUILD + DOCK + ANALYZE` 클릭 후 Docking 탭 진행률을 확인합니다. 종료 후 `Results & Analysis`에서 검증된 Pose, 구조, 상호작용과 결과 보고서를 확인합니다.
6. 오류나 Pose 0개일 때는 성공이 아닙니다. 오류 메시지 및 `Direct_Docking/<실행ID>/results/v6_compute_pipeline.json`을 확인하세요. mmCIF 원본의 chain, 여러 모델, alternate location, ligand 및 비표준 잔기는 별도로 검토해야 합니다.

Native Score는 무차원 탐색 점수입니다. ΔG/Kd/실험 친화도와 동일하게 해석해서는 안 됩니다. 일부 구조에 대한 실행 성공이 모든 구조의 적합성을 보증하지 않습니다.
