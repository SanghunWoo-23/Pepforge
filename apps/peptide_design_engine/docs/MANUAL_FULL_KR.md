# Peptide Design Engine — Full User Manual KR

## 1. 엔진 개요

Peptide Design Engine은 peptide 후보를 생성하고, 조건을 적용하고, 구조 검증에 사용할 수 있도록 정리하는 설계 시스템이다.

이 엔진이 하는 일:

```text
peptide 후보 생성
→ length / chemistry / motif / linker 조건 적용
→ target 또는 hotspot 기반 설계 bias 적용
→ scoring 및 filtering
→ docking-readiness 분류
→ CSV / FASTA / manifest export
```

이 엔진이 하지 않는 일:

```text
molecular docking
binding energy calculation
molecular dynamics
wet-lab validation
```

따라서 결과는 “후보 생성 및 구조검증 준비”로 해석해야 한다.

---

## 2. Colab 기본 사용 순서

1. GitHub repo를 Colab에서 clone한다.
2. requirements.txt가 있으면 자동 설치한다.
3. `Ultimate_Peptide_Final_Engine.py`를 로드한다.
4. `Ultimate_Peptide_Final_UI.py`를 로드한다.
5. `Ultimate_Peptide_Final_Run.py`를 로드한다.
6. UI에서 옵션을 선택한다.
7. `RUN FINAL PIPELINE` 버튼을 누른다.
8. 결과 CSV / FASTA / manifest 파일을 확인한다.
9. 필요하면 `Colab_Analysis_Cell.py` 코드를 실행해 figure zip을 생성한다.

---

## 3. Target Mode

Colab UI의 TargetMode는 다음 세 가지다.

```text
SINGLE
MULTI
BRIDGE
```

### SINGLE

target 또는 hotspot이 하나일 때 사용하는 모드다.

추천 상황:

```text
target epitope 1개
hotspot 1개
단일 target bias 실험
```

### MULTI

target 또는 hotspot이 여러 개일 때 사용하는 모드다.

추천 상황:

```text
Auto Hotspot으로 HOTSPOT_TOPK 3~5개를 뽑은 경우
여러 epitope를 동시에 고려하는 경우
```

### BRIDGE

target-derived anchor와 linker/bridge 설계를 함께 고려하는 모드다.

추천 상황:

```text
두 hotspot 또는 두 motif 사이를 연결하는 peptide 설계
linker가 포함된 bridge peptide 설계
```

---

## 4. Preset Mode

### Fast Mode

빠른 테스트와 배포용 데모에 적합하다.

특징:

```text
Length 짧음
Population 작음
Generation 적음
Chemistry 대부분 OFF
ML OFF
Pseudo-docking OFF
```

### Paper Mode

논문용 후보 생성에 적합하다.

특징:

```text
Length 12–15
TopK 약 25
Bridge/linker 사용 가능
ML 기본 OFF
Hotspot 필요 시 ON
```

### Exploration Mode

화학적 다양성 탐색에 적합하다.

특징:

```text
D-form ON
Noncanonical ON
Linker ON
Tag/Label/Chemistry ON
Optional ML ON 가능
```

### Hotspot Only Mode

motif 없이 hotspot만 target bias로 사용하는 모드다.

핵심 설정:

```text
AUTO_HOTSPOT = ON
HOTSPOT_REPLACE_TARGETS = ON
HOTSPOT_LOCK_AS_MOTIF = OFF
MOTIF_LOCK = OFF
```

의미:

```text
hotspot은 TARGETS로 사용
hotspot은 motif처럼 강제 삽입되지 않음
peptide 생성은 유연하게 유지됨
```

추천 상황:

```text
target-derived bias만 주고 싶을 때
기능성 motif를 따로 넣고 싶지 않을 때
논문용으로 안전한 hotspot 기반 후보를 만들 때
```

---

## 5. Length 설정

### RANGE

`MinLen`과 `MaxLen` 사이에서 후보 길이를 생성한다.

추천:

```text
빠른 테스트: 10–12
논문 후보: 12–15
탐색 모드: 12–20
긴 linker 후보: 18–30
```

### FIX

`FixLen`으로 길이를 고정한다.

사용 상황:

```text
길이를 엄격히 비교하고 싶을 때
합성 길이를 고정하고 싶을 때
동일 길이 후보만 만들고 싶을 때
```

### LENGTH_COUNT_MODE

```text
TOKEN: linker/tag/chemical token을 하나의 단위로 계산
EXPANDED: surrogate 또는 expanded sequence 기준으로 계산
```

일반적으로는 `TOKEN`을 추천한다.

---

## 6. Chemistry 옵션

체크박스 의미:

```text
체크됨 = 해당 기능 사용
체크 안 됨 = 해당 기능 사용하지 않음
```

### D-form

D-amino acid token을 후보에 포함한다.

주의:

```text
표준 docking workflow에 바로 맞지 않을 수 있음
parameterization 필요 가능성 있음
```

### Non-natural

noncanonical residue를 포함한다.

주의:

```text
force field parameter 필요 가능성 있음
surrogate FASTA는 prescreening 용도
```

### Linker

linker token을 포함한다.

사용 상황:

```text
bridge peptide
motif 연결
epitope 간 연결
flexible spacer 설계
```

### Tag / Label / Base Chemistry

실험용 tag, label, chemical modification을 포함한다.

주의:

```text
구조 모델링 복잡도 증가
main docking 후보로는 비추천일 수 있음
```

---

## 7. Hotspot과 Motif 구분

반드시 구분해야 한다.

```text
HOTSPOT = 단백질 sequence/PDB에서 자동으로 추출된 target-derived reference
MOTIF   = 사용자가 peptide 안에 넣고 싶은 기능성 서열
```

즉:

```text
hotspot은 참고/bias
motif는 삽입/강제
```

Hotspot Only Mode에서는 hotspot을 TARGETS로만 쓰고 motif처럼 강제 삽입하지 않는다.

---

## 8. Motif / Constraint

이 엔진에서 motif는 target 결합 자체와 반드시 같은 뜻이 아니다.

```text
MOTIF = 내가 peptide 안에 반드시 넣고 싶은 기능성 서열
TARGET = 설계 bias 또는 target-derived reference
```

### Motif Lock

```text
ON  = motif 강제 포함
OFF = motif 강제 없음
```

### Motif Position

```text
FREE   = 기존 방식, 위치 자유
N_TERM = N-terminal 쪽에 배치
CENTER = 중앙 근처에 배치
C_TERM = C-terminal 쪽에 배치
```

### Motif Map 예시

```text
KLVFF:CENTER
HHHHHH:C_TERM
RGD:N_TERM
```

---

## 9. Auto Hotspot 기능

Auto Hotspot은 protein sequence 또는 PDB text에서 hotspot-like fragment를 자동으로 뽑아 TARGETS로 사용하는 기능이다.

중요:

```text
이 기능은 실제 binding hotspot을 증명하지 않는다.
target-specific design bias를 강화하는 optional preprocessing이다.
```

### Sequence mode

Protein sequence를 sliding window로 나누고 hydrophobicity, aromatic residue, charge balance 등을 이용해 fragment를 점수화한다.

추천 설정:

```text
HotSource: SEQUENCE
HotWin: 5–8
HotTopK: 3–5
Use as TARGETS: ON
Lock hotspots: OFF
```

### PDB mode

PDB text에서 CA atom neighbor count를 이용해 surface-exposure proxy를 계산한다.

중요 표현:

```text
SASA-like surface exposure proxy
```

정식 SASA 계산은 아니다.

추천 설정:

```text
HotSource: PDB
HotWin: 5–8
HotTopK: 3–5
MinExpose: 0.30–0.45
Use as TARGETS: ON
Lock hotspots: OFF 또는 선택적 ON
```

---

## 10. Hotspot과 Motif의 안전한 조합

### motif 없이 hotspot만 쓰고 싶을 때

```text
MOTIF_LOCK = OFF
LOCKED_MOTIFS = empty
AUTO_HOTSPOT = ON
HOTSPOT_REPLACE_TARGETS = ON
HOTSPOT_LOCK_AS_MOTIF = OFF
```

이 설정은 Hotspot Only Mode가 자동으로 적용한다.

### hotspot을 motif처럼 강제하고 싶을 때

```text
AUTO_HOTSPOT = ON
HOTSPOT_LOCK_AS_MOTIF = ON
```

이 경우 추출된 hotspot fragment가 peptide 안에 강제로 포함될 수 있다.

---

## 11. Docking 관련 설정

이 엔진은 docking을 직접 수행하지 않는다.

대신 다음을 수행한다.

```text
docking-ready 후보 분류
surrogate FASTA 생성
modeling manifest 생성
pseudo-docking input 준비
```

### Docking Stage

```text
OFF
FINAL_TOP_ONLY
EVERY_N_GENERATIONS
```

일반적으로 `FINAL_TOP_ONLY`를 추천한다.

### Docking Engine

```text
NONE
CUSTOM
ROSETTA
VINA
DIFFDOCK
```

이 설정은 실제 docking 실행이 아니라 route/계획 표시 성격이 강하다.

---

## 12. 결과 파일

### results_top.csv

최종 상위 후보 리스트.

### docking_ready_candidates.csv

docking-ready 기준으로 정리된 후보.

### extracted_hotspots.csv

Auto Hotspot을 켰을 때 생성된다.

포함 정보:

```text
motif
score
source
start/end
exposure
```

### hotspot_peptide_map

각 peptide가 추출 hotspot과 어떻게 연결되는지 보여준다.

예:

```text
KLVFF:YES|RGD:NO|WYYF:PARTIAL
```

### target_hotspot_sequences

target으로 사용된 hotspot sequence 목록이다.

### best_hotspot

가장 관련성이 높은 hotspot motif를 표시한다.

---

## 13. Colab 분석/그래프

`Colab_Analysis_Cell.py`를 실행하면 다음 figure가 생성된다.

```text
score_distribution.png
length_distribution.png
docking_readiness_category.png
hotspot_match_distribution.png
top_hotspots.png
analysis_results.zip
```

이 기능은 엔진 로직을 바꾸지 않고 결과 분석만 수행한다.

---

## 14. 추천 실험 구조

논문용 비교는 다음 3개 조건을 권장한다.

```text
1. Hotspot OFF
2. Hotspot Only Mode with SEQUENCE
3. Hotspot Only Mode with PDB
```

이 비교를 통해 hotspot-guided design bias가 후보 분포와 hotspot overlap에 어떤 영향을 주는지 볼 수 있다.

---

## 15. 해석 원칙

반드시 다음을 구분해야 한다.

```text
target-derived design bias ≠ binding proof
pseudo-docking input ≠ docking result
ML reranking ≠ experimental evidence
surface proxy ≠ formal SASA
```

안전한 논문 표현:

```text
The engine generates docking-ready peptide candidates and prepares structured inputs for downstream validation workflows.
```

또는:

```text
The optional hotspot module provides target-derived design bias using sequence-based or SASA-like surface-exposure proxy features.
```


---

## Hotspot 출력 확인

Auto hotspot을 켜면 결과에 target hotspot sequence가 명시적으로 출력된다.

확인할 컬럼/파일:

```text
target_hotspot_sequences
hotspot_source_sequence_used
hotspot_peptide_map
best_hotspot
hotspot_peptide_pairs.csv
```

Colab UI에서 `ProteinSeq` 칸이 비어 있어도, `Targets` 칸에 단백질 전체 sequence를 넣었다면 그 sequence를 hotspot 추출 source로 사용할 수 있도록 패치되어 있다.

즉 다음 둘 다 가능하다.

```text
방법 1: Hotspot/Position 탭의 ProteinSeq에 단백질 sequence 입력
방법 2: Basic/Length 탭의 Targets에 단백질 sequence 입력
```

추천은 방법 1이지만, 방법 2도 동작한다.


## RESIDUE length mode

Default length mode is now `RESIDUE`.

This means:

```text
FIX_LENGTH = amino-acid residue count
C-terminal NH2 = terminal modification, not an amino acid
```

Example:

```text
FIX_LENGTH = 12
USE_CTERM_NH2 = True
```

Output should contain 12 amino-acid residues plus optional `NH2`.

Additional output columns:

```text
residue_length
expanded_length
token_length_sum
```


## Final length and chemistry semantics

Default length mode is `TOKEN`.

```text
TOKEN   = amino-acid residues + selected chemical/linker/tag/label tokens
RESIDUE = amino-acid residues only
EXPANDED = expanded peptide-like length where available
```

`NH2` is treated as a C-terminal modification and is excluded from length counting.

Chemical, linker, label, and tag features are only introduced when the corresponding UI option is enabled. They are not hard-forced by default. The optional enrichment setting is a soft design bias, not a mandatory insertion rule.


## Terminal topology rules

Default final topology:

```text
chemical / tag / label = N-terminal only
linker = internal / middle only
NH2 = C-terminal modification
```

`Soft-enrich selected chem` is not a hard forcing mode. It only helps selected chemical/linker/tag/label options appear and remain in ranked candidates when those options are enabled.


## PDB file upload and hotspot output

Colab supports PDB hotspot extraction through a `.pdb` file upload widget in the `Hotspot/Position` tab.

When `Auto hotspot` is enabled, the top results include explicit target-hotspot mapping columns:

```text
binding_target_hotspot
peptide_to_target_hotspot
all_target_hotspots_used
hotspot_status
target_hotspot_sequences
hotspot_peptide_map
best_hotspot
```

If `HOTSPOT_SOURCE = PDB` but no PDB file/text is provided, the engine falls back to sequence-based hotspot extraction when a protein sequence is available.


## Hotspot debug mode

If `AUTO_HOTSPOT` is ON but no hotspots are extracted, enable `Hotspot debug fallback`.

This produces diagnostic hotspot windows and saves:

```text
hotspot_debug_visualization.csv
hotspot_peptide_pairs.csv
```

These files show the hotspot sequence, source, start/end residue positions, and peptide-hotspot relationship.

## Long-target chemistry balance

For long protein sequence targets, target/hotspot scoring may dominate and chemical/label features may disappear from top candidates. The engine includes long-target chemistry balancing so selected chemical/linker/tag/label options are less likely to be lost during ranking.

This is not hard forcing.


## Hotspot region output

Top results include the target-derived hotspot region used as design reference:

```text
binding_target_hotspot_sequence
binding_target_hotspot_start
binding_target_hotspot_end
binding_target_hotspot_range
binding_target_hotspot_chain
binding_target_hotspot_source
```

Example:

```text
binding_target_hotspot_sequence = ACDEFG
binding_target_hotspot_range = A:125-132
```

This is a design-referenced hotspot region, not proof of physical binding.
