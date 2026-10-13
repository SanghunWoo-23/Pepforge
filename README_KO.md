# Pepforge V5.0.0 FINAL

**UI Polish R4 · 2026-10-12**

Pepforge는 펩타이드 설계, 구조 준비, native docking, interaction review, mechanics/trajectory follow-up, SPPS planning을 하나의 로컬 workflow로 연결하는 peptide R&D desktop toolkit입니다.

## V5 FINAL R4 핵심

### Structure & Docking Studio

PSB와 Native Docking을 한 Studio에서 이어서 사용합니다.

`Peptide input → conformer preparation → receptor preparation → Native Docking → interaction/mechanics/trajectory review`

- 긴 peptide sequence를 위한 큰 multi-line 입력창
- **일반 마우스 휠로 페이지 스크롤**
- `PageUp / PageDown / Home / End` 지원
- 끝구간에서 반복 wheel event를 누적하지 않는 edge clamp
- 고해상도 마우스 wheel event coalescing
- scrollregion update debounce
- outer page 폭을 viewport에 고정하여 scrollbar drag 시 화면이 늘어나는 geometry feedback 차단
- 긴 sequence와 결과표는 각 widget의 자체 horizontal scrollbar 사용

### Workflow Mode

Workflow Mode도 같은 안정적인 vertical page scrolling contract를 사용합니다.

- 일반 마우스 휠로 전체 workflow 이동
- 긴 페이지 끝구간의 버벅임 완화
- scrollbar thumb를 직접 움직여도 outer page 폭 고정
- 기존 project/candidate lineage와 workflow hand-off 계약 유지

### SPPS Planner 연동

Pepforge는 제공된 **SPPS Planner V7.0.0 FINAL R2**의 UI/launch 패턴을 참고하고, Pepforge에서 필요한 runtime integration만 유지합니다. Pepforge와 SPPS Planner의 프로젝트 정체성은 분리되어 있습니다.

## 실행

```bash
python main_launcher.py
```

Launcher에서 주요 workflow를 선택합니다.

1. Hotspot Finder
2. Peptide Design Engine
3. Structure & Docking Studio
4. SPPS Planner
5. External Validation

## 주요 기능

- Hot Spot Finder
- Peptide Design Engine (PDE)
- Structure & Docking Studio (PSB + Native Docking)
- modified-peptide notation/chemistry handling
- interaction evidence review
- Native Mechanics / Trajectory analysis
- Shared Native Result Viewer
- SPPS Planner integration
- public protein–peptide benchmark/tuning infrastructure
- RCSB PDB / UniProt provenance bridge
- project/session/result lineage

## Scientific claim boundary

Pepforge의 native docking score는 내부 pose-search score입니다.

- docking score ≠ measured affinity
- docking score ≠ ΔG / Kd
- contact geometry ≠ biological activity
- RMSD stability ≠ functional validation
- Native Mechanics ≠ production MD

V5의 목표는 실행 가능한 native scientific workflow와 검증 가능한 provenance를 제공하는 것이며, 실험적 truth를 만들어내는 것이 아닙니다.

## 문서

- `MANUAL_KO.md` — 한국어 사용 설명서
- `MANUAL_EN.md` — English manual
- `CHANGELOG.md` — release history
- `CONTRIBUTING.md` — contribution guide
- `SECURITY.md` — security policy

V6/V7 Roadmap과 상세 인수인계 자료는 공개 repository와 분리된 Handover package에서 관리합니다.
