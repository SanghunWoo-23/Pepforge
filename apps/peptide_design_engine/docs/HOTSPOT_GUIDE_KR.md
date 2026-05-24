# Hotspot / PDB / Motif Position Guide

## 기능 요약

이 버전은 기존 기능을 유지하면서 다음 optional 기능을 추가한다.

- protein sequence 기반 hotspot-like fragment 추출
- PDB text 기반 surface exposure proxy 추출
- 추출된 fragment를 TARGETS로 자동 사용
- 추출된 fragment를 motif로 lock 가능
- motif 위치 지정: FREE / N_TERM / CENTER / C_TERM

## 주의

PDB 기반 기능은 정식 SASA 계산이 아니라 CA-neighbor count 기반 surface proxy다. 논문에서는 `SASA-like surface exposure proxy` 또는 `surface-exposure proxy`라고 쓰는 것이 안전하다.

## 추천 사용

- 단백질 전체 sequence만 있을 때: `HotSource = SEQUENCE`
- PDB 구조가 있을 때: `HotSource = PDB`
- target-specific bias를 강화하고 싶을 때: `Use as TARGETS = ON`
- 추출 motif를 강제 포함하고 싶을 때: `Lock hotspots = ON`
- 특정 기능성 motif 위치를 고정하고 싶을 때: `MotifPos = N_TERM / CENTER / C_TERM`

## 해석

이 기능은 결합을 증명하지 않는다. target-derived candidate generation bias를 강화하는 optional preprocessing이다.
