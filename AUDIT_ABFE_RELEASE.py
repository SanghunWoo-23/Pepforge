from __future__ import annotations
import argparse,json
from pathlib import Path
from peptiforg_core.v6_abfe_release_gate import audit_result

def main():
 p=argparse.ArgumentParser();p.add_argument('result');p.add_argument('--out');a=p.parse_args()
 result=audit_result(a.result)
 dst=Path(a.out) if a.out else Path(a.result).with_suffix('.release_audit.json')
 if dst.exists(): raise FileExistsError(dst)
 dst.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
