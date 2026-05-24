# 엔진 기능과 차별점

## 1. 엔진의 정체성

Peptide Design Engine은 단순 sequence generator도 아니고 docking simulator도 아니다.

이 엔진은 다음 역할을 한다.

```text
peptide design과 structural validation 사이를 연결하는 interface layer
```

즉, peptide 후보를 만들고, 화학적/구조적 조건을 반영하여, 외부 docking 또는 구조검증 도구로 넘기기 좋은 형태로 정리한다.

---

## 2. 핵심 기능

### 2.1 Colab-first interactive design

#### 프리셋 기반 UI

Colab UI에는 Fast Mode, Paper Mode, Exploration Mode가 포함되어 있다. 이 프리셋들은 권장 설정을 빠르게 적용하기 위한 것이며, 엔진 기능을 제한하지 않는다.



Colab UI를 중심으로 설계되어 있다.

장점:

- 코드 수정 없이 옵션 조정 가능
- length, design mode, chemistry option 선택 가능
- 실험자가 사용하기 쉬움
- Python 환경에 익숙하지 않아도 사용 가능

### 2.2 Chemistry-aware token handling

다음 개념을 보존한다.

- D-form residue
- noncanonical residue
- linker
- tag
- label
- chemical modification

이 후보들을 무조건 제거하지 않고 docking-readiness에 따라 분류한다.

### 2.3 Docking-readiness classification

일반 sequence generator는 좋은 sequence만 출력한다.

이 엔진은 추가로 묻는다.

```text
이 후보를 구조검증 workflow에 어떻게 넘길 수 있는가?
```

그래서 후보를 다음처럼 나눈다.

- 바로 docking 가능한 L-form 후보
- parameterization이 필요한 후보
- heavy modeling이 필요한 후보
- unsupported token이 있는 후보

### 2.4 Bridge / linker / epitope-oriented design

단순 random peptide 생성보다 구체적인 설계 개념을 포함한다.

지원 개념:

- bridge linker
- motif-aware design
- epitope-oriented planning
- constrained design
- multi-target exploration

### 2.5 Structured export

출력 예:

- ranked CSV
- docking-ready CSV
- modeling manifest
- surrogate FASTA
- pseudo-docking index

### 2.6 Optional ML 구조

ML은 핵심 엔진에 강제되지 않는다.

장점:

- 데이터가 없어도 작동
- heuristic 기반 해석 가능성 유지
- docking score나 실험 label이 생기면 확장 가능

### 2.7 Optional pseudo-docking input preparation

엔진은 pseudo-docking을 직접 수행한다고 주장하지 않는다.

대신 receptor:peptide FASTA 입력을 준비한다.

---

## 3. 다른 접근법과의 차이

### 일반 peptide sequence generator와의 차이

일반 sequence generator:

```text
sequence 생성 → score 출력
```

이 엔진:

```text
sequence 생성 → chemistry 보존 → docking-readiness 분류 → export
```

### Docking tool과의 차이

Docking tool:

```text
입력된 peptide 구조를 target에 docking
```

이 엔진:

```text
도킹에 넘길 peptide 후보를 생성하고 분류
```

즉, docking tool의 upstream design layer다.

### ML-only model과의 차이

ML-only model은 학습 데이터에 크게 의존한다.

이 엔진은:

- ML 없이도 작동
- heuristic scoring 제공
- ML은 optional
- 데이터가 쌓이면 확장 가능

---

## 4. 강점

- 실험자가 이해하기 쉬운 Colab UI
- 화학적 다양성 유지
- docking-readiness 명시
- 논문용 output 정리 가능
- 과장된 docking claim 회피

---

## 5. 한계

이 엔진은 다음을 직접 수행하지 않는다.

- full molecular docking
- molecular dynamics simulation
- wet-lab validation
- binding affinity prediction의 확정적 증명

---

## 6. 요약

이 엔진은 다음을 목표로 한다.

```text
화학적 다양성을 보존한 peptide 후보 생성
+
도킹/구조검증 가능성 분류
+
후속 validation workflow로 넘길 수 있는 output 생성
```
