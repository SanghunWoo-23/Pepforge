# Expert Override / Advanced CONFIG 수정 안내

## 문제

기존 Advanced CONFIG 탭은 기본값으로 chemistry 관련 key만 들어가 있었습니다.

예:

```json
{
  "TAG_TYPES": [...],
  "BASE_CHEM_TYPES": [...],
  "LABEL_TYPES": [...],
  "LINKER_TYPES": [...],
  "NON_NAT_TYPES": [...],
  "LINKER_MODE": "MIX",
  "FIX_LINKER_TYPE": "PEG4",
  "MAX_LINKERS": 2
}
```

이 때문에 사용자가 보기에는 Advanced CONFIG가 전체 CONFIG가 아니라 chemistry 목록만 있는 것처럼 보였습니다.

## 수정

탭 이름을 다음처럼 변경했습니다.

```text
Advanced CONFIG → Expert Override
```

기본 내용은 이제 다음처럼 비워져 있습니다.

```json
{}
```

즉, 일반 GUI 사용자는 이 칸을 건드리지 않아도 됩니다.

## 추가 버튼

- `Show FULL current CONFIG`
  - 현재 GUI 값까지 반영된 전체 CONFIG를 editor에 표시합니다.
  - 검사/저장/복사용입니다.

- `Insert chemistry override example`
  - tag/linker/label/non-natural/N-terminal chemistry 예시 override를 삽입합니다.

- `Insert constraints/scoring example`
  - MAX_D_RATIO, MAX_CYS, docking/hotspot/scoring weight 예시 override를 삽입합니다.

- `Validate JSON`
  - JSON 형식이 맞는지 확인합니다.

- `Reset to {}`
  - override를 비웁니다.

## 핵심 설명

Expert Override는 새 기능이나 데이터를 만드는 곳이 아닙니다.

```text
데이터 없음 → 못 살림
엔진 로직 없음 → 못 살림
구현되지 않은 key → 효과 없음
```

이 탭은 이미 `peptide_engine.py`에 구현된 CONFIG key를 마지막에 덮어쓰는 연구용 안전장치입니다.

정상적인 사용은 GUI 탭에서 하고, Expert Override는 연구/디버깅/일괄 실험 조건 변경용으로만 쓰는 것을 권장합니다.
