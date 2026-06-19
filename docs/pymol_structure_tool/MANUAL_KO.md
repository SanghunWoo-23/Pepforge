# Pepforge PyMOL Structure Tool v1.0.0 Manual

## 1. 목적

이 툴은 label, tag, linker, non-natural AA, L/D-form AA가 포함된 modified peptide 문자열을 받아 PyMOL에서 바로 볼 수 있는 3D starting structure를 생성한다.

핵심 출력물은 다음 5종이다.

- `.sdf`: 결합 정보 보존용 구조 파일
- `.pdb`: PyMOL/일반 viewer 호환용 구조 파일
- `.json`: token 분류, atom range, MW, formula, warning 기록
- `_report.txt`: 사람이 읽는 검증 리포트
- `.pml`: PyMOL 자동 로딩/색상/label 스크립트

## 2. 입력 문법

### 기본 sequence

```text
ACDEFGHIK
```

### D-form

```text
dK-dF-dL
```

### non-natural AA

```text
Ac-dK-Aib-LVFF-NH2
```

### linker + label

```text
Ac-dK-Aib-LVFF-Ahx-Biotin-NH2
```

이 경우 Biotin은 sequence residue가 아니라 label로 분류된다.

### side-chain label

```text
Ac-K(FITC)-LVFF-NH2
Ac-K(Ahx-Biotin)-LVFF-NH2
```

괄호 안에는 linker-label 조합을 넣을 수 있다.

## 3. 실행 명령

```bash
python build_for_pymol.py "Ac-K(Ahx-Biotin)-LVFF-NH2" --name K_Ahx_Biotin_LVFF --outdir outputs --confs 8
```

옵션:

| 옵션 | 의미 |
|---|---|
| `--name` | 출력 파일명/객체명 |
| `--outdir` | 출력 폴더 |
| `--confs` | 생성할 conformer 수 |
| `--no-opt` | force-field 최적화 생략 |
| `--keep-all-confs` | SDF에 모든 conformer 저장 |
| `--parse-only` | 구조 생성 없이 token 분류만 출력 |
| `--tokens` | 지원 token 목록 출력 |
| `--env` | RDKit 환경 확인 |
| `--batch-csv` | CSV batch 생성 |
| `--prefer sdf/pdb` | PML에서 어떤 구조 파일을 load할지 지정 |

## 4. PyMOL에서 확인

```pymol
@outputs/K_Ahx_Biotin_LVFF.pml
```

PML은 구조를 load하고 category별 색상/selection/token label을 자동 생성한다.

## 5. 리포트 해석

`*_report.txt`에는 다음이 들어간다.

- 입력 sequence
- molecular formula
- exact molecular weight
- heavy atom 수
- category count
- token별 atom range
- chemistry audit
- conformer summary
- warnings

## 6. 주의점

이 결과는 connected 3D starting model이다. 실험 구조나 docking/MD-ready 구조가 아니다. 큰 label/fluorophore는 simplified fragment 기반이므로 실제 연구용 정밀 구조는 template 교체와 추가 minimization이 필요하다.
