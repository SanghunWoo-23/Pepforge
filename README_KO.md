<div align="center">

<img src="assets/Pepforge_Icon.png" alt="Pepforge" width="150">

# Pepforge

### 펩타이드 설계 · 구조 생성 · SPPS 계획 · 상호작용 검토를 하나로 연결하는 연구용 워크벤치

**Pepforge V4.0.0 · Public Research Source Release**

[![Release](https://img.shields.io/badge/release-v4.0.0-2563EB?style=for-the-badge)](VERSION.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#빠른-시작)
[![Release Gate](https://img.shields.io/badge/release_gate-25%2F25-16A34A?style=for-the-badge)](#검증)

**[English](README.md) · [빠른 시작](#빠른-시작) · [주요 기능](#주요-기능) · [Modified peptide](#modified-peptide-지원) · [과학적 범위](#과학적-범위) · [전체 매뉴얼](MANUAL_KO.md)**

</div>

---

## 개요

Pepforge는 **서열 수준 후보 탐색 → 펩타이드 설계 → 3D 구조 생성 → SPPS 계획 → protein–peptide interaction 검토 → 외부 검증 hand-off**를 하나의 흐름으로 연결하는 Windows 우선 데스크톱 연구 도구입니다.

일반적인 canonical peptide뿐 아니라 지원되는 범위에서 terminal chemistry, D-amino acid, non-natural residue, linker, label 및 modified-peptide notation을 보존합니다. 동시에 계산 결과와 실험 근거의 경계를 분명하게 유지합니다.

```text
Target / protein sequence
        ↓
Hot Spot Finder
        ↓
Peptide Design Engine (PDE)
        ↓
Peptide Structure Builder (PSB)
        ↓
SPPS Planner
        ↓
Docking Workbench / interaction review
        ↓
Evidence export / external validation hand-off
```

Pepforge는 내부 점수를 실험적 affinity로 바꾸어 주장하지 않으며, 지원되지 않는 chemistry를 임의로 canonical residue로 치환하거나 가짜 all-atom 구조를 만들지 않습니다.

---

## 주요 기능

| 모듈 | 기능 |
| --- | --- |
| **Workflow Mode** | Hot Spot → PDE → PSB → SPPS를 candidate lineage와 project/session 상태로 연결 |
| **Hot Spot Finder** | protein/peptide sequence를 직접 입력해 후보 구간을 ranking하고 결과 export |
| **Peptide Design Engine** | Pareto NSGA-II, 5개 scientific design mode, chemistry-aware diversity, stable candidate ID 기반 후보 생성/평가 |
| **Peptide Structure Builder** | 지원 chemistry를 해석하고 explicit structure intent가 있을 때 이를 반영한 최대 5개 ranked coordinate 후보 생성 |
| **SPPS Planner** | Plan, Materials, Total Materials, Checklist, cleavage review, evidence guidance, project export |
| **Docking Workbench** | residue-centered contact와 보수적 interaction evidence를 통한 peptide–target 구조 검토 |
| **Structure / validation tools** | PDB/SDF 비교, PyMOL review 준비, 외부 docking/MD hand-off |

PDE의 scientific design objective는 다음 5개입니다.

- Interaction Only
- Interaction First
- Balanced
- Structure Guided
- Structure Exploration

PSB는 지원 범위에서 α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, coil/mixed 계열을 탐색합니다. 생성 구조는 **검토 및 후속 검증을 위한 starting hypothesis**이지 생리적 native state의 증명이 아닙니다.

---

## R14 핵심 변경

R14에서는 PSB가 만든 PDB를 Docking Workbench에 다시 넣을 때 peptide identity가 유실되는 문제를 보완했습니다.

PSB PDB에 다음이 함께 기록됩니다.

- peptide `SEQRES`
- `REMARK 901 PEPFORGE_EXACT_SEQUENCE`
- token/modifier metadata
- 기존 residue-aware `ATOM` / `HETATM` 좌표
- 긴 exact sequence용 continuation metadata

예를 들어 아래 notation을 PDB 안에 보존할 수 있습니다.

```text
Ac-EEMQRR-NH2
Pal-AEEA-dK-NH2
```

Docking Workbench의 sequence 복원 순서는 다음과 같습니다.

```text
Pepforge exact-sequence metadata
        ↓
SEQRES
        ↓
ATOM / HETATM residue extraction
```

Modifier와 linker는 peptide residue numbering을 소모하지 않습니다. 이미 curated coordinate graph가 있는 chemistry는 좌표를 유지하지만, derivative/attachment가 하나로 결정되지 않는 chemistry에는 가짜 all-atom 좌표를 부여하지 않습니다.

R12/R13의 SPPS 수정도 그대로 유지됩니다. Project Manager의 visible Sequence가 Generate/Apply의 기준이며, 빈 시작/idle refresh 상태에서는 parser를 자동 호출하지 않아 `Core sequence is empty`가 실행 직후 뜨지 않습니다.

자세한 검증은 [R14 validation](docs/validation/VALIDATION_R14_2026-09-21.md)과 [GitHub-ready validation](docs/validation/GITHUB_READY_VALIDATION_R14_2026-09-22.md)을 참고하십시오.

---

## Modified peptide 지원

예시:

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Biotin-AEEA-GH-dab(EEEK)-NH2
```

| 입력 | 해석 |
| --- | --- |
| `Ac-` / `AC-` | N-terminal acetyl modifier |
| `Pal-` / `PAL-` | N-terminal palmitoyl modifier |
| `A-C-` | Ala–Cys residue sequence |
| `P-A-L-` | Pro–Ala–Leu residue sequence |
| `FITC-` / `Biotin-` | 지원되는 label/tag token |
| `AEEA`, `Ahx`, PEG 계열 | 지원되는 linker token |
| D/non-natural residue | 가능한 범위에서 별도 chemistry identity로 보존 |

`ACDE-NH2`는 A-C-D-E sequence이며, terminal modifier를 의미하려면 explicit separator가 있는 `AC-...` notation을 사용합니다.

지원 여부는 workflow stage마다 다릅니다. Parse/metadata 보존은 가능하지만 정확한 3D derivative가 정의되지 않은 경우에는 좌표 생성을 제한할 수 있습니다.

자세한 내용은 [Modified Peptide Support](docs/MODIFIED_PEPTIDE_SUPPORT_V4.md)와 [Token Registry / Sequence Grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md)을 참고하십시오.

---

## SPPS Planner

Pepforge V4.0.0에는 **SPPS Planner V5.0.0 Public/Data-Sanitized** workflow가 통합되어 있습니다.

주요 기능:

- editable Plan
- step-wise Materials
- Total Materials
- Checklist
- cleavage review
- project/session persistence
- literature/evidence guidance
- 사용자가 로컬에서 기록한 experimental evidence 기반 decision support

Public package에는 private laboratory history, private seed DB, 사용자 로컬 experimental database가 포함되지 않습니다. LOT Number와 Batch Manager는 Pepforge operator-facing integration에서 의도적으로 제외되어 있습니다.

---

## Docking / interaction review

Docking Workbench는 validated docking engine, all-atom MD, binding experiment를 대체하는 도구가 아니라 **구조 및 interaction screening/review layer**입니다.

지원되는 보수적 interaction review 범주에는 hydrogen bond, hydrophobic contact, salt bridge, π–π, cation–π, vdW/clash, disulfide geometry, water bridge, metal coordination, halogen bond, aromatic–sulfur, weak C–H···O/N, NH–π 등이 포함됩니다.

Geometry-aware interaction evidence와 coarse contact triage는 분리되어 있으며, 내부 score나 거리 기준은 실험적으로 측정된 affinity가 아닙니다.

---

## 빠른 시작

### 요구사항

- Windows 10/11 권장
- 64-bit Python **3.10+**
- Tk 지원
- 실제 3D 구조 생성을 위한 RDKit

PyMOL 및 외부 docking/MD 프로그램은 선택 사항이며 별도로 설치합니다.

### Source 실행

```bat
git clone https://github.com/poowsh1407/Pepforge.git
cd Pepforge
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

### 모듈 직접 실행

```bat
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool structure
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool workflow
python main_launcher.py --tool external
```

`--tool pymol`은 structure-builder route의 호환 alias로 유지됩니다.

전체 버튼 순서와 troubleshooting은 [MANUAL_KO.md](MANUAL_KO.md)를 참고하십시오.

---

## 저장소 구조

```text
Pepforge/
├─ main_launcher.py
├─ pepforge_cli.py
├─ suite_gui/
├─ peptiforg_core/
├─ pepforge_structure_tool/
├─ spps_v4_gui/
├─ apps/
├─ tests/
├─ docs/
├─ installer/
├─ MANUAL_EN.md
└─ MANUAL_KO.md
```

Runtime workspace, generated outputs, local DB, credentials, cache, private experimental history는 public source package에서 제외됩니다.

---

## 검증

GitHub-ready R14 public source tree의 최종 공개 패키징 검증 결과입니다.

| 항목 | 결과 |
| --- | ---: |
| Release Gate | **25 / 25 passed** |
| Release Verify Matrix | **16 / 16 passed** |
| Release Integrity | **18 / 18 passed** |
| Full Package Audit | **20 / 20 passed** |
| Source-integrity audit | **0 findings** |
| Focused GitHub-readiness regression | **32 / 32 passed** |
| Release Gate compile | **325 Python files / 0 errors** |
| 대표 modified construct PDB round-trip | **20 / 20 passed** |
| explicit/buildable chemistry round-trip | **47 / 47 passed** |

로컬에서 다음 검증을 실행할 수 있습니다.

```bat
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

---

## 과학적 범위

Pepforge는 **research prioritization, reproducible computational preparation, synthesis planning, validation hand-off**를 위한 연구 지원 도구입니다.

V4에서는 production MD 실행과 trajectory 분석을 사용자 기능으로 제공하지 않습니다. 외부 simulation workflow 준비는 가능하지만 실제 production simulation 및 trajectory analysis는 향후 V5 범위입니다.

Pepforge 결과만으로 다음을 증명할 수 없습니다.

- experimental binding affinity / Kd
- binding free energy
- native in-vivo structure
- biological efficacy
- synthesis yield / purity
- laboratory safety / validated SOP

지원되지 않는 building block, force-field parameter, experimental outcome, 최적 synthesis condition을 임의로 만들어내지 않습니다.

---

## 문서

| 문서 | 내용 |
| --- | --- |
| [한국어 매뉴얼](MANUAL_KO.md) | 설치, 사용법, 입력, 출력, troubleshooting |
| [English Manual](MANUAL_EN.md) | Complete English guide |
| [Modified Peptide Support](docs/MODIFIED_PEPTIDE_SUPPORT_V4.md) | stage별 chemistry 지원 범위 |
| [Token Registry / Grammar](docs/TOKEN_REGISTRY_AND_SEQUENCE_GRAMMAR.md) | sequence/modifier token 규칙 |
| [PSB Conformer Engine](docs/PSB_CONFORMER_ENGINE.md) | 구조 생성 및 Top-5 경로 |
| [SPPS V5 Integration](docs/SPPS_V5_INTEGRATION.md) | SPPS evidence workflow |
| [Public Data Policy](PUBLIC_DATA_POLICY.md) | public/private 데이터 경계 |
| [Release Notes](RELEASE_NOTES_V4.0.0.md) | V4.0.0 릴리스 요약 |

---

## Citation / License

학술 작업에 Pepforge 또는 Pepforge-generated workflow가 실질적으로 기여했다면 사용한 **정확한 release**를 인용하십시오. Citation metadata는 [CITATION.cff](CITATION.cff)에 있습니다.

권장 표기:

> Woo, S. *Pepforge: An Integrated Peptide Research Workbench*. Version 4.0.0, 2026. https://github.com/poowsh1407/Pepforge

Pepforge는 custom **Pepforge Public Academic Citation License**를 사용하며 OSI-approved open-source license로 표시하지 않습니다. 재배포/파생 배포/상업적 사용 전 [LICENSE](LICENSE)를 확인하십시오.

---

<div align="center">

**Pepforge V4.0.0**  
Peptide sequence에서 structure, SPPS planning, interaction review, validation hand-off까지.

</div>
