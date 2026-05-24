# Installer build notes

## 왜 이 구조인가?

최종 사용자는 Python, requirements, batch 파일 등을 볼 필요가 없습니다.

그래서 배포용 흐름은 다음과 같이 분리했습니다.

```text
개발자/배포자:
  Python 3.11 + PyInstaller + Inno Setup
  -> 설치 파일 1개 생성

최종 사용자:
  PeptideDesignEngine_Setup.exe 실행
  -> 설치 완료
  -> 시작 메뉴 / 바탕화면 아이콘으로 GUI 실행
```

## 최종 사용자 경험

- 설치 파일 1개 실행
- 설치 위치 선택 가능
- 시작 메뉴 등록
- 바탕화면 아이콘 선택 가능
- 설치 완료 후 자동 실행 가능
- 실행 시 콘솔 창 없음

## 참고

이 패키지에서는 실제 Windows EXE를 여기서 미리 빌드한 것이 아니라,
Windows 환경에서 바로 빌드할 수 있도록 스크립트와 설정을 정리한 것입니다.
