import sys
from pathlib import Path
import unittest
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from numerical_reference.policy import evaluate_node
from numerical_reference.current_nodes import _v5

class NumericalProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def test_qk_array_ast_matches_native_production_cpu_dot(self):
        rng=np.random.default_rng(20261019)
        q=rng.integers(-(1<<20),1<<20,size=(24,4,32),dtype=np.int64)
        k=rng.integers(-2047,2048,size=(24,4,32),dtype=np.int64)
        code=rng.integers(1,256,size=(24,4),dtype=np.int64)
        shift=rng.integers(8,33,size=(24,4),dtype=np.int64)
        a=dict(dot=np.sum(q*k,axis=-1),kv_code=code,kv_shift=shift,query_s24=q,key_s12=k)
        result=evaluate_node('qk',a,{})
        v5=_v5();audit=v5.V5Audit(torch.device('cpu'))
        keys=v5.KV12(torch.from_numpy(k[:,None,None,:,:]),torch.from_numpy(code[:,None,None,:]),torch.from_numpy(shift[:,None,None,:]))
        expected=v5._qk_scores_s20(torch.from_numpy(q.reshape(24,1,1,128)),keys,1,audit).numpy().reshape(24)
        np.testing.assert_array_equal(result['current_code'],expected)
        self.assertTrue(np.all(result['valid_mask']))
        self.assertFalse(torch.cuda.is_initialized())
    def test_softmax_private_trace_is_identical_to_active_function(self):
        v5=_v5();rng=np.random.default_rng(9)
        from model.fixbit_v2 import build_softmax_exp_lut_u17
        lut=np.array(build_softmax_exp_lut_u17(),dtype=np.int64)
        scores=rng.integers(-(16<<14),(16<<14)+1,size=(48,128),dtype=np.int64)
        mask=rng.random((48,128))>.3;mask[:,0]=True;mask[0,:]=False
        result=evaluate_node('softmax',dict(score_q14=scores,valid_mask=mask,lut_u17=lut),{})
        expected=v5._softmax_u16(torch.from_numpy(scores),torch.from_numpy(mask),torch.from_numpy(lut)).numpy()
        np.testing.assert_array_equal(result['current_code'],expected)
        self.assertFalse(np.any(result['bound_violation_mask']))
        self.assertFalse(np.any(result['reference_bound_violation_mask']))
        self.assertTrue(np.all(result['software_padding_mask'][0]))
    def test_array_broadcast_and_invalid_rows_are_separate(self):
        a=dict(dot=np.array([[1,2],[3,4]],dtype=np.int64),act_code=np.array(1,dtype=np.uint8),
               weight_code=np.array([1,2],dtype=np.uint8),act_shift=np.array([[12],[63]]),weight_shift=np.array([13,13]))
        result=evaluate_node('linear',a,{'profile':'mlp_gate_up','metadata':{'document_id':'test-only'}})
        np.testing.assert_array_equal(result['domain_valid_mask'],[True,False])
        np.testing.assert_array_equal(result['metric_mask'],[True,True])
        self.assertEqual(result['metadata']['document_id'],'test-only')
        self.assertEqual(result['metadata']['output_shape'],[2])

if __name__=='__main__':unittest.main()
