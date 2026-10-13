# Pepforge V5.0.0 FINAL 사용자 매뉴얼

**UI Polish R3 · 2026-10-08**

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
V5의 주 구조/도킹 workspace입니다.

```text
Peptide sequence
→ conformer preparation
→ receptor preparation
→ Native Docking
→ interaction review
→ optional Native Mechanics / trajectory
→ Shared Native Result Viewer
```

#### 스크롤
- 일반 마우스 휠: 전체 Studio 위/아래 이동
- PageUp / PageDown: 페이지 단위 이동
- Home / End: 맨 위 / 맨 아래
- 가운데 버튼은 필요하지 않음
- 긴 peptide sequence: sequence 입력창 자체 horizontal scrollbar 사용
- 긴 table: table 자체 scrollbar 사용

### SPPS Planner
Pepforge는 **SPPS Planner V7.0.0 FINAL R2** runtime을 기본 synthesis planner로 실행합니다.

주요 화면:
- Project Manager
- Batch Manager
- Add/Edit peptide
- synthesis plan / material / checklist workflow

source 실행에서는 별도 process로 열립니다.

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

Pepforge V5에는 protein–peptide benchmark 실행을 위한 registry, RCSB PDB sync, UniProt provenance, validation/tuning infrastructure가 포함됩니다.

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
R3에서는 outer page horizontal expansion을 차단했습니다. 최신 R3 package인지 확인하십시오.

### SPPS 화면이 예전 버전처럼 보일 때
최신 R3 package의 launcher로 실행하십시오. 정상 source runtime 제목은 `SPPS Planner V7.0.0 Final`입니다.

### optional dependency가 없을 때
Native core는 가능한 범위에서 계속 실행하며 optional backend는 별도 status로 표시됩니다.

## 9. 문서

- `README_KO.md` / `README.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `CONTRIBUTING.md`

상세 개발 인수인계와 V6/V7 roadmap은 Internal/Handover package에서 별도 관리합니다.
