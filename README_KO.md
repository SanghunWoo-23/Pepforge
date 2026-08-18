# Pepforge

Sequence 분석, modified-peptide 설계, 구조 ensemble 생성, SPPS 계획, docking-oriented screening을 연결하는 peptide 전용 데스크톱 연구 도구입니다.

**공개 기준:** 3.0.0 · **우선 지원 환경:** Windows · **Author:** Sanghun Woo

**현재 STD:** SPPS Planner V4 근거 기반 workflow가 통합된 Pepforge V3.0.0(2026-08-13)

[English](README.md) · [STD 기준](STD_BASELINE.md) · [한국어 완전 매뉴얼](MANUAL_KO.md) · [과학적 범위](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md) · [SPPS V4 방식](docs/SPPS_V4_EVIDENCE_WORKFLOW.md) · [릴리스 안내](RELEASE_NOTES_V3.0.0.md) · [개발 참여](CONTRIBUTING.md) · [변경 내역](CHANGELOG.md)

> Pepforge의 구조, 점수, contact, 합성 권고는 연구 가설 및 계획 보조 자료입니다. 실험 측정값, 생체 내 native 구조의 증명, 의료 지침이 아닙니다.

## Workflow

V3 Modern/Classic hybrid launcher는 6개 active module을 하나의 workflow sidebar에 표시하고, 선택한 모듈의 목적·출력·workspace·명시적 실행 버튼을 보여줍니다. Docking Workbench는 한 번만 표시됩니다.

```text
sequence / target
  → hotspot 우선순위 분석
  → modified-peptide 후보 설계
  → peptide 구조 ensemble 및 대표 Top 5
  → SPPS 계획과 material 계산
  → docking-oriented screening
  → 외부 검증용 export
```

| 모듈 | 역할 | 해석 한계 |
| --- | --- | --- |
| Hot Spot Finder | 후보 sequence 구간 우선순위 분석 | 점수는 biological proof가 아님 |
| Peptide Design Engine | canonical 및 일부 modified-peptide 후보 생성 | 화학·합성 가능성 검토 필요 |
| Structure Builder | peptide conformer 생성·분류 | 생체 내 단일 구조를 확정하지 않음 |
| SPPS Planner V4 | 편집 가능한 합성 단계, material, 공정 시간, 근거 검토, 문헌 기반 경고 작성 | 검증된 실험 SOP를 자동 보장하지 않음 |
| Docking Workbench | pose/contact 기반 후보 우선순위 분석 | 내부 점수는 실험 affinity나 Kd가 아님 |
| External Tools | 외부 검증용 파일·폴더 준비 | 외부 프로그램은 별도 설치 필요 |

## Sequence 기반 구조 생성

입력 peptide sequence를 분석하여 α-helix, 3₁₀-helix, β-extended/strand-like, β-hairpin-like, PPII, turn-rich, coil/mixed 등 여러 backbone family를 탐색합니다. 공개 Top-5 build가 성공하려면 실제 좌표 후보를 정확히 5개 정렬·출력하며, 일부만 생성된 경우 완성으로 처리하지 않습니다.

Canonical L-peptide에는 짧은 stochastic search가 주요 구조 family를 놓치지 않도록 torsion-basin seed가 추가될 수 있습니다. Sequence context, terminal chemistry, D-residue, 지원되는 modification, cyclization/disulfide constraint, α/β/γ-peptidomimetic pattern은 parser와 evidence rule이 지원하는 범위에서만 반영됩니다. Seed는 탐색 후보이며 실제 평형 population 예측값이 아닙니다.

PDE는 active target과 locked example motif가 빈 상태로 시작합니다. 기본 exploratory mode는 매 실행 새로운 seed를 기록하고 최종 sequence diversity filter를 적용하며, 정확한 재현이 필요하면 seed를 잠그거나 `Repeat Last Run`을 사용합니다.

대표 출력:

```text
<name>_conformer_ensemble.sdf
<name>_conformer_families.csv
<name>_backbone_torsions.csv
```

자세한 설치·버튼 순서·입력 문법·결과 판독·문제 해결은 [한국어 완전 매뉴얼](MANUAL_KO.md), 구조 주장 범위는 [과학적 범위](docs/SCIENTIFIC_SCOPE_AND_VALIDATION.md)를 참고하십시오.

## 설치 및 실행

Python 3.10 이상과 Tk 지원 환경이 필요합니다. 전용 virtual environment 사용을 권장합니다.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main_launcher.py
```

개별 모듈 실행:

```bash
python main_launcher.py --tool hotspot
python main_launcher.py --tool design
python main_launcher.py --tool pymol
python main_launcher.py --tool spps
python main_launcher.py --tool docking
python main_launcher.py --tool external
python main_launcher.py --tool workflow
```

실제 옵션은 `python main_launcher.py --help`로 확인하십시오. 실제 3D 구조 생성에는 RDKit이 필요합니다. PyMOL과 외부 docking/MD 프로그램은 선택적 외부 프로그램입니다.

상세 workflow와 문제 해결은 [한국어 사용자 매뉴얼](MANUAL_KO.md)을 참고하십시오.

## SPPS V4 근거 기반 workflow

Pepforge에는 공개용으로 정리된 SPPS Planner V4의 단일 계획 workflow가 통합되어 있습니다. Generate/Update로 Plan, Materials, Total Materials, Checklist, cleavage 결과를 만들고, 표 수정은 `Apply Change`로 명시적으로 반영합니다.

- `verified` 기록만 exact-condition Apply의 직접 근거가 됩니다. `parsed` 기록은 검토 근거로 남으며, `incomplete`와 `excluded` 기록은 자동 적용되지 않습니다.
- Cleavage 추천은 product name이 아니라 sequence를 우선합니다.
- 한 추천은 한 개의 일관된 실제 기록에서 조건 전체를 가져옵니다. 서로 다른 기록의 cocktail을 섞거나 모델이 만든 가상 optimum을 Apply하지 않습니다.
- Loading/cleavage time은 별도 공정 조건이며 reagent stoichiometry를 몰래 변경하지 않습니다.
- Pepforge 통합본에서는 LOT Number와 Batch Manager를 제외했습니다. 공개 seed 폴더에는 실제 실험 이력이 포함되지 않습니다.

## 자동 검증

```bash
python -m compileall -q .
python -m pytest -q
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
```

통합 source baseline은 개발 환경에서 compile, source-integrity, runtime-validation, regression, verification-matrix, release-gate 검사를 통과했습니다. 단, native Windows GUI, 실제 RDKit 3D export, PyMOL session open, 외부 docking/MD 실행은 목표 컴퓨터에서 별도 확인해야 합니다.

## 공개 데이터 정책

이 저장소에는 source code, 공개 근거 기반 chemical catalog, 빈 schema/template, example, test만 포함합니다. 비공개 실험 이력, 회사 기록, credential, 미공개 dataset, 로컬 model, runtime project는 포함하지 않습니다. Fork 공개 또는 Release asset 첨부 전 [PUBLIC_DATA_POLICY.md](PUBLIC_DATA_POLICY.md)를 확인하십시오.

## Modified-peptide 표기

```text
Ac-EEMQRR-NH2
Pal-AEEA-dab(KKEK)-dG-NH2
Gal-GH-dab(EEEK)-NH2
```

PSB에서는 `Ac-/AC-`를 acetyl로, `Pal-/PAL-`을 palmitoyl로 우선 해석합니다. 개별 residue는 `A-C-` 또는 `P-A-L-`처럼 구분해 입력하십시오.

지원 근거가 없는 building block이나 parameter는 `unsupported` 또는 `estimated`로 남겨야 합니다. Pepforge는 residue propensity, force-field parameter, 실험 결과를 임의로 생성하지 않습니다.

## 저장소 구조

```text
apps/                    bundled application engine
peptiforg_core/          공통 scientific/workflow logic
spps_v4_gui/             SPPS Planner V4 workflow 및 실험 데이터 계층(LOT/Batch 제외)
suite_gui/               desktop module interface
tests/                   unit, regression, contract test
docs/                    scientific, API, release 문서
installer/               Windows build 설정
main_launcher.py         desktop entry point
pepforge_cli.py          workflow 및 release-audit CLI
```

Runtime output은 tool별 workspace에 저장됩니다. 이는 application-level isolation이며 OS security sandbox는 아닙니다.

## 기여, 인용, 라이선스

Issue에는 버전, OS, Python 버전, 실행 방식, 모듈, 최소 재현 입력, 재현 단계, 관련 log를 포함하십시오. 공개 전에 기밀·미공개 데이터를 제거하십시오.

Runtime monkey patch, 완성 기능처럼 보이는 placeholder, 조작된 scientific output, 알림 없는 기능 삭제는 허용하지 않습니다. [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하십시오.

학술 연구에 실질적으로 사용했다면 정확한 release를 명시해 인용하십시오. [CITATION.cff](CITATION.cff)에 citation metadata가 있습니다.

Pepforge는 custom **Pepforge Public Academic Citation License**를 사용하며 OSI-approved license라고 주장하지 않습니다. 재배포나 상업적 사용 전 [LICENSE](LICENSE)를 확인하십시오.
