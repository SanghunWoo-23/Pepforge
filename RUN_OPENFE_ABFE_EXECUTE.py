"""Execute a prepared OpenFE ABFE transformation and verify artifact provenance."""
import argparse,json
from peptiforg_core.v6_openfe_result_runner import run,inspect_openfe_result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('transformation_json',nargs='?')
    p.add_argument('work_directory',nargs='?')
    p.add_argument('--timeout-seconds',type=int)
    p.add_argument('--inspect-result',help='Inspect existing OpenFE full-cycle result JSON without a new simulation')
    args=p.parse_args()
    if args.inspect_result:
        outcome=inspect_openfe_result(args.inspect_result)
    else:
        if not args.transformation_json or not args.work_directory: p.error('Transformation and work directory required')
        outcome=run(args.transformation_json,args.work_directory,timeout_seconds=args.timeout_seconds)
    print(json.dumps(outcome,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
