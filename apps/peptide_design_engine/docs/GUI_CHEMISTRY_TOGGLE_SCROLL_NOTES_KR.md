# GUI Chemistry Toggle + Mouse Wheel Scroll Patch

## 추가/수정 내용

### 1. Feature toggle 기반 세부 라이브러리 표시

`2. Chemistry / Constraints` 탭에서 다음 항목을 체크했을 때만 아래 세부 선택 박스가 표시됩니다.

- Use non-natural residues → `NON_NAT_TYPES` 표시
- Use linker system → `LINKER_TYPES` + Linker behavior 표시
- Use tag system → `TAG_TYPES` 표시
- Use base chemistry / N-terminal chemicals → `BASE_CHEM_TYPES` + 설명 표시
- Use label system → `LABEL_TYPES` 표시

체크를 해제하면 해당 영역은 `grid_remove()`로 접힙니다.

### 2. 마우스 휠 스크롤

스크롤 가능한 탭 영역에 마우스를 올린 상태에서 마우스 휠을 움직이면 위/아래로 스크롤됩니다.

지원:
- Windows/macOS: `<MouseWheel>`
- Linux 계열: `<Button-4>`, `<Button-5>`

### 3. 유지 사항

- 기존 Advanced JSON Override 유지
- 기존 Data/ML, AF3/PRODIGY parser 유지
- 기존 selectable chemistry CONFIG 반영 유지
- 기존 Colab/Python 코드 유지
