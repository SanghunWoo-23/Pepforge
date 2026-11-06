import csv
import tempfile
import unittest
from pathlib import Path
from peptiforg_core.scientific_assessment_v2 import assess_evidence,consensus_rank,run_assessment

class ScientificAssessmentTests(unittest.TestCase):
    def test_evidence_fail_closed(self):
        result=assess_evidence({'candidate_id':'p1'})
        self.assertEqual(result['status'],'REVIEW_REQUIRED')
        self.assertEqual(len(result['flags']),5)
        good=assess_evidence({'candidate_id':'p1','residue_status':'standard','parameter_status':'verified','receptor_provenance':'pdb','pose_source':'executed_native','benchmark_domain':'in_domain_verified'})
        self.assertEqual(good['status'],'EVIDENCE_DOCUMENTED')
        self.assertIsNone(good['calibrated_probability'])
    def test_mixed_scale_and_direction(self):
        rows=[{'backend':'a','candidate_id':'x','score':1,'direction':'higher'},
              {'backend':'a','candidate_id':'y','score':0,'direction':'higher'},
              {'backend':'b','candidate_id':'x','score':-200,'direction':'lower'},
              {'backend':'b','candidate_id':'y','score':-100,'direction':'lower'}]
        r=consensus_rank(rows)
        self.assertEqual(r['results'][0]['candidate_id'],'x')
        self.assertEqual(r['results'][0]['consensus_rank_score'],1)
    def test_missing_or_invalid_rejected(self):
        rows=[{'backend':'a','candidate_id':'x','score':1,'direction':'higher'},
              {'backend':'a','candidate_id':'y','score':0,'direction':'higher'},
              {'backend':'b','candidate_id':'x','score':2,'direction':'higher'}]
        with self.assertRaises(ValueError):consensus_rank(rows)
        rows[2]['candidate_id']='y';rows[2]['score']='NaN'
        with self.assertRaises(ValueError):consensus_rank(rows)
    def test_audit_writes_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'scores.csv';out=Path(td)/'out.json'
            with inp.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['candidate_id']);w.writeheader();w.writerow({'candidate_id':'p'})
            self.assertIn('input_sha256',run_assessment(inp,out,mode='evidence'))
            self.assertTrue(out.exists())
if __name__=='__main__':unittest.main()
