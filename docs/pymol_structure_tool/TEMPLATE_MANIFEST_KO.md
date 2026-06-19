# Template manifest / attach point 규칙 (v1.3.0)

`data/template_manifest_v130.json`은 non-natural AA, linker, label, chemical modification의 template 정보를 기록한다.

중요한 점:

- 현재 구조 생성은 RDKit 기반 connected starting model이다.
- `data/templates/*.sdf`는 PyMOL/RDKit에서 읽히는지 검증된다.
- curated SDF로 교체할 때 token 이름과 attach-point 역할을 유지하면 기존 입력 문법을 유지할 수 있다.

검증:

```bash
python build_for_pymol.py --audit-templates
```
