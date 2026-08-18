# SPPS Planner V4.0.0

Pepforge V3.0.0에 통합된 SPPS Planner **V4.0.0** 애플리케이션 엔진과 필수 데이터입니다.

## 주요 동작

- 시작 시 저장된 item이 전혀 없으면 빈 peptide item 1개를 표시합니다.
- `CTC(합성기)`는 Sequence에 적은 residue 전체를 합성 대상으로 사용합니다. 삭제된 `CTC(합성용)` 표기는 이전 저장 데이터를 열 때만 `CTC(합성기)`로 변환됩니다.
  - 별도 loading AA/DIEA 행은 만들지 않습니다.
  - `AEKIRKELEKQ`를 입력하면 Plan은 Q부터 시작하며 AA coupling 행은 11개입니다.
- Cleavage Cocktail preset 선택 목록과 결과의 preset 이름은 resin명이 아니라 실제 조성으로 표시됩니다.
  - 예: `TFA=95; TIS=2.5; Water=2.5`
- 통합 SPPS 모듈은 `V4.0.0`으로 표시되며, 상위 Pepforge 공개 버전은 `V3.0.0`을 유지합니다.
- Windows build 경로와 Installer 출력 이름 불일치를 수정했습니다.

## 실행

```bat
python main_launcher.py
```

## Windows EXE 생성

```bat
BUILD_EXE_ONLY.bat
```

결과:

```text
dist\SPPS_Planner\SPPS_Planner.exe
```

## Windows Installer 생성

1. Python 3.11 또는 3.12 64-bit를 설치합니다.
2. Inno Setup 6 또는 7을 설치합니다.
3. 압축을 완전히 푼 폴더에서 아래 파일을 실행합니다.

```bat
BUILD_INSTALLER.bat
```

결과:

```text
installer\output\Pepforge_Setup_V3.0.0.exe
```

`INSTALL_BUILD_TOOLS_AND_BUILD.bat`도 동일한 Installer 빌드 파일입니다.
