import csv
import tempfile
import unittest
from pathlib import Path
from peptiforg_core.paired_benchmark_v2 import evaluate_paired

class PairedBenchTests(unittest.TestCase):
    def write(self, td, rows):
        path=Path(td)/'benchmark.csv'
        with path.open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=['target_id','split','baseline_success','candidate_success','family'])
            w.writeheader();w.writerows(rows)
        return path
    def test_gain_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as td:
            rows=[dict(target_id=str(i),split='test',baseline_success='0',candidate_success='1',family='F'+str(i%5)) for i in range(25)]
            inp=self.write(td,rows)
            a=evaluate_paired(inp,Path(td)/'a.json',bootstrap_replicates=100)
            b=evaluate_paired(inp,Path(td)/'b.json',bootstrap_replicates=100)
            self.assertEqual(a,b)
            self.assertEqual(a['paired_delta'],1)
            self.assertEqual(a['family_bootstrap_95pct_delta_interval'],[1,1])
            self.assertFalse(a['release_approved'])
    def test_duplicates_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            row=dict(target_id='X',split='test',baseline_success='0',candidate_success='1',family='F')
            inp=self.write(td,[row,row])
            with self.assertRaisesRegex(ValueError,'duplicate'):evaluate_paired(inp,Path(td)/'a.json',bootstrap_replicates=100)
    def test_invalid_outcome_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            inp=self.write(td,[dict(target_id='X',split='test',baseline_success='0.5',candidate_success='1',family='F')])
            with self.assertRaisesRegex(ValueError,'0 or 1'):evaluate_paired(inp,Path(td)/'a.json',bootstrap_replicates=100)
    def test_insufficient_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            inp=self.write(td,[dict(target_id='X',split='test',baseline_success='0',candidate_success='1',family='F')])
            a=evaluate_paired(inp,Path(td)/'a.json',bootstrap_replicates=100)
            self.assertEqual(a['status'],'INSUFFICIENT_EVALUATION_COVERAGE')
if __name__=='__main__':unittest.main()
