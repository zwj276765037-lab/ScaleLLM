"""Independent CPU qualification; reference uses centered NumPy probabilities
and positive-mass difference, not the evaluated torch L1 implementation."""
import json,math,unittest
from pathlib import Path
import numpy as np
import torch
from softmax_tv_extension_v2 import probability_mass_tv,measure_logits
from logit_numerical_extension import OutputHead,measure_logits as old_measure

def independent(current,reference):
    result=[];masses=[]
    for a,b in zip(np.asarray(current,dtype=np.float64),np.asarray(reference,dtype=np.float64)):
        ea=np.exp(a-np.max(a));eb=np.exp(b-np.max(b))
        pa=ea/math.fsum(ea.tolist());pb=eb/math.fsum(eb.tolist())
        # Positive mass is TV for two normalized distributions.
        result.append(math.fsum(max(float(x-y),0.) for x,y in zip(pa,pb)))
        masses.append([math.fsum(pa.tolist()),math.fsum(pb.tolist())])
    return np.array(result),masses

def evaluated(a,b,chunk):
    a=torch.as_tensor(a,dtype=torch.float64);b=torch.as_tensor(b,dtype=torch.float64)
    return probability_mass_tv(((s,min(s+chunk,a.shape[1]),a[:,s:s+chunk],b[:,s:s+chunk]) for s in range(0,a.shape[1],chunk)),torch.logsumexp(a,1),torch.logsumexp(b,1),a.shape[0],a.shape[1])

class TVTests(unittest.TestCase):
    def test_exact_equality(self):
        a=np.arange(30).reshape(3,10);r=evaluated(a,a,4);self.assertEqual(r['tv'],[0.,0.,0.])
    def test_closed_form_quarter(self):
        result=evaluated([[math.log(3.),0.]],[[0.,0.]],1)
        self.assertAlmostEqual(result['tv'][0],.25,places=14)
    def test_common_shift(self):
        a=np.arange(30).reshape(3,10)/7;r=evaluated(a,a+1000,4);self.assertLess(max(r['tv']),1e-12)
    def test_extreme_finite(self):
        a=np.array([[10000,-10000,0],[-10000,10000,0]],float);b=-a
        r=evaluated(a,b,2);np.testing.assert_allclose(r['tv'],[1,1],atol=1e-14);self.assertGreater(r['natural_exp_underflow_entries_current'],0)
    def test_chunk_equivalence_independent(self):
        rng=np.random.default_rng(912);a=rng.normal(size=(7,103))*8;b=a+rng.normal(size=a.shape)*.4
        expected,_=independent(a,b)
        for chunk in [1,9,32,103]:np.testing.assert_allclose(evaluated(a,b,chunk)['tv'],expected,rtol=1e-12,atol=1e-14)
    def test_normalization_failure(self):
        a=torch.zeros((2,5),dtype=torch.float64)
        with self.assertRaises(ValueError):probability_mass_tv([(0,5,a,a)],torch.zeros(2),torch.zeros(2),2,5)
    def test_missing_vocab_failure(self):
        a=torch.zeros((2,5),dtype=torch.float64)
        with self.assertRaises(ValueError):probability_mass_tv([(0,4,a[:,:4],a[:,:4])],torch.zeros(2),torch.zeros(2),2,5)
    def test_nonfinite_failure(self):
        with self.assertRaises(ValueError):evaluated([[0,float('nan')]],[[0,0]],2)
    def test_wrapper_preserves_old_metrics(self):
        generator=torch.Generator().manual_seed(1);w=torch.randn((37,8),generator=generator);a=torch.randn((5,8),generator=generator);b=a+.01
        head=OutputHead(w,{'consumed_tensor_sha256':'synthetic'},Path('/tmp'),chunk_size=7);doc={'doc_id':'synthetic','domain':'test'}
        old=old_measure(a,b,head,doc);new=measure_logits(a,b,head,doc);tv=new.pop('softmax_tv');self.assertEqual(new,old)
        expected,_=independent((a@w.T).numpy(),(b@w.T).numpy());np.testing.assert_allclose(tv['tv'],expected,rtol=1e-5,atol=1e-7)

if __name__=='__main__':unittest.main()
