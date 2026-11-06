# 구형 SPPS 내장 엔진 (호환성 유지)

**Pepforge 본체 버전: V6.0.0.** 최신 기본 합성 계획 모듈은 `vendor/spps_planner_v8/`에 포함된 **SPPS Planner V8.0.0 Public**입니다.

`apps/spps_planner_app/`는 과거 프로젝트 파일·모듈 참조 및 데이터 호환성 때문에 보존한 하위 모듈로, V6 설치기의 기준이 아닙니다. 기존 V5 설치 명령을 사용하지 마세요.

Pepforge 최상위 디렉터리에서 실행:

```bat
python main_launcher.py --tool spps
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

SPPS V8 단독 EXE를 직접 빌드하는 BAT는 `vendor/spps_planner_v8/` 아래에 남겨 별도 빌드·검증용으로만 관리합니다. 합성 계획 결과는 실험 수율·순도·반응 완결성을 보증하지 않습니다.
