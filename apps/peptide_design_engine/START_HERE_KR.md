# Peptide Design Engine — Clean Installer + Conda Research Package

이 패키지는 두 가지 실행 방식을 모두 포함합니다.

## 1. 일반 Python/EXE-style 실행

처음 실행:

```bat
INSTALL_AND_RUN.bat
```

이 파일은 다음을 한 번에 처리합니다.

```text
Python 3 확인
requirements 설치
바탕화면 바로가기 생성 여부 질문
GUI 실행
```

다음부터는:

```bat
RUN_GUI.bat
```

또는 바탕화면 바로가기 사용.

## 2. Conda 연구용 실행

Anaconda Prompt에서 실행 권장:

```bat
INSTALL_AND_RUN_CONDA.bat
```

또는 단계별:

```bat
SETUP_CONDA_ENV.bat
RUN_GUI_CONDA.bat
```

Conda 판은 연구 확장, ML 재학습, AF3/PRODIGY 데이터 누적, 패키지 추가에 적합합니다.

## 3. 어떤 걸 쓰면 되나?

```text
시연/가벼운 실행/배포 흐름 → INSTALL_AND_RUN.bat 또는 RUN_GUI.bat
연구/개발/ML/AF3/PRODIGY 확장 → INSTALL_AND_RUN_CONDA.bat 또는 RUN_GUI_CONDA.bat
```

둘 다 있는 것이 가장 좋습니다.

## 4. 주요 폴더 구조

```text
Python/          핵심 엔진, GUI, CLI, ML, parser
Colab/           Colab용 코드
data/            templates, sample external outputs
example_results/ 예시 결과
build/           EXE build scripts
docs/            문서/패치 노트
Analysis/        분석 스크립트
```

## 5. 바탕화면 아이콘

`INSTALL_AND_RUN.bat` 또는 `INSTALL_AND_RUN_CONDA.bat` 실행 중 다음 질문이 나옵니다.

```text
Create a desktop shortcut?
```

Y를 누르면 바탕화면에 바로가기가 생성됩니다.

## 6. EXE 빌드

일반 Python 환경:

```bat
build\build_desktop_gui_exe.bat
```

Conda 환경:

```bat
build\build_desktop_gui_exe_conda.bat
```
