# EXE 배포용 안내

이번 패키지는 **최종 배포용 Windows GUI EXE + 설치 파일(Installer)** 을 만들기 위한 버전입니다.

## 목표

- 사용자는 **설치 파일 1개만 실행**하면 됨
- 설치 후 시작 메뉴 / 바탕화면 아이콘으로 실행
- 프로그램 실행 시 **Python 콘솔 창이 뜨지 않음**
- 방금 만든 **Pd 모노그램 아이콘** 포함

## 포함된 핵심 파일

```text
assets/PeptideDesignEngine_Icon.ico
assets/PeptideDesignEngine_Icon.png

build/BUILD_EXE_PY311.bat
build/BUILD_INSTALLER.bat
build/BUILD_ALL_RELEASE.bat
build/PeptideDesignEngine_Setup.iss
```

## 배포 파일 만드는 순서

### 준비물
1. Python 3.11.9 설치
2. Inno Setup 6 설치

### 실행
가장 간단한 방법:

```bat
build\BUILD_ALL_RELEASE.bat
```

이 스크립트가 순서대로:

```text
1. Python 3.11 build venv 생성
2. requirements + pyinstaller 설치
3. PeptideDesignEngine.exe 생성
4. Inno Setup으로 설치 파일 생성
```

## 결과물

최종 사용자에게 배포할 파일:

```text
InstallerOutput\PeptideDesignEngine_Setup.exe
```

사용자는 이 설치 파일 **하나만 실행**하면 된다.

## 콘솔 창 숨김

PyInstaller는 다음 옵션으로 빌드된다.

```text
--windowed
```

그래서 최종 GUI EXE 실행 시 Python/console 창이 보이지 않는다.

## 아이콘

이번 버전에는 `P`와 `d`를 조합한 biotech/tech 스타일의 아이콘이 포함되어 있다.

- EXE 아이콘
- 설치 파일 아이콘
- 시작 메뉴 아이콘
- 바탕화면 바로가기 아이콘

모두 동일한 아이콘을 사용하도록 설정했다.


## 아이콘 투명 배경

최종 아이콘은 원형 로고 바깥 배경이 투명 처리된 PNG/ICO를 사용합니다.
