# GUI Selectable Chemistry Patch

## 추가된 기능

`2. Chemistry / Constraints` 탭에서 다음 세부 항목을 직접 선택할 수 있습니다.

- Tags / affinity or epitope handles (`TAG_TYPES`)
- Linkers / spacers / conjugation handles (`LINKER_TYPES`)
- Linker behavior (`LINKER_MODE`, `FIX_LINKER_TYPE`, `MAX_LINKERS`)
- Labels / fluorophores / biotin / chelators (`LABEL_TYPES`)
- Non-natural residues (`NON_NAT_TYPES`)
- N-terminal chemicals / base chemistry caps (`BASE_CHEM_TYPES`)

각 선택 영역에는 `All` / `None` 버튼이 있습니다.

## 실제 CONFIG 반영

GUI에서 선택한 값은 실행 시 다음 CONFIG key로 들어갑니다.

```python
TAG_TYPES
LINKER_TYPES
LINKER_MODE
FIX_LINKER_TYPE
MAX_LINKERS
LABEL_TYPES
BASE_CHEM_TYPES
NON_NAT_TYPES
```

또한 `peptide_engine.py`의 `build_pool()`을 수정하여 `USE_NON_NAT=True`일 때 전체 non-natural library가 아니라 GUI에서 선택된 `NON_NAT_TYPES`만 후보 생성 pool에 들어가도록 했습니다.

## Use base chemistry / N-terminal chemicals 의미

이 기능은 일반 아미노산 치환이 아니라 펩타이드의 말단, 특히 N-terminus 쪽에 붙는 cap/modification/conjugation token을 사용할지 정하는 옵션입니다.

예시:

- Ac: acetylation
- Pal: palmitoyl
- Myr: myristoyl
- Chol: cholesterol-like hydrophobic modification
- BiotinCap: N-terminal biotin-like cap
- Azide / Alkyne / DBCO / TCO / Tetrazine: click chemistry or conjugation handle
- Succinyl / Maleimide: functional group for conjugation

즉 `non-natural residue`는 서열 내부 residue 후보이고, `N-terminal chemicals`는 펩타이드 N말단에 붙는 modification/cap 후보로 취급하는 것이 핵심 차이입니다.

## 보존 사항

- 기존 Advanced JSON Override 유지
- 기존 Colab/Python/ML parser 기능 유지
- 기존 데이터/문서 유지
- GUI 선택값보다 Advanced JSON Override가 나중에 적용되므로, 고급 사용자는 여전히 직접 CONFIG를 덮어쓸 수 있음
