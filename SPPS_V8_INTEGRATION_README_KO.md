# Pepforge V6.0.0 — SPPS Planner V8.0.0 연동

- Pepforge 메인 런처에서 **SPPS Planner**를 선택하고 **Open SPPS Planner**를 클릭합니다.
- PDE와 PSB처럼 **독립된 데스크톱 창**이 열립니다. Windows SetParent 방식의 창 임베딩은 사용하지 않습니다.
- 원본 V8 Project Manager, Batch, Materials, Checklist, Cleavage, Recommendations 기능과 계산 엔진을 보존합니다. 제외된 중복 단축 버튼은 복원하지 않습니다.
- 소스 실행: `python -m pip install -r vendor/spps_planner_v8/requirements.txt`, `python main_launcher.py --tool spps`.
- Windows 빌드: `INSTALL_BUILD_TOOLS_AND_BUILD.bat`가 별도 `SPPS_Planner/SPPS_Planner.exe`를 빌드·포함해야 하며, EXE만 단독 복사해서는 안 됩니다.
- 실행 실패 시 Pepforge 런처의 `spps_v8_launch.log`를 확인합니다.
- 버전: **Pepforge V6.0.0**, 원본 **SPPS Planner V8.0.0**. 서로 독립적인 버전입니다.
- PUBLIC에는 PRIVATE 실험 이력·개인 정보·seed 데이터를 넣지 않습니다.
- SPPS Planner는 합성 계획 보조 프로그램이며 수율·순도·반응 성공을 보장하지 않습니다.

## 2026-10-29 최신 SPPS V8 UI 반영

- 제공된 **SPPS Planner V8.0.0 Treeview Style Fixed** 에디션을 Public/Private 각각 그대로 반영했습니다.
- Recommendations 창의 전용 `SPPS.History.Treeview` / `SPPS.History.Treeview.Heading` 스타일로 변경되어 Plan 열 제목 굵기가 유지됩니다.
- 기능이나 화학 계산 엔진은 변경하지 않았으며, 원본 V8 GUI는 Pepforge에서 별도의 정상 창으로 실행됩니다.
- GUI 테스트: `cd vendor/spps_planner_v8` 이후 `python -m pytest -q tests/test_v8_recommendations_style_isolation.py` (Tk 화면 환경 필요).
