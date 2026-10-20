import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
from generation_core import decode_arm, generation_budget, pair_summary, read_prompts, token_identity


class ControlsTest(unittest.TestCase):
    def test_independent_prefixes_and_equal_budget(self):
        prefixes=[]
        def step_a(prefix,first):
            prefixes.append(('a',prefix))
            return (9 if first else 2),{}
        def step_b(prefix,first):
            prefixes.append(('b',prefix))
            return (8 if first else 2),{}
        a=decode_arm([1,3],step_a,{2},5,20)
        b=decode_arm([1,3],step_b,{2},5,20)
        self.assertEqual(prefixes,[('a',[1,3]),('a',[1,3,9]),('b',[1,3]),('b',[1,3,8])])
        self.assertTrue(a['eos_seen'] and b['eos_seen'])
        self.assertFalse(a['truncated'])
        self.assertEqual(pair_summary(a,b)['first_divergence_index'],0)

    def test_cap_is_explicit(self):
        a=decode_arm([1],lambda p,f:(7,{}),{2},3,5)
        self.assertEqual(a['generated_token_ids'],[7,7,7])
        self.assertEqual(a['stop_reason'],'max_new_tokens')
        self.assertTrue(a['truncated'])
        with self.assertRaises(ValueError):
            generation_budget(4,5,2)

    def test_prompt_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.jsonl'
            p.write_text(json.dumps(dict(id='x',prompt='hello'))+'\n')
            self.assertEqual(read_prompts(p)[0]['prompt_id'],'x')
            p.write_text(json.dumps(dict(id='x',prompt='hello',prompt_sha256='bad'))+'\n')
            with self.assertRaises(ValueError):read_prompts(p)
        self.assertEqual(token_identity([1,2]),token_identity([1,2]))
        self.assertNotEqual(token_identity([1,2]),token_identity([2,1]))


class ArithmeticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from numerical_reference.model_compat import production_module
        torch.set_num_threads(1)
        cls.torch=torch
        cls.v5=production_module()

    def test_quantization_is_independent_per_token(self):
        t=self.torch
        generator=t.Generator().manual_seed(73)
        raw=t.randint(-(1<<23),(1<<23)-1,(1,7,8,128),generator=generator,dtype=t.int32)
        audit=self.v5.V5Audit(t.device('cpu'))
        whole=self.v5._kv12_quantize(raw,audit)
        split=[self.v5._kv12_quantize(raw[:,start:stop],audit) for start,stop in ((0,3),(3,7))]
        for field in ('values_s12','codes_u8','shifts_u8'):
            self.assertTrue(t.equal(getattr(whole,field),t.cat([getattr(x,field) for x in split],dim=1)))
        values=t.randint(-(1<<22),(1<<22)-1,(1,7,4096),generator=generator,dtype=t.int64)
        a=self.v5.prepare_fixed_activation(values,input_width=24,hadamard_width=28,audit=audit)
        chunks=[self.v5.prepare_fixed_activation(values[:,start:stop],input_width=24,hadamard_width=28,audit=audit) for start,stop in ((0,3),(3,7))]
        for field in ('values_u8','codes_u8','shifts_u8','zero_points_u8'):
            self.assertTrue(t.equal(getattr(a,field),t.cat([getattr(x,field) for x in chunks],dim=0)))

    def test_rope_extension_keeps_128_entries(self):
        from cached_adapter import extend_rope
        config=json.loads(Path('/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct/config.json').read_text())
        c,s,record=extend_rope(self.v5,config,2048,self.torch.device('cpu'))
        self.assertEqual(c.shape,(2048,64))
        self.assertEqual(s.shape,(2048,64))
        self.assertTrue(record['first128_bitwise_equal'])
        self.assertFalse(self.torch.cuda.is_initialized())

if __name__=='__main__':unittest.main()
