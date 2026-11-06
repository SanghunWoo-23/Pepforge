"""CLI: python AUDIT_ENSEMBLE_RESULTS.py path/to/ensemble_run"""
import argparse
import json
from peptiforg_core.v6_artifact_audit import audit_ensemble_run


def main():
    parser = argparse.ArgumentParser(description='Verify ensemble input/result hashes and status consistency')
    parser.add_argument('run_folder')
    args = parser.parse_args()
    result = audit_ensemble_run(args.run_folder)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
