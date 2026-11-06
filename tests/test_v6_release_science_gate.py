import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from peptiforg_core.v6_release_science_gate import CHECKS, audit_science_evidence, write_template
from peptiforg_core.v6_parameter_registry import audit_registry

class ScienceGateTests(unittest.TestCase):
    def test_template_never_passes(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t); write_template(p/'in.json')
            result = audit_science_evidence(p/'in.json', p/'out.json')
            self.assertEqual(result['status'], 'NOT_READY')
            self.assertEqual(result['checks_passed'], 0)
            self.assertEqual(len(result['checks']), len(CHECKS))

    def test_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t); (p/'actual.txt').write_text('real result')
            (p/'in.json').write_text(json.dumps({'v5_regression':{'status':'PASS','artifact':'actual.txt','sha256':'0'*64}}))
            result = audit_science_evidence(p/'in.json', p/'out.json')
            self.assertEqual(result['checks']['v5_regression']['status'], 'FAIL')

    def test_verified_artifact_still_requires_review(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t); content=b'actual artifact'; (p/'real').write_bytes(content)
            e={k:{'status':'PASS','artifact':'real','sha256':hashlib.sha256(content).hexdigest()} for k in CHECKS}
            (p/'in.json').write_text(json.dumps(e))
            result=audit_science_evidence(p/'in.json',p/'out.json')
            self.assertEqual(result['status'],'EVIDENCE_PRESENT_REQUIRES_REVIEW')
            self.assertEqual(result['scientific_validation'],'NOT_AUTOMATICALLY_CERTIFIED')

    def test_registry_never_automatically_approves_forcefield(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            rec={'canonical_identity':'dK','validation_level':'validated'}
            for key in ('attachment_graph_sha256','coordinate_template_sha256','parameter_file_sha256','validation_report_sha256'):
                rec[key]='a'*64
            for key in ('forcefield_name','charge_provenance','atom_typing_provenance'):
                rec[key]='declared'
            (p/'registry.json').write_text(json.dumps([rec]))
            result=audit_registry(p/'registry.json',p/'out.json')
            self.assertFalse(result['records'][0]['forcefield_ready'])
            self.assertEqual(result['records'][0]['status'],'EXTERNAL_REVIEW_REQUIRED')

    def test_duplicate_chemical_identity_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'in.json').write_text(json.dumps([{'canonical_identity':'dK'},{'canonical_identity':'dK'}]))
            with self.assertRaises(ValueError): audit_registry(p/'in.json',p/'out.json')

if __name__ == '__main__': unittest.main()
