# SPPS Planner V8.0.0 — Windows 빌드 안내

배포 ZIP은 **소스 패키지**이며 EXE 또는 Installer 완성품을 포함하지 않습니다. Windows 10/11 x64에서 전체 ZIP을 압축 해제한 후 루트의 **`INSTALL_BUILD_TOOLS_AND_BUILD.bat`**을 실행하세요.

## 단일 BAT 사용법

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

명령행에서 자동화할 때:

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat --no-pause
```

스크립트는 다음 순서로 진행합니다.

1. Python 3.11/3.12 **64비트** 확인. 없다면 `winget`을 통해 Python 3.12 설치 시도.
2. `requirements.txt`와 `requirements-dev.txt` 의존성 설치.
3. Inno Setup 6/7 (`ISCC.exe`) 탐색. 없다면 `winget` 설치 시도.
4. Python 문법 검사, `tools/verify_windows_release.py` 정적 검사, 소스 self-test.
5. PyInstaller로 `dist\SPPS_Planner\SPPS_Planner.exe` 빌드 및 구조 검사.
6. 생성된 EXE의 `--self-test`와 self-test 보고서 검증.
7. Inno Setup을 통해 `installer\output\SPPS_Planner_Setup_V8.0.0.exe` 생성.
8. EXE/Installer 파일 검사.

`winget`이 없거나 설치 후 실행 파일 검색에 실패하면 오류를 출력하고 종료합니다. 필요한 프로그램을 수동으로 설치하고 다시 실행해야 할 수 있습니다. 인터넷, 해당 도구 설치 권한 및 보안 정책에 영향을 받습니다.

**주의:** 이 BAT은 *설치 프로그램을 만드는 빌드 도구*이며 SPPS Planner를 PC에 설치하지 않습니다. Installer가 정상 작동하는지는 실제 Windows에서 설치·업그레이드·제거·GUI 동작을 직접 확인해야 합니다. 위 단계가 자동 테스트로 모두 완료되더라도 실험 SOP나 GUI 사용성을 검증한 것은 아닙니다.

## 소스 실행 및 테스트

```bat
python -m pip install -r requirements.txt -r requirements-dev.txt
python main_launcher.py
python -m pytest -q
python tools\verify_windows_release.py
```

## Windows 배포 체크리스트 (미실행 환경에서는 미검증)

- 앱 실행 및 제목·아이콘·Project Manager·Step 1/2·Batch Manager 확인
- Auto Plan → Generate → Plan/Materials/Cleavage/Workup 확인
- 휠/드래그 스크롤과 화면 하단 위젯 높이 확인
- JSON 저장·로드·외부 변경·복구·한글 경로 확인
- EXE 실행 및 Installer 설치·업그레이드·제거·재설치, 사용자 데이터 보존 확인
