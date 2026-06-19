# Peptide Design Engine — Final Branded Installer Package

이 버전은 사용자가 일반 프로그램처럼 설치해서 사용할 수 있도록 만드는 최종 배포용 패키지입니다.

## 최종 아이콘

사용자가 선택한 **글로시 Green Pd 원형 로고**를 최종 아이콘으로 고정했습니다.

포함 파일:

```text
assets/PeptideDesignEngine_Icon.png
assets/PeptideDesignEngine_Icon.ico
assets/PeptideDesignEngine_Splash.png
```

## 브랜딩 기본값

```text
App Name: Peptide Design Engine
Version: 2.1.0
Publisher: Sanghun Woo
GitHub URL: https://github.com/SanghunWoo-23/peptide-design-engine
```

## 적용된 항목

- EXE 아이콘
- 설치 파일 아이콘
- 시작 메뉴 아이콘
- 바탕화면 바로가기 아이콘
- 프로그램 내부 상단 로고
- Splash screen
- 콘솔창 숨김 실행 설정

## 설치 파일 만들기

Windows에서 다음을 설치한 뒤:

```text
Python 3.11.9
Inno Setup 6
```

압축 푼 폴더에서 실행:

```bat
BUILD_DISTRIBUTION_ONECLICK.bat
```

또는:

```bat
build\BUILD_ALL_RELEASE.bat
```

## 최종 배포 파일

빌드가 완료되면 이 파일이 생성됩니다.

```text
InstallerOutput\PeptideDesignEngine_Setup.exe
```

최종 사용자는 이 설치 파일 하나만 실행하면 됩니다.

## 콘솔창 숨김

PyInstaller 빌드 옵션에 다음이 포함되어 있습니다.

```text
--windowed
```

따라서 설치 후 실행되는 GUI 프로그램은 Python 콘솔창 없이 실행됩니다.

## Splash screen

앱 실행 시 글로시 Pd 로고를 사용한 splash screen이 짧게 표시되고, 이후 메인 GUI가 열립니다.


## 아이콘 투명 배경

최종 아이콘은 원형 로고 바깥 배경이 투명 처리된 PNG/ICO를 사용합니다.
