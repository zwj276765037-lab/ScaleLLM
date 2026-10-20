"""CPU semantic tests against independent dense NumPy calculations."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from logit_numerical_extension import OutputHead,measure_logits,qualify_chunks,THRESHOLDS

def lse(x):
    m=x.max(axis=1)
    return m+np.log(np.exp(x-m[:,None]).sum(axis=1))

class Measurement(unittest.TestCase):
    def compare(self,a,b,w,chunk=7,raw=False):
        with tempfile.TemporaryDirectory() as tmp:
            head=OutputHead(torch.tensor(w,dtype=torch.float32),{'consumed_tensor_sha256':'synthetic'},Path(tmp),chunk)
            doc={'doc_id':'synthetic','domain':'test'}
            if raw:doc['_logit_audit_dir']=tmp
            row=measure_logits(torch.tensor(a),torch.tensor(b),head,doc)
            x=a.astype(np.float64)@w.astype(np.float64).T;y=b.astype(np.float64)@w.astype(np.float64).T
            delta=x-y
            self.assertEqual(row['score_pairs'],x.size)
            self.assertEqual(row['error_energy'],float((delta*delta).sum()))
            self.assertEqual(row['reference_signal_energy'],float((y*y).sum()))
            if row['reference_signal_energy']>0:
                self.assertAlmostEqual(row['relative_l2_percent'],100*np.linalg.norm(delta)/np.linalg.norm(y),places=10)
            np.testing.assert_array_equal(row['per_token']['max_abs_logit_delta'],np.max(np.abs(delta),axis=1))
            np.testing.assert_array_equal(row['per_token']['current_top1_ids'],x.argmax(1))
            np.testing.assert_array_equal(row['per_token']['reference_top1_ids'],y.argmax(1))
            np.testing.assert_array_equal(row['per_token']['current_top1_tie_counts'],(x==x.max(1)[:,None]).sum(1))
            np.testing.assert_array_equal(row['per_token']['reference_top1_margin'],np.sort(y,axis=1)[:,-1]-np.sort(y,axis=1)[:,-2])
            expected=np.max(np.abs(delta-(lse(x)-lse(y))[:,None]),axis=1)
            np.testing.assert_allclose(row['per_token']['max_abs_logprob_delta'],expected,rtol=1e-12,atol=1e-12)
            self.assertEqual(row['score_within_threshold_counts'],[int((np.abs(delta)<=v).sum()) for v in THRESHOLDS])
            self.assertEqual(row['top1_match_count'],int((x.argmax(1)==y.argmax(1)).sum()))
            if raw:
                with np.load(Path(tmp)/'logit_raw_audit.npz') as z:
                    np.testing.assert_array_equal(z['logits_current'],x[z['token_positions']])
                    np.testing.assert_array_equal(z['logits_reference'],y[z['token_positions']])
            q=qualify_chunks(torch.tensor(a),torch.tensor(b),head,Path(tmp)/'qualification.json',alternate=3)
            self.assertEqual(q['paired_delta_difference_max'],0)
            json.dumps(row,allow_nan=False)
            return row
    def test_all_vocab_with_tail_and_raw(self):
        rng=np.random.default_rng(531)
        a=rng.integers(-7,8,(5,9)).astype(np.float32)/4
        b=rng.integers(-7,8,(5,9)).astype(np.float32)/4
        w=rng.integers(-7,8,(37,9)).astype(np.float32)/4
        self.compare(a,b,w,raw=True)
    def test_ties_across_chunks(self):
        a=np.array([[1.,2.],[0.,0.]],dtype=np.float32)
        w=np.array([[1.,0.],[0.,1.],[0.,1.],[0.,-1.],[0.,1.]],dtype=np.float32)
        r=self.compare(a,a,w,chunk=2)
        self.assertEqual(r['per_token']['current_top1_ids'],[1,0])
        self.assertEqual(r['per_token']['current_top1_tie_counts'],[3,5])
        self.assertEqual(r['max_abs_logit_delta'],0)
    def test_common_shift(self):
        a=np.array([[3.,2.],[4.,1.]],dtype=np.float32)
        b=a.copy();b[:,0]-=2
        w=np.array([[1.,0.],[1.,1.],[1.,1.],[1.,-1.],[1.,3.]],dtype=np.float32)
        r=self.compare(a,b,w,chunk=2)
        self.assertEqual(r['max_abs_logit_delta'],2)
        self.assertLess(r['max_abs_logprob_delta'],1e-12)
        self.assertEqual(r['top1_match_count'],2)
    def test_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            head=OutputHead(torch.ones(3,2),{'consumed_tensor_sha256':'synthetic'},Path(tmp),2)
            with self.assertRaises(ValueError):measure_logits(torch.tensor([[float('nan'),1.]]),torch.ones(1,2),head,{'doc_id':'bad'})
            head.weight[0,0]=float('inf')
            with self.assertRaises(ValueError):measure_logits(torch.ones(1,2),torch.ones(1,2),head,{'doc_id':'bad'})

if __name__=='__main__':
    torch.set_num_threads(1)
    unittest.main()
