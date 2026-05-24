# Python 3 실행 오류 수정 안내

## 증상

```text
File "Python\desktop_gui.py", line 60
    def parse_targets(text: str) -> List[List[str]]:
                          ^
SyntaxError: invalid syntax
```

이 오류는 코드가 Python 2로 실행될 때 발생합니다. `text: str`, `List[List[str]]` 같은 type hint 문법은 Python 3 전용입니다.

## 수정 내용

- `run_desktop_gui.bat`가 이제 `py -3`를 먼저 사용합니다.
- Python 3.8 이상인지 확인한 뒤 실행합니다.
- `check_python_version.bat`를 추가했습니다.
- EXE build script도 `py -3 -m PyInstaller`를 사용하도록 수정했습니다.

## 실행 방법

1. 먼저 버전 확인:

```bat
check_python_version.bat
```

2. GUI 실행:

```bat
run_desktop_gui.bat
```

3. 직접 실행:

```bat
py -3 Python\desktop_gui.py
```

## Python 3가 없다면

Python 3.10 또는 3.11 설치를 권장합니다. 설치할 때 `Add python.exe to PATH`를 체크하세요.
