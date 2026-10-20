import sys
from pathlib import Path
import unittest
import tempfile
import json
import hashlib
from unittest.mock import patch
import torch
from transformers import AutoModel,LlamaConfig
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from numerical_reference.model_compat import attention_geometry,v5_original_proxy,wrap_hf5_attention,normalize_attention_mask,production_module,attachment_context,attach_v5_fullchain_compatible

class NumericalCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
    def test_geometry_and_tiny_hf5_forward_adapter(self):
        config=LlamaConfig(vocab_size=37,hidden_size=32,intermediate_size=64,num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,max_position_embeddings=64)
        model=AutoModel.from_config(config,dtype=torch.bfloat16,attn_implementation='eager').eval()
        class Core(torch.nn.Module):
            def __init__(self,original):super().__init__();self.original=original;self.seen=None
            def forward(self,**kwargs):
                self.seen=kwargs['attention_mask']
                kwargs.pop('past_key_value',None)
                a,b=self.original(**kwargs)
                return a,b,None
        cores=[]
        for layer in model.layers:
            proxy=v5_original_proxy(layer.self_attn)
            self.assertEqual(proxy.num_heads,4);self.assertEqual(proxy.num_key_value_heads,2)
            self.assertEqual(attention_geometry(layer.self_attn)['hidden_size'],32)
            core=Core(layer.self_attn);cores.append(core)
            layer.self_attn=wrap_hf5_attention(core)
        with torch.inference_mode():out=model(input_ids=torch.tensor([[1,2,3]]),use_cache=False).last_hidden_state
        self.assertEqual(tuple(out.shape),(1,3,32))
        self.assertFalse(torch.cuda.is_initialized())
    def test_cache_and_mask_contract(self):
        class Core(torch.nn.Module):
            def forward(self,**kwargs):return kwargs['hidden_states'],None,None
        wrapped=wrap_hf5_attention(Core())
        for kw in ({'use_cache':True},{'past_key_values':object()},{'past_key_value':object()}):
            with self.assertRaises(ValueError):wrapped(torch.zeros(1,1,2),**kw)
        mask=normalize_attention_mask(torch.tensor([[[[True,False]]]]))
        self.assertEqual(mask[0,0,0,0].item(),0);self.assertTrue(torch.isneginf(mask[0,0,0,1]))
        with self.assertRaises(ValueError):normalize_attention_mask(torch.ones(2,2))
        with self.assertRaises(ValueError):normalize_attention_mask(torch.ones(1,1,2,2))


    def test_attach_context_restoration_and_explicit_format05(self):
        v5=production_module()
        original=v5.V5Attention
        with attachment_context(v5) as same:
            self.assertIs(same,v5);self.assertIsNot(same.V5Attention,original)
        self.assertIs(v5.V5Attention,original)
        with self.assertRaises(RuntimeError):
            with attachment_context(v5):raise RuntimeError('exercise restore')
        self.assertIs(v5.V5Attention,original)
        seen={}
        def fake_attach(model,**kwargs):seen.update(kwargs);return {'ok':True},None
        with tempfile.TemporaryDirectory(prefix='A015_compat_') as directory:
            config_path=Path(directory)/'config.json'
            config_path.write_text(json.dumps({'rope_theta':500000,'rope_scaling':{'rope_type':'llama3'}}))
            with patch.object(v5,'attach_v5_fullchain',fake_attach):
                result=attach_v5_fullchain_compatible(object(),checkpoint_dir=Path(directory),device='cpu')
            self.assertEqual(result[0]['rope_config_adapter']['source']['sha256'],hashlib.sha256(config_path.read_bytes()).hexdigest())
        self.assertTrue(result[0]['ok']);self.assertTrue(seen['down_shift12_candidate'])
        self.assertEqual(seen['down_output_width'],32);self.assertFalse(seen['software_extended'])
        with self.assertRaises(ValueError):
            attach_v5_fullchain_compatible(object(),checkpoint_dir=Path('/tmp'),device='cpu',down_output_width=24)
        self.assertFalse(torch.cuda.is_initialized())


    def test_original_rope_config_bridge_exact_tables_and_restoration(self):
        raw=dict(rope_theta=500000.0,rope_scaling=dict(rope_type='llama3',factor=8.0,
                     low_freq_factor=1.0,high_freq_factor=4.0,original_max_position_embeddings=8192))
        config=LlamaConfig(**raw)
        before=json.dumps(config.to_dict(),sort_keys=True)
        v5=production_module();original=v5._rope_tables
        expected=original(raw,torch.device('cpu'))
        with attachment_context(v5,rope_config=raw):
            actual=v5._rope_tables(config,torch.device('cpu'))
            for first,second in zip(expected,actual):
                self.assertTrue(torch.equal(first,second))
                self.assertEqual(first.numpy().tobytes(),second.numpy().tobytes())
        self.assertIs(v5._rope_tables,original)
        self.assertEqual(json.dumps(config.to_dict(),sort_keys=True),before)
        with self.assertRaises(RuntimeError):
            with attachment_context(v5,rope_config=raw):raise RuntimeError('restore rope after failure')
        self.assertIs(v5._rope_tables,original)
        self.assertFalse(torch.cuda.is_initialized())

if __name__=='__main__':unittest.main()
