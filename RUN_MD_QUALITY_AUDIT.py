"""Evaluate real OpenMM StateDataReporter CSV without asserting MD convergence."""
import argparse
from peptiforg_core.v6_md_quality import write_md_quality_report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('production_csv')
    parser.add_argument('report_json')
    parser.add_argument('--temperature-k',type=float,default=300)
    args=parser.parse_args()
    result=write_md_quality_report(args.production_csv,args.report_json,target_temperature_k=args.temperature_k)
    print(result['status'],result['issues'])
