"""Pepforge V6.0.0 offline public-source preflight (NOT scientific validation)."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT_DOCS = ('README.md', 'README_KO.md', 'MANUAL_EN.md', 'MANUAL_KO.md',
             'SCIENCE_ENGINE_INSTALL_GUIDE_KO.md', 'SPPS_V8_INTEGRATION_README_KO.md')
ROOT_BATS = {'INSTALL_BUILD_TOOLS_AND_BUILD.bat', 'RUN_PEPFORGE_SOURCE.bat'}
REQUIRED = (*ROOT_DOCS, 'VERSION.txt', 'CITATION.cff', 'LICENSE',
            'main_launcher.py', 'INSTALL_SCIENCE_ENGINES.py',
            'installer/Pepforge_Setup.iss', 'installer/Pepforge.spec',
            'vendor/spps_planner_v8/VERSION.txt')
MD_LOCAL_LINK = re.compile(r'(?<!!)\[[^\]]*\]\(([^)]+)\)')


def audit(root: Path) -> dict:
    root = Path(root).resolve()
    issues: list[str] = []
    for item in REQUIRED:
        if not (root/item).is_file():
            issues.append(f'missing-required:{item}')
    if issues:
        return {'pass':False, 'issues':issues}
    if (root/'VERSION.txt').read_text(encoding='utf-8').strip() != 'V6.0.0':
        issues.append('incorrect-pepforge-version')
    if (root/'vendor/spps_planner_v8/VERSION.txt').read_text(encoding='utf-8').strip() != 'V8.0.0':
        issues.append('incorrect-spps-v8-version')
    citation=(root/'CITATION.cff').read_text(encoding='utf-8')
    if 'version: "6.0.0"' not in citation:
        issues.append('citation-version-not-6.0.0')
    installer=(root/'installer/Pepforge_Setup.iss').read_text(encoding='utf-8')
    if '#define MyAppVersion "6.0.0"' not in installer or 'OutputBaseFilename=Pepforge_Setup_v6.0.0' not in installer:
        issues.append('windows-installer-version-mismatch')
    for item in ROOT_DOCS:
        data=(root/item).read_text(encoding='utf-8')
        if 'V6.0.0' not in data:
            issues.append(f'current-document-version-missing:{item}')
        if item.startswith('MANUAL') and re.search(r'SPPS Planner V7\.0\.0|Pepforge V5\.0\.0',data):
            issues.append(f'outdated-current-manual:{item}')
    if set(x.name for x in root.glob('*.bat'))!=ROOT_BATS:
        issues.append('unexpected-top-level-bat-inventory')
    all_bats=sorted(str(x.relative_to(root)) for x in root.rglob('*.bat') if '.build_venv' not in x.parts)
    all_txt=sorted(str(x.relative_to(root)) for x in root.rglob('*.txt') if '.build_venv' not in x.parts)
    root_txt=[x for x in all_txt if '/' not in x]
    if any('RELEASE' in name.upper() or 'HANDOVER' in name.upper() for name in root_txt):
        issues.append('root-contains-release-or-handover-txt')
    broken=[]
    for item in ROOT_DOCS:
        file=root/item
        for dest in MD_LOCAL_LINK.findall(file.read_text(encoding='utf-8')):
            dest=dest.split('#',1)[0].split('?',1)[0].strip()
            if not dest or dest.startswith(('https://','http://','mailto:')): continue
            if not (file.parent/dest).exists(): broken.append(f'{item}: {dest}')
    if broken: issues.extend('broken-local-link:'+l for l in broken)
    return {
        'pass': not issues, 'issues':issues,
        'version':'V6.0.0','bundled_spps_version':'V8.0.0',
        'top_level_bats':sorted(ROOT_BATS),
        'total_bats':len(all_bats),'bat_inventory':all_bats,
        'total_txt':len(all_txt),'txt_inventory':all_txt,
        'broken_current_doc_links':broken,
        'checks':'static source/doc/installer inventory only',
        'windows_exe_verified':False,'wsl_install_verified':False,'abfe_accuracy_verified':False,
    }


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--output',type=Path)
    args=ap.parse_args(argv)
    result=audit(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'pass':result['pass'],'issues':result['issues'],
                      'total_bats':result.get('total_bats'),'total_txt':result.get('total_txt')},ensure_ascii=False))
    return 0 if result['pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
