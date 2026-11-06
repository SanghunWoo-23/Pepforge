import csv
import tempfile
import unittest
from pathlib import Path
from peptiforg_core.independent_benchmark_v2 import build_independent_split, sequence_identity

class IndependentBenchmarkTests(unittest.TestCase):
    def test_identity_and_invalid_chemistry(self):
        self.assertEqual(sequence_identity('ACDE','ACDE'),1.0)
        self.assertLess(sequence_identity('AAAA','RRRR'),0.3)
        with self.assertRaises(ValueError): sequence_identity('ACX','ACD')
    def test_group_locked_split(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.csv'
            rows=[('a','AAAA','famA','X'),('b','AAAA','famA','X'),
                  ('c','RRRR','famB','Y'),('d','GGGG','famC','Z'),
                  ('e','CCCC','famD','Q'),('f','TTTT','famE','R')]
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['target_id','receptor_sequence','receptor_family','receptor_accession']);w.writerows(rows)
            result=build_independent_split(p,Path(td)/'out',seed=9)
            split={r['target_id']:r['split'] for r in result['assignments']}
            self.assertEqual(split['a'],split['b'])
            self.assertEqual(result['cross_split_violations'],[])
            self.assertTrue((Path(td)/'out/independent_split_audit.json').exists())
    def test_missing_annotations_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.csv';p.write_text('target_id,receptor_sequence,receptor_family,receptor_accession\na,ACDE,,P1\n')
            with self.assertRaises(ValueError):build_independent_split(p,Path(td)/'out')
if __name__=='__main__': unittest.main()
