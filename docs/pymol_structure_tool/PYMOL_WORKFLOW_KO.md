# PyMOL Workflow

## 기본 흐름

```text
modified peptide 입력
→ build_for_pymol.py 실행
→ SDF/PDB/JSON/report/PML 생성
→ PyMOL에서 PML 실행
```

## 예시

```bash
python build_for_pymol.py "Ac-dK-Aib-LVFF-Ahx-Biotin-NH2" --name test --outdir outputs --confs 8
```

PyMOL:

```pymol
@outputs/test.pml
```

## PML이 하는 일

- SDF 또는 PDB 구조 load
- stick 표시
- 수소 숨김
- token별 selection 생성
- category별 색상 적용
- token label 표시
- 전체 구조 zoom/orient

## 색상

- STD AA: white
- D-form: hotpink
- non-natural AA: yelloworange
- side-chain labeled AA: magenta
- linker: cyan
- label: lime
- N-terminal mod: orange
- C-terminal atom: marine

## 주의

PML은 PyMOL 플러그인이 아니라 실행 스크립트다. PyMOL에 설치할 필요가 없다.
