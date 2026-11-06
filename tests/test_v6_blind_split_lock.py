import csv
import tempfile
import unittest
from pathlib import Path
from peptiforg_core.v6_blind_split_lock import create_lock,verify_lock

class LockTests(unittest.TestCase):
    def test_lock_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); src=base/'splits.csv'
            with src.open('w', newline='') as f:
                w=csv.writer(f);w.writerow(['target_id','split','cluster']);w.writerows([('x','train','a'),('y','validation','b'),('z','test','c')])
            create_lock(src,base/'lock.json')
            self.assertEqual(verify_lock(src,base/'lock.json',base/'verify.json')['status'],'MATCH')
            src.write_text(src.read_text().replace('x,train,a','x,test,a'))
            self.assertEqual(verify_lock(src,base/'lock.json',base/'verify.json')['status'],'FAIL')
    def test_cluster_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);src=base/'s.csv';src.write_text('target_id,split,cluster\nx,train,a\ny,test,a\nz,validation,b\n')
            with self.assertRaises(ValueError):create_lock(src,base/'l.json')
if __name__=='__main__':unittest.main()
