# Dependency install fix

## 발생 오류

```text
ModuleNotFoundError: No module named 'numpy'
```

이 오류는 Python 3는 잡혔지만 `numpy`, `pandas` 등 requirements 패키지가 아직 설치되지 않았을 때 발생합니다.

## 수정 내용

- `run_desktop_gui.bat`가 실행 전에 핵심 패키지 설치 여부를 확인합니다.
- 없으면 자동으로 다음 명령을 실행합니다.

```bat
py -3 -m pip install -r Python\requirements.txt
```

- 수동 설치용 `install_requirements.bat`도 추가했습니다.

## 실행 순서

1. `install_requirements.bat` 실행 또는 바로 `run_desktop_gui.bat` 실행
2. 첫 실행 때 패키지 설치가 진행될 수 있음
3. 설치 완료 후 GUI 자동 실행

## 수동 명령

```bat
py -3 -m pip install -r Python\requirements.txt
py -3 Python\desktop_gui.py
```
