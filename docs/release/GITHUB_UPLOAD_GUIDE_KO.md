# Pepforge V4.0.0 — GitHub 공개 업로드 가이드

이 문서는 R14 최종 public source tree를 GitHub repository와 Release에 올릴 때 사용하는 체크리스트입니다.

## 1. Repository에 올릴 것

최종 ZIP을 통째로 repository 안에 커밋하지 말고, ZIP을 푼 뒤 **Pepforge source tree의 내용 자체**를 repository root에 올립니다.

예상 root 예시:

```text
README.md
README_KO.md
LICENSE
CITATION.cff
CHANGELOG.md
RELEASE_NOTES_V4.0.0.md
main_launcher.py
pepforge_cli.py
apps/
suite_gui/
peptiforg_core/
pepforge_structure_tool/
spps_v4_gui/
docs/
tests/
installer/
```

## 2. 첫 commit 전 확인

```bat
git init
git status
git add -n .
```

특히 다음을 확인합니다.

- `installer/Pepforge.spec`가 add 대상에 포함되는지
- `workspace/`, runtime log, local DB, cache가 포함되지 않는지
- private experimental data가 포함되지 않는지
- `actual_runs.csv`가 header-only인지

현재 R14 `.gitignore`는 `*.spec` 일반 규칙에 대해 `!installer/Pepforge.spec` 예외를 두어 build spec이 빠지지 않도록 구성되어 있습니다.

## 3. Repository push

Repository URL 기준:

```text
https://github.com/poowsh1407/Pepforge
```

예시:

```bat
git add .
git commit -m "Release Pepforge v4.0.0"
git branch -M main
git remote add origin https://github.com/poowsh1407/Pepforge.git
git push -u origin main
```

이미 remote가 있으면 `git remote add` 대신 기존 remote를 확인하고 사용합니다.

## 4. Tag

권장 tag:

```text
v4.0.0
```

예시:

```bat
git tag -a v4.0.0 -m "Pepforge V4.0.0"
git push origin v4.0.0
```

## 5. GitHub Release

권장 Release title:

```text
Pepforge V4.0.0 — Public Research Release
```

본문은 repository root의 `GITHUB_RELEASE_BODY.md`를 그대로 사용할 수 있습니다.

Source release asset으로 최종 source ZIP과 SHA-256 파일을 첨부합니다.

Windows installer/EXE는 반드시 실제 Windows 환경에서 build 및 smoke test 후에만 추가 asset으로 첨부합니다.

## 6. Release 후 확인

- README 이미지/상대 링크 정상 표시
- GitHub의 `Cite this repository`가 `CITATION.cff`를 정상 인식
- Release tag가 `v4.0.0`을 가리킴
- source ZIP SHA-256 일치
- public repository에 runtime/private/local data가 없음
- installer/build 문서와 실제 source tree가 일치

## 7. 과학적 표기

README/Release의 validation 숫자는 software/package verification 결과입니다. 실험적 affinity, efficacy, native structure, synthesis success를 검증했다는 의미로 사용하지 않습니다.
