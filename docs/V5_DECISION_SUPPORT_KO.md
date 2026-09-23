# SPPS Planner V5.0.0 — Evidence-Driven Decision Support

## 목적

V5.0.0은 V4.0.0의 검증된 Planner 계산을 유지하면서, 실제 합성 기록을 **추천 근거와 검토 자료**로 연결한다. V5 기능은 Generate/Apply Change 계산을 대체하지 않으며, 기록에 없는 시약·cocktail·범주형 조건을 만들어내지 않는다.

## 근거 우선순위

1. 반복된 동일/매우 유사 실험의 성공 historical consensus
2. exact bottle-level building block / exact sequence / exact product evidence
3. 충분히 반복된 category consensus
4. 관측 범위 안에서만 허용되는 bounded interpolation
5. chemistry/risk reference
6. 근거 부족 시 `INSUFFICIENT EVIDENCE`

실제 historical condition이 존재하면 generic chemistry rule이 그 기록을 임의로 바꾸지 않는다.

## V5 기능

### Sequence Difficulty Map

현재 sequence를 residue 단위로 분석해 steric/beta-branched, Aspartimide-prone motif, hydrophobic cluster, Cys, Met/Trp 등 검토 항목을 표시한다. 점수는 **deterministic review score**이며 실패 확률이 아니다. 자동 Apply하지 않는다.

### Stage Risk Advisor

Loading / Coupling / Cleavage를 분리해 다음을 보여준다.

- Loading: resin + C-terminal building block의 exact historical evidence 존재 여부
- Coupling: 기존 transparent risk rules + 동일 sequence의 recorded coupling outcomes
- Cleavage: Cys/oxidation review, historical cleavage condition match, material-usage unit review 상태

Risk level은 triage용이며 biochemical failure probability가 아니다.

### Similar Historical Experiments

현재 sequence와 page-local STD sequence history를 canonical token 기준으로 비교해 유사 기록을 보여준다. 연결된 verified/parsed outcomes가 있으면 yield/purity/result를 같이 표시한다. 유사 기록은 근거 탐색용이며 자동 조건 생성에 쓰지 않는다.

### Outcome-aware data

Condition과 Outcome을 분리 저장한다.

- stage
- product / sequence
- success/partial/fail 또는 recorded result
- yield / purity
- doubling required
- observation
- source provenance

Coupling 결과는 active Work Item review와 Experimental DB에 함께 기록된다.

### Cleavage Amount / Workup Evidence

원재료 사용 기록에서 TFA / Water / TIS / Ether 실제 사용량을 별도 저장한다.

- 단위가 명확한 값만 mL로 정규화
- 숫자만 있고 단위가 없는 값은 raw value 보존 + `NEEDS UNIT REVIEW`
- Ether는 cleavage cocktail이 아니라 workup/precipitation evidence로 분리
- exact scale이 있으면 exact historical amount 사용
- 반복된 동일 composition의 관측 scale 범위 안에서만 bounded interpolation 허용
- 관측 scale 밖 extrapolation 금지

### Explicit Loading Model Registry

Loading model은 Advisor를 열었다고 자동 재학습하지 않는다.

- `Rebuild Loading Model`: Verified loading records가 충분할 때만 명시적으로 학습
- cross-validated MAE와 training count 저장
- rebuild마다 별도 model version 보존
- `Rollback Loading Model`: 이전 저장 model을 명시적으로 재활성화
- model prediction은 advisory only
- Apply는 여전히 real historical condition이 있어야 가능

## Public / Private

공통 실행 코드는 동일하다. 차이는 `build_profile.py`와 bundled data/policy뿐이다.

- Public: empty experimental seed, Public 전용 runtime directory
- Private: 내부 Loading/Cleavage/Sequence/Material Usage seed, Private 전용 runtime directory

두 runtime DB는 공유하지 않는다.

## Data provenance

Sequence history는 계산 파일의 **페이지별 Check table STD**를 기준으로 보존한다. 같은 제품이 여러 날짜에 존재해도 임의로 하나의 sequence로 합치지 않는다. source file / sheet / cell locator를 함께 저장한다.

Raw value와 canonical lookup key는 함께 보존한다. 대소문자·공백·일부 제품명 부가표기 차이는 lookup에서 정규화하지만 원본 데이터는 수정하지 않는다.

## 안전 원칙

- monkey patch / runtime function replacement 금지
- placeholder/stub/dummy implementation 금지
- historical record에 없는 reagent를 history로 생성 금지
- 서로 다른 experiment의 cocktail component를 합성해 새 조건 생성 금지
- unresolved unit 추측 금지
- model output 자동 Apply 금지
- 새 record 유입 시 자동 online retraining 금지
- V4 Planner core 기능 삭제/단순화 금지


### V5.0.0 final workup safety rules
- Cleavage 조건, 현재 scale 사용량, 침전/workup을 서로 분리해 표시한다.
- Ethyl Ether와 n-Hexane은 cleavage cocktail 성분이 아니라 별도 workup solvent로 취급한다.
- 여러 제품을 합산한 aggregate 원재료 기록은 참고자료로만 유지하고 자동 scale 계산에서는 제외한다.
- 단위가 없는 사용량은 원본을 보존하고 NEEDS UNIT REVIEW로 남기며 mL/L를 추측하지 않는다.
- current-scale cocktail 총량은 단일 제품의 실제 사용량 또는 관측 scale 범위 내부의 반복 기록에서만 계산한다.


## Synthesis Issue Log

합성 중 실제 문제를 `Stage → Issue type → Severity → Observation → Action → Resolution` 구조로 기록합니다. Product/sequence/scale은 현재 Planner에서 가능한 범위에서 자동으로 채워집니다. Issue record는 Risk & Evidence의 historical evidence로 다시 연결되지만, 그 자체가 자동으로 coupling/cleavage 조건을 변경하거나 실패로 판정하지는 않습니다.
