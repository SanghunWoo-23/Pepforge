import argparse,json
from peptiforg_core.v6_independent_benchmark import benchmark
p=argparse.ArgumentParser();p.add_argument('test_manifest_csv');p.add_argument('output_json');a=p.parse_args()
print(json.dumps(benchmark(a.test_manifest_csv,a.output_json),indent=2))
