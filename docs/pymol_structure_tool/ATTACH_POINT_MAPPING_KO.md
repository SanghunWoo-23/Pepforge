# Attach-point mapping v1.3.0

이 버전의 목표는 PyMOL에서 chemical / label / linker / non-natural / D/L AA가 포함된 modified peptide를 한 덩어리 구조로 띄우고, 어느 원자가 결합 진입점(IN)·결합 진행점(OUT)인지 확인할 수 있게 하는 것이다.

## 핵심 규칙

- blue sphere = 해당 token/template의 inferred IN attach atom
- red sphere = 해당 token/template의 inferred OUT attach atom
- label 계열(Biotin, FITC, Cy5 등)은 보통 OUT atom이 없고 terminal 또는 side-chain modification으로 끝난다.
- linker/non-natural/chemical 중 carbonyl을 가진 token은 OUT atom이 표시된다.

## 생성 파일에 남는 정보

각 구조의 JSON에는 다음 필드가 추가된다.

```json
"attach_point_map": [
  {
    "token": "Ahx",
    "kind": "linker",
    "local_in_atom_1based": 1,
    "local_out_atom_1based": 8,
    "global_in_atom_1based": 45,
    "global_out_atom_1based": 52
  }
]
```

이 값은 PyMOL PML에서 자동으로 selection과 sphere label로 반영된다.

## 한계

v1.3.0은 attach atom을 명시적으로 기록하고 PyMOL에 표시하지만, 최종 docking/MD용 좌표를 보장하지 않는다. 논문용·도킹용으로 쓰려면 curated SDF template의 attach atom ID를 사람이 검수하고, 필요 시 MMFF/xTB/MD minimization을 추가해야 한다.
