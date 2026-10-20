import inspect
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from numerical_reference.local_observer import LocalObserver,local_observer_context,NODES

class Audit:
    def __init__(self,device='cpu'):
        self.device=torch.device(device)
        self.values={name:torch.zeros((),dtype=torch.int64,device=device) for name in
                     ('rope_output_saturation','qk_score_clip','pv_output_saturation')}
    def add(self,name,value):self.values[name].add_(value)


def fake_source():
    last={}
    def linear(activation,saturation_count,accumulator_overflow_count):
        saturation_count.add_(1);accumulator_overflow_count.add_(2)
        last['linear']=activation+1
        return last['linear']
    def rope(raw,cos_q16,sin_q16,audit):
        audit.add('rope_output_saturation',1);last['rope']=raw+1;return last['rope']
    def qk(query_s24,keys,num_key_value_groups,audit):
        audit.add('qk_score_clip',1);return query_s24+1
    def softmax(score_s20,valid_mask,lut_u17):return torch.where(valid_mask,score_s20+1,0)
    def pv(probability_u16,values,num_key_value_groups,audit,head_chunk=4):
        audit.add('pv_output_saturation',1);return probability_u16+1
    source=SimpleNamespace(grouped_linear_s24=linear,_fixed_rope=rope,_qk_scores_s20=qk,_softmax_u16=softmax,_pv_s24=pv)
    class Linear:
        op_name='q_proj'
        def project_prepared(self,activation):
            return source.grouped_linear_s24(activation,self.sat,self.acc)
        def __init__(self):self.sat=torch.zeros((),dtype=torch.int64);self.acc=self.sat.clone()
    source.V5ProductionLinear=Linear
    def linear_ref(activation,saturation_count,accumulator_overflow_count):
        saturation_count.add_(3);accumulator_overflow_count.add_(4);return activation
    def rope_ref(raw,cos_q16,sin_q16,audit):audit.add('rope_output_saturation',7);return raw
    def qk_ref(query_s24,keys,num_key_value_groups,audit):audit.add('qk_score_clip',7);return query_s24
    def softmax_ref(score_s20,valid_mask,lut_u17):return torch.where(valid_mask,score_s20,0)
    def pv_ref(probability_u16,values,num_key_value_groups,audit,head_chunk=4):audit.add('pv_output_saturation',7);return probability_u16
    backend=SimpleNamespace(grouped_linear_exact=linear_ref,rope_exact=rope_ref,qk_exact=qk_ref,softmax_exact=softmax_ref,pv_exact=pv_ref)
    return source,backend,last


class LocalObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def test_only_current_continues_shadow_audit_and_statistics(self):
        source,backend,last=fake_source();sink=[];audit=Audit();x=torch.tensor([2,4],dtype=torch.int64)
        originals={name:getattr(source,name) for name in NODES}
        with local_observer_context(source,backend=backend,sink=sink.append,doc_id='doc',layer=0) as observer:
            observer.op_name='rope_test'
            out=source._fixed_rope(x,None,None,audit)
            self.assertIs(out,last['rope'])
            self.assertEqual(audit.values['rope_output_saturation'].item(),1)
            # Repeat to test per-call deltas and shadow reset, not cumulative counts.
            source._fixed_rope(x,None,None,audit)
            self.assertEqual(audit.values['rope_output_saturation'].item(),2)
            rows=observer.flush('doc')
            self.assertEqual(len(rows),1);row=rows[0]
            self.assertEqual(row['count'],4);self.assertEqual(row['calls'],2)
            self.assertAlmostEqual(row['sum_signal2'],40/(1<<32))
            self.assertAlmostEqual(row['sum_diff2'],4/(1<<32))
            self.assertAlmostEqual(row['bias'],1/(1<<16))
            self.assertAlmostEqual(row['relative_l2_percent'],100*math.sqrt(.1))
            self.assertEqual(row['audit_current_delta']['rope_output_saturation'],2)
            self.assertEqual(row['audit_reference_delta']['rope_output_saturation'],14)
            self.assertEqual(row['audit_delta_current_minus_reference']['rope_output_saturation'],-12)
            self.assertFalse(row['strict_per_output_domain']);self.assertFalse(row['exact_pre_output_comparison'])
        self.assertEqual(sink,rows)
        for name,value in originals.items():self.assertIs(getattr(source,name),value)
        self.assertFalse(torch.cuda.is_initialized())
    def test_linear_module_operation_and_independent_counter_pointers(self):
        source,backend,last=fake_source();linear=source.V5ProductionLinear();old=source.V5ProductionLinear.project_prepared
        with local_observer_context(source,backend=backend,doc_id='x',layer=31) as observer:
            result=linear.project_prepared(torch.tensor([1],dtype=torch.int32))
            self.assertIs(result,last['linear']);self.assertEqual(linear.sat.item(),1);self.assertEqual(linear.acc.item(),2)
            row=observer.flush()[0]
            self.assertEqual(row['op_name'],'q_proj')
            self.assertEqual(row['audit_reference_delta']['saturation_count'],3)
            self.assertEqual(row['audit_current_delta']['accumulator_overflow_count'],2)
            self.assertIsNone(row['audit_reference_delta']['accumulator_overflow_count'])
            self.assertIsNone(row['audit_delta_current_minus_reference']['accumulator_overflow_count'])
        self.assertIs(source.V5ProductionLinear.project_prepared,old)
    def test_softmax_mask_padding_zero_signal_and_document_boundaries(self):
        source,backend,_=fake_source()
        with local_observer_context(source,backend=backend,doc_id='a',layer=2) as observer:
            scores=torch.tensor([[0,0],[8,9]],dtype=torch.int64);mask=torch.tensor([[True,False],[False,False]])
            source._softmax_u16(scores,mask,None)
            observer.set_document('b');source._softmax_u16(scores,mask,None)
            row=observer.flush('a')[0]
            self.assertEqual(row['count'],1);self.assertEqual(row['total_shape_elements'],4)
            self.assertTrue(row['zero_signal']);self.assertIsNone(row['relative_l2_percent']);self.assertIsNone(row['normalized_bias'])
            self.assertEqual(observer.flush()[0]['doc_id'],'b')
            self.assertEqual(observer.flush(),[])
    def test_signatures_all_wrappers_and_exception_restoration(self):
        source,backend,_=fake_source();originals={name:getattr(source,name) for name in NODES}
        with self.assertRaisesRegex(RuntimeError,'exercise'):
            with local_observer_context(source,backend=backend,doc_id='d',layer=1) as observer:
                for name in NODES:self.assertEqual(inspect.signature(getattr(source,name)),inspect.signature(originals[name]))
                x=torch.tensor([1,2],dtype=torch.int64);audit=Audit()
                source._qk_scores_s20(x,None,1,audit);source._pv_s24(x,None,1,audit)
                self.assertEqual({r['node'] for r in observer.flush()},{'qk','pv'})
                raise RuntimeError('exercise')
        for name,value in originals.items():self.assertIs(getattr(source,name),value)
        self.assertFalse(hasattr(source,'_m005_local_observer_active'))
    def test_missing_coordinates_and_nested_or_reference_context_rejected(self):
        source,backend,_=fake_source();observer=LocalObserver(source,backend=backend)
        with observer.context():
            with self.assertRaises(RuntimeError):source._fixed_rope(torch.tensor([1]),None,None,Audit())
            with self.assertRaises(RuntimeError):
                with observer.context():pass
        source._m005_arithmetic_context_active=True
        with self.assertRaises(RuntimeError):
            with observer.context():pass
        del source._m005_arithmetic_context_active
        with self.assertRaises(ValueError):observer.set_context(doc_id='d',layer=32)


    def test_native_production_and_backend_keyword_signatures(self):
        from numerical_reference.model_compat import production_module
        from numerical_reference import gpu_reference
        source=production_module()
        for name,(_,exact_name,_) in NODES.items():
            current=inspect.signature(getattr(source,name))
            reference=inspect.signature(getattr(gpu_reference,exact_name))
            self.assertTrue(set(current.parameters)<=set(reference.parameters),(name,current,reference))
        self.assertFalse(torch.cuda.is_initialized())


    def test_rope_query_key_sites_are_disjoint(self):
        source,backend,_=fake_source()
        with local_observer_context(source,backend=backend,doc_id='d',layer=3) as observer:
            source._fixed_rope(torch.tensor([1]),None,None,Audit())
            source._fixed_rope(torch.tensor([2,3]),None,None,Audit())
            records=observer.flush()
            self.assertEqual({row['op_name'] for row in records},{'query_rope','key_rope'})
            self.assertEqual([row['count'] for row in records],[1,2])
            self.assertTrue(all(row['rope_site_pair_complete'] for row in records))

    def test_actual_native_cpu_observer_on_off_noninterference(self):
        from numerical_reference.model_compat import production_module
        from numerical_reference import gpu_reference
        source=production_module();torch.manual_seed(20261019)
        rope_raw=torch.randint(-4000,4001,(1,2,1,128),dtype=torch.int64)
        cos=torch.randint(-65536,65537,(1,2,64),dtype=torch.int64)
        sin=torch.randint(-65536,65537,(1,2,64),dtype=torch.int64)
        query=torch.randint(-5000,5001,(1,2,1,128),dtype=torch.int32)
        kval=torch.randint(-2047,2048,(1,2,1,4,32),dtype=torch.int16)
        code=torch.full((1,2,1,4),123,dtype=torch.uint8)
        shift=torch.full((1,2,1,4),20,dtype=torch.uint8)
        cache=source.KV12(kval,code,shift)
        score=torch.tensor([[0,-513,-1025],[0,0,0]],dtype=torch.int64)
        mask=torch.tensor([[True,True,False],[False,False,False]])
        from model.fixbit_v2 import build_softmax_exp_lut_u17
        lut=torch.tensor(build_softmax_exp_lut_u17(),dtype=torch.int64)
        probability=torch.tensor([[[[65535,0],[32768,32767]]]],dtype=torch.int64)
        tensors=[rope_raw,cos,sin,query,kval,code,shift,score,mask,lut,probability]
        frozen=[value.clone() for value in tensors]
        calls=[('_fixed_rope',lambda audit:(rope_raw,cos,sin,audit)),
               ('_qk_scores_s20',lambda audit:(query,cache,1,audit)),
               ('_softmax_u16',lambda audit:(score,mask,lut)),
               ('_pv_s24',lambda audit:(probability,cache,1,audit))]
        for name,make_args in calls:
            baseline_audit=source.V5Audit(torch.device('cpu'))
            expected=getattr(source,name)(*make_args(baseline_audit))
            observed_audit=source.V5Audit(torch.device('cpu'))
            with local_observer_context(source,backend=gpu_reference,doc_id='native',layer=0,track_linear_modules=False) as observer:
                with observer.operation('native_'+name):
                    result=getattr(source,name)(*make_args(observed_audit))
                records=observer.flush()
            self.assertTrue(torch.equal(expected,result),name)
            self.assertEqual(baseline_audit.collect(),observed_audit.collect(),name)
            self.assertEqual(len(records),1)
            self.assertFalse(records[0]['exact_pre_output_comparison'])
            for original,before in zip(tensors,frozen):self.assertTrue(torch.equal(original,before),name)
        self.assertFalse(torch.cuda.is_initialized())

if __name__=='__main__':unittest.main()
