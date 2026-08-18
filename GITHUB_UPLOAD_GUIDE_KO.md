# GitHub 업로드 안내

## 새 저장소에 처음 올릴 때

```bash
git init
git add .
git commit -m "Release Pepforge v3.0.0 with SPPS Planner V4"
git branch -M main
git remote add origin https://github.com/poowsh1407/Pepforge.git
git push -u origin main
```

이미 같은 원격 저장소가 연결되어 있다면 `git init`과 `git remote add`를 다시 실행하지 말고 변경사항을 검토한 뒤 commit/push하십시오.

## Release 권장값

- Tag: `v3.0.0`
- Release title: `Pepforge v3.0.0 — SPPS Planner V4 Integrated Public Release`
- 본문: `RELEASE_NOTES_V3.0.0.md` 내용 사용
- Asset: 최종 GitHub 공개 ZIP

## 올리기 전 확인

```bash
python -m compileall -q .
python pepforge_cli.py release-gate --root-dir . --output-dir qa_output
git status --ignored
```

`PUBLIC_DATA_POLICY.md`와 `docs/GITHUB_PUBLISH_CHECKLIST.md`를 확인하고, 실제 실험 데이터·회사 자료·credential·SQLite·model·session·log가 없는지 최종 점검하십시오.
