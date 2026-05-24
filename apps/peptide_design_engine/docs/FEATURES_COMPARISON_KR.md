# Peptide Design Engine — 특징, 차이점, 장단점

## 1. 핵심 정체성

Peptide Design Engine은 단순 peptide sequence generator가 아니다.

이 엔진은 다음 역할을 수행한다.

```text
peptide candidate generation
+ constraint-based design
+ hotspot-guided target bias
+ chemistry-aware modeling
+ docking-readiness classification
+ structured export
```

즉, 이 엔진은 다음 단계를 연결하는 설계-검증 인터페이스 시스템이다.

```text
design → validation preparation
```

---

## 2. 주요 장점

### 2.1 Design-to-validation 통합

기존 workflow:

```text
peptide 생성
→ manual filtering
→ docking 준비
→ 구조 검증
```

이 엔진:

```text
생성
→ 필터링
→ docking-ready 분류
→ CSV / FASTA / manifest export
```

장점:

```text
중간 단계 자동화
workflow 단축
재현성 증가
```

### 2.2 Hotspot 기반 설계

protein sequence 또는 PDB에서 hotspot-like fragment를 자동 추출할 수 있다.

효과:

```text
target-derived design bias 부여
```

주의:

```text
binding 예측은 아님
```

### 2.3 Hotspot과 Motif 분리

```text
HOTSPOT = target-derived reference
MOTIF   = user-defined functional sequence
```

이 둘을 분리함으로써 다음 설계가 가능하다.

```text
target-derived bias + user-defined functional motif
```

### 2.4 Motif 위치 제어

지원 위치:

```text
FREE
N_TERM
CENTER
C_TERM
```

기능성 motif를 원하는 위치에 배치할 수 있다.

### 2.5 Chemistry-aware 설계

지원:

```text
D-form
noncanonical
linker
tag
label
chemical modification
```

실험용 peptide construct를 더 현실적으로 표현할 수 있다.

### 2.6 Docking-readiness 분류

후보를 다음처럼 분류한다.

```text
DIRECT_LFORM_DOCKING_READY
PARAMETERIZED_DOCKING_READY
PARAMETERIZATION_HEAVY
BLOCKED_UNSUPPORTED_TOKEN
```

구조검증 준비 상태를 바로 판단할 수 있다.

### 2.7 Colab 기반 인터페이스

설치 없이 실행 가능하고 UI 기반으로 조작할 수 있다.

장점:

```text
접근성 증가
재현성 증가
공유 용이
```

### 2.8 설명 가능한 설계

결과 파일에 다음 컬럼이 포함된다.

```text
target_hotspot_sequences
hotspot_peptide_map
best_hotspot
```

이로써 어떤 hotspot이 설계에 사용되었고 peptide와 어떻게 연결되는지 확인할 수 있다.

---

## 3. 다른 도구와의 차이

### 3.1 단순 peptide generator와의 차이

일반 generator:

```text
sequence 생성
score 출력
```

이 엔진:

```text
sequence 생성
chemistry 처리
hotspot bias
motif 제어
docking-ready 분류
structured export
```

차이:

```text
설계 + 해석 + 검증 준비까지 포함
```

### 3.2 Docking tool과의 차이

Docking tool:

```text
prepared structure → docking pose / score
```

이 엔진:

```text
candidate peptide generation → docking-ready preparation
```

즉, docking tool의 upstream design layer이다.

### 3.3 ML 기반 generator와의 차이

ML generator:

```text
학습 데이터 의존
black-box 가능성
```

이 엔진:

```text
heuristic 기반
설명 가능
ML optional
```

장점:

```text
데이터 없어도 사용 가능
해석 가능
```

### 3.4 Structure prediction tool과의 차이

AlphaFold/ColabFold 등:

```text
구조 예측
```

이 엔진:

```text
입력 peptide 후보 생성 및 정리
```

즉, structure prediction tool에 들어갈 후보를 준비하는 역할이다.

---

## 4. 한계

이 엔진은 다음을 직접 수행하지 않는다.

```text
molecular docking
binding energy calculation
molecular dynamics simulation
formal SASA calculation
experimental validation
```

PDB 기반 hotspot은 정식 SASA가 아니라 C-alpha neighbor 기반 surface-exposure proxy이다.

따라서 결론은 다음 범위로 제한해야 한다.

```text
candidate generation
target-derived design bias
structural validation preparation
```

---

## 5. 논문용 안전 표현

```text
We present a Colab-first peptide design framework that integrates hotspot-guided target bias, chemistry-aware sequence generation, motif-position control, and docking-readiness classification for downstream validation workflows.
```

```text
The framework does not perform docking directly. Instead, it generates docking-ready peptide candidates and prepares structured outputs for downstream docking, structure prediction, or experimental validation workflows.
```

```text
The optional hotspot module provides target-derived design bias using sequence-based or SASA-like surface-exposure proxy features.
```

---

## 6. 요약

```text
장점:
설계 + 해석 + 검증 준비 통합

차별점:
target-aware + chemistry-aware + explainable

한계:
binding prediction 없음
```
