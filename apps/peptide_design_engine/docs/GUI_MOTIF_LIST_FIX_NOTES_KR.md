# GUI motif/list 초기화 오류 수정

## 발생 오류

```text
TypeError: sequence item 0: expected str instance, list found
```

## 원인

`peptide_engine.CONFIG` 내부의 `TARGETS`, `LOCKED_MOTIFS` 값은 문자열 리스트가 아니라 다음처럼 residue list 형태일 수 있습니다.

```python
TARGETS = [list("DELIKFVRWA"), list("YYERWFCAA")]
LOCKED_MOTIFS = [list("RGD")]
```

기존 GUI는 이를 그대로 `", ".join(...)`으로 표시하려고 해서 list가 들어오면 오류가 발생했습니다.

## 수정

`desktop_gui.py`에 GUI 표시용 변환 함수를 추가했습니다.

- `seq_token_to_text()`
- `list_to_gui_text()`

이제 문자열, 리스트, 중첩 리스트 형태를 모두 안전하게 GUI 문자열로 변환합니다.

## 영향

- 기존 엔진 기능/데이터 변경 없음
- GUI 초기화 안정성만 개선
- `TARGETS`, `LOCKED_MOTIFS` 모두 안전 표시
