"""Independent comparison of OpenFE ABFE against experimentally measured Kd.

This tool NEVER claims validation from synthetic fixtures or missing benchmarks.
Input columns: case_id,family,split,calc_dg_kcal_mol,calc_uncertainty_kcal_mol,
                  kd_molar,temperature_K,replicates,source_doi
All energies are in kcal/mol at the supplied temperature and 1 M standard state.
"""
from __future__ import annotations
import csv, hashlib, json, math, random, statistics
from pathlib import Path

R = 0.00198720425864083  # kcal mol^-1 K^-1
COLUMNS = ('case_id','family','split','calc_dg_kcal_mol', 'calc_uncertainty_kcal_mol',
           'kd_molar','temperature_K','replicates','source_doi')
class ValidationError(ValueError): pass

def analyze_csv(path, *, min_cases=10, bootstrap=2000, seed=2026):
    # Validate configuration before reading inputs; zero iterations cannot yield a CI.
    if isinstance(min_cases, bool) or not isinstance(min_cases, int) or min_cases < 1:
        raise ValidationError('min_cases must be a positive integer')
    if isinstance(bootstrap, bool) or not isinstance(bootstrap, int) or bootstrap < 100:
        raise ValidationError('bootstrap must be an integer >= 100')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValidationError('seed must be an integer')
    path=Path(path)
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValidationError('Missing required columns: '+','.join(set(COLUMNS)-set(reader.fieldnames or [])))
        rows=list(reader)
    seen=set(); cases=[]
    for i, row in enumerate(rows,2):
        cid=row['case_id'].strip()
        if not cid or cid in seen: raise ValidationError(f'Row {i}: duplicate or missing case_id')
        seen.add(cid)
        if row['split'].strip().lower() != 'independent_test':
            raise ValidationError(f'Row {i}: not an independent_test case')
        if not row['family'].strip() or not row['source_doi'].strip():
            raise ValidationError(f'Row {i}: missing family/experiment source')
        try:
            dg=float(row['calc_dg_kcal_mol']); unc=float(row['calc_uncertainty_kcal_mol'])
            kd=float(row['kd_molar']); t=float(row['temperature_K']); n=int(row['replicates'])
        except (ValueError, TypeError): raise ValidationError(f'Row {i}: invalid numeric value')
        if not all(map(math.isfinite,(dg,unc,kd,t))) or unc<0 or kd<=0 or t<250 or t>400 or n<3:
            raise ValidationError(f'Row {i}: invalid parameters or insufficient replicates')
        exp=R*t*math.log(kd/1.0) # standard-state binding free energy
        cases.append({'case_id':cid,'family':row['family'].strip(), 'predicted':dg,
                      'experimental':exp,'error':dg-exp,'replicates':n,'source_doi':row['source_doi'].strip()})
    if len(cases)<min_cases: raise ValidationError(f'Independent cases {len(cases)} < required {min_cases}')
    errors=[c['error'] for c in cases]
    def stats(v):
        return {'mae_kcal_mol':sum(abs(x) for x in v)/len(v),
                'rmse_kcal_mol':math.sqrt(sum(x*x for x in v)/len(v)),
                'bias_kcal_mol':sum(v)/len(v)}
    families=sorted({c['family'] for c in cases})
    by_family={fam:[c['error'] for c in cases if c['family']==fam] for fam in families}
    macro=stats([statistics.mean(by_family[f]) for f in families])
    rng=random.Random(seed); draws=[]
    if len(families)>=2:
        for _ in range(bootstrap):
            sampled=[rng.choice(families) for _ in families]
            batch=[rng.choice(by_family[f]) for f in sampled]
            draws.append(stats(batch)['mae_kcal_mol'])
        draws.sort()
        ci=[draws[int(.025*(len(draws)-1))],draws[int(.975*(len(draws)-1))]]
    else: ci=None
    # A numerical fit is not a scientific accuracy certificate without verified independent provenance.
    return {'status':'INDEPENDENT_DATA_STATISTICS_ONLY_NOT_CERTIFIED',
            'science_accuracy_certified':False,'n_cases':len(cases),'n_families':len(families),
            'metrics':stats(errors),'family_mean_error_metrics':macro,
            'family_bootstrap_mae_95pct_ci':ci,'bootstrap_iterations':bootstrap,
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'cases':cases,
            'caveats':['Experimental assay conditions and sources must be independently checked',
                       'Predicted values must come from genuine complete OpenFE ABFE runs',
                       'No certification without sampling/convergence and force-field evidence']}

def main():
    import argparse
    p=argparse.ArgumentParser(description='ABFE experimental Kd comparison; never self-certifies accuracy')
    p.add_argument('csv');p.add_argument('output');p.add_argument('--min-cases',type=int,default=10)
    args=p.parse_args()
    result=analyze_csv(args.csv,min_cases=args.min_cases)
    out=Path(args.output)
    if out.exists(): raise SystemExit('Output already exists; refusing overwrite')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(result['status'])
if __name__=='__main__':main()
