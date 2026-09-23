# SPPS Planner V4.0.0 — Experimental Data / ML 설계

V4.0.0은 V3.0.0의 Plan, Materials, Checklist, Total Materials, Apply Change, Project/Session, Batch, parser 및 catalog 계산 경로를 대체하지 않는다. 새 기능은 실제 실험 데이터를 별도 SQLite knowledge base에 보존하고, 기존 Planner 입력을 근거 데이터와 비교하여 조언하는 독립 계층이다.

## 데이터 상태

- `parsed`: Excel/CSV 또는 전사 데이터에서 읽었으나 운영자 검토 전. Advisor 근거에는 사용할 수 있지만 confidence를 낮춘다.
- `verified`: 운영자가 확인한 실험값. supervised ML 학습에 사용할 수 있다.
- `incomplete`: 조건/결과가 부족한 기록. 보존하지만 학습 target으로 사용하지 않는다.
- `excluded`: 잘못된 기록, 중복, 측정 오류 등으로 제외한 기록. 삭제하지 않는다.

원문(`raw_note`, `raw_observation`, `raw_filter_note`)과 표준화 필드를 동시에 보존한다. 자동 parsing 결과가 원문을 덮어쓰지 않는다.

## Loading History

핵심 입력은 resin, bottle-level amino-acid name, stereochemistry/protecting group, loading AA eq, base/base eq, coupling reagent/additive, reaction time, capping, sample resin mass 및 Abs이다. 결과값은 measured loading rate (mmol/g)이다.

V4 Loading Advisor는 먼저 유사 실험을 보여준다. Verified loading 데이터가 12건 이상이고 measured loading target의 변이가 충분할 때 Random Forest regression을 학습해 similarity estimate와 함께 advisory evidence로 사용한다. Apply 조건 자체는 실제 exact historical record에서만 가져온다. 작은 데이터에서 과도한 정밀도를 피하기 위해 결과에는 observed range, evidence count, exact resin+AA match count, confidence 및 extrapolation warning을 함께 표시한다.

## Cleavage / Precipitation History

지원되는 cleavage report 형식을 읽어 product, scale, TFA/TIS/H2O, cleavage eq/time, ether, filter condition, crude 및 원문 특이사항을 저장할 수 있다. 자유 메모는 제한된 deterministic keyword parser로 precipitation/separation/concentration/TIS 관련 flag를 만들며 원문은 항상 보존한다.

Cleavage Advisor는 현재 sequence와 page-local STD sequence history를 우선 연결하고, 재현 가능한 완전 historical cocktail이 있으면 그 실제 condition을 우선한다. Generic chemistry rule은 historical record를 거부하거나 부족한 component를 만들어내는 필터로 쓰지 않으며, history가 없을 때 참고값으로만 제시하고 Apply를 비활성화한다. causal optimum이나 성공확률은 단정하지 않는다.

## Sequence History / Excel/ZIP import

- 안정적인 Cleavage Report 형식: 구조화해서 `cleavage_records`로 import.
- V4 loading CSV schema: `loading_records`로 import.
- 월별 계산 workbook의 각 sheet에서 `Check table`이 확인되면 그 페이지의 STD product/sequence를 `synthesis_sequence_records`에 저장한다. 다른 날짜의 동일 product를 강제로 하나의 canonical sequence로 합치지 않으며, 각 페이지의 STD observation과 source file/sheet/cell 위치를 그대로 보존한다.
- 지원되는 `Check table` 또는 Cleavage Report 구조가 없는 workbook은 source registry에만 등록하고 임의의 sequence/실험 행을 추측하지 않는다.
- ZIP은 내부의 xlsx/xlsm/csv를 순회하며 Office 임시파일(`~$`)은 제외하고, archive 내부 원본 경로를 provenance로 보존한다.

## 사용자 제공 seed data

`apps/spps_planner_app/data/experimental_seed/`에는 공개판에서 실제 실험 기록을 번들하지 않는다. 사용자는 **Record Lab Data** 또는 **Import Lab Data**로 권한이 있는 자신의 데이터를 추가한다. imported record는 검토 상태를 명시적으로 관리하며, 자동으로 `verified`로 승격하지 않는다.

## UI

`Data / ML > Experimental Data / ML Advisors...`에서 다음을 제공한다.

- Loading History / Cleavage History / Sequence History 조회
- Excel / ZIP / CSV import 전 `Import Preview / Audit`으로 실제 parser 결과와 provenance 확인
- Parsed → Verified / Excluded 상태 변경 및 Sequence History의 동일 product page observation 일괄 검증
- 선택 record 수정
- Loading Advisor
- Cleavage Advisor
- Data Health: canonical-key 누락, sequence↔cleavage linkage, 반복 loading group, EDT explicit record 수, retrospective consistency 지표

Chemistry-rule fallback은 historical/ML evidence로 취급하지 않으며 자동 Apply를 허용하지 않는다. 실제로 기록된 완전한 historical condition은 generic chemistry preset보다 우선한다. Advisor의 변경은 사용자가 명시적으로 Apply한 경우에만 Planner에 반영되며 기존 Generate / Apply Change의 역할은 그대로 유지한다.

## Canonical lookup keys

Raw product/sequence/resin/building-block 값은 그대로 보존하면서 별도의 `product_key`, `sequence_key`, `resin_key`, `amino_acid_key`를 저장한다. 기존 SQLite DB도 시작 시 자동 backfill되며 원문을 수정하지 않는다. Sequence key는 대소문자를 무시하지만 explicit D-form은 보존한다. 이 key는 조회 안정성을 위한 것이며 서로 다른 제품이나 stereochemistry를 임의로 합치지 않는다.

## Golden regression

Private build는 실제 bundled historical seed를 대상으로 대표 sequence/Loading/Cleavage 결과를 고정 검증한다. Public build는 private product/sequence를 포함하지 않고 synthetic regression만 사용한다. Golden regression은 generic chemistry rule이 실제 historical cocktail을 덮어쓰거나, case 차이 때문에 history lookup이 끊기는 회귀를 막기 위한 계약 테스트다.
