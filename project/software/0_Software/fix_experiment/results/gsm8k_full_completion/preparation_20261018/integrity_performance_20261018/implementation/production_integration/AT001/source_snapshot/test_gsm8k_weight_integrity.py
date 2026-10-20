"""CPU execution and corruption controls for the complete static-content guard."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
import torch
from safetensors.torch import save_file
from gsm8k_protocol import canonical_hash,sha256_file
from gsm8k_weight_integrity import StaticContentIntegrity,IntegrityError,tensor_descriptor
from run_eval_worker import REFERENCE_QDQ_DIR
sys.path.insert(0,str(REFERENCE_QDQ_DIR))
from mlp4_method_inference import ScalePathIAHFP16ScaleLinear,ScalePathIAHFP32ScaleLinear,ScalePathIAHScaleCodeLinear
import scalepath4_method_inference as scalepath


class Tiny(torch.nn.Module):
    def __init__(self, tied=False, rope=False):
        super().__init__()
        self.proj=torch.nn.Linear(32,64,bias=True,dtype=torch.bfloat16)
        self.register_buffer('persistent',torch.tensor(2.,dtype=torch.bfloat16))
        if tied:
            self.alias=self.proj
        if rope:
            from transformers import LlamaConfig
            from transformers.models.llama.modeling_llama import LlamaRotaryEmbedding
            self.rotary_emb=LlamaRotaryEmbedding(config=LlamaConfig(hidden_size=32,num_attention_heads=2,head_dim=16),device='cpu')


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        scalepath._H_CACHE={}
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.model=Tiny()
        self.identity={'case':'bf16','stage':'smoke','plan_sha256':'p','model_fingerprint_sha256':'m','gpu_uuid':'test-cpu'}
    def tearDown(self):
        scalepath._H_CACHE={};self.temp.cleanup()
    def fixture(self,model=None,case=None):
        model=model or self.model
        path=self.root/'checkpoint';path.mkdir()
        # Tied duplicate aliases are intentionally absent from file storage.
        tensors={name:tensor.detach().contiguous().clone() for name,tensor in model.named_parameters()}
        for name,tensor in model.named_buffers():
            owner,_,attr=name.rpartition('.')
            if 'rotary_emb' not in name:tensors[name]=tensor.detach().contiguous().clone()
        save_file(tensors,str(path/'model.safetensors'))
        (path/'config.json').write_text('{}')
        files=[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted(path.iterdir())]
        out=self.root/'attempt';out.mkdir()
        identity=dict(self.identity)
        if case:identity['case']=case
        guard=StaticContentIntegrity(path,{'files':files},out,identity,device='cpu')
        return guard,model,path,out
    def load(self,guard,model):
        guard.observe('cpu_loaded',model);guard.observe('gpu_loaded',model)
    def freeze(self,guard,model):
        self.load(guard,model);guard.observe('attached',model);guard.check('setup_complete')
    def test_full_positive_and_all_phases(self):
        guard,model,_,out=self.fixture();self.freeze(guard,model)
        guard.check('verification_before');guard.check('verification_after')
        guard.check('sample:train:0000:before');guard.check('sample:train:0000:after')
        ref=guard.finish();data=json.loads((out/'integrity.json').read_text())
        self.assertTrue(data['qualified']);self.assertEqual(ref['sha256'],sha256_file(out/'integrity.json'))
        self.assertEqual(data['coverage']['checkpoint_names'],data['coverage']['effective_static_names'])
        self.assertEqual(data['baseline_root_sha256'],canonical_hash(data['baseline_manifest']))
        self.assertEqual(data['phase_checks'],[json.loads(line) for line in (out/'integrity_checks.jsonl').read_text().splitlines()])
    def test_cpu_parameter_corruption_rejected(self):
        guard,model,_,_=self.fixture();model.proj.weight.data[0,0]+=1
        with self.assertRaises(IntegrityError):guard.observe('cpu_loaded',model)
    def test_gpu_copy_parameter_corruption_rejected(self):
        guard,model,_,_=self.fixture();guard.observe('cpu_loaded',model);model.proj.weight.data[0,0]+=1
        with self.assertRaises(IntegrityError):guard.observe('gpu_loaded',model)
    def test_version_counter_is_not_a_content_proxy(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model);version=model.proj.weight._version
        model.proj.weight.data[0,0]+=1
        self.assertEqual(model.proj.weight._version,version)
        with self.assertRaises(IntegrityError):guard.check('sample:train:0000:after')
    def test_equal_content_new_parameter_identity_rejected(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model)
        model.proj.weight=torch.nn.Parameter(model.proj.weight.detach().clone())
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_buffer_content_corruption_rejected(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model);model.persistent.add_(1)
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_missing_tensor_rejected(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model);del model.proj.bias
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_unexpected_tensor_rejected(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model);model.register_buffer('unknown',torch.ones(1))
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_static_dtype_and_stride_identity_rejected(self):
        guard,model,_,_=self.fixture();self.freeze(guard,model)
        model.proj.weight.data=model.proj.weight.data.t().contiguous().t()
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_checkpoint_file_changed_after_verification_rejected(self):
        guard,model,path,_=self.fixture();(path/'config.json').write_text('{"changed":true}')
        with self.assertRaises(IntegrityError):guard.observe('cpu_loaded',model)
    def test_checkpoint_file_changed_before_terminal_rejected(self):
        guard,model,path,_=self.fixture();self.freeze(guard,model);(path/'config.json').write_text('{"changed":true}')
        with self.assertRaises(IntegrityError):guard.finish()
    def test_tied_parameter_alias_covered(self):
        guard,model,_,_=self.fixture(Tiny(tied=True));self.freeze(guard,model)
        self.assertEqual(guard.data['checkpoint_key_map']['alias.weight'],'proj.weight')
    def test_generated_rope_rebuilt_and_guarded(self):
        guard,model,_,_=self.fixture(Tiny(rope=True));self.freeze(guard,model)
        self.assertEqual(guard.data['baseline_manifest']['rotary_emb.inv_freq']['role'],'derived_static_buffer')
        model.rotary_emb.inv_freq.add_(1)
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_unknown_derived_buffer_rejected(self):
        model=Tiny();model.register_buffer('surprise',torch.ones(1),persistent=False)
        guard,model,path,_=self.fixture(model)
        # Remove it from checkpoint while preserving the declared new file identity.
        tensors={'proj.weight':model.proj.weight.detach().clone(),'proj.bias':model.proj.bias.detach().clone(),'persistent':model.persistent.clone()}
        save_file(tensors,str(path/'model.safetensors'))
        guard.reader.identity['files']=[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted(path.iterdir())]
        guard.reader.key_to_file={name:'model.safetensors' for name in tensors}
        with self.assertRaises(IntegrityError):guard.observe('cpu_loaded',model)
    def attach(self,guard,model,cls):
        self.load(guard,model)
        kwargs=dict(module_name='proj',op_name='up_proj',hadamard_block=32,group_size=32,act_bits=8,weight_bits=4,compute_dtype=torch.bfloat16)
        if cls is ScalePathIAHScaleCodeLinear:kwargs['scale_code_bits']=8
        model.proj=cls(model.proj,**kwargs)
        guard.observe('attached',model);guard.check('setup_complete')
    def test_all_three_original_qdq_constructors_fullshape_rebuild(self):
        for cls,case in [(ScalePathIAHFP16ScaleLinear,'a8w4_fp16'),(ScalePathIAHFP32ScaleLinear,'a8w4_fp32'),(ScalePathIAHScaleCodeLinear,'reference_qdq')]:
            with self.subTest(case=case):
                # Each independent subcase gets its own source/output and cache.
                scalepath._H_CACHE={}
                sub=self.root/case;sub.mkdir();old=self.root;self.root=sub
                guard,model,_,_=self.fixture(Tiny(),case);self.attach(guard,model,cls)
                self.assertTrue(guard.data['coverage']['external_cache_names'])
                self.assertIn('proj.weight',guard.data['coverage']['qdq_rebuilt_names'])
                guard.check('verification_before');guard.check('verification_after');guard.finish()
                self.root=old
    def test_effective_nonpersistent_qdq_buffer_corruption_rejected(self):
        guard,model,_,_=self.fixture(case='a8w4_fp32');self.attach(guard,model,ScalePathIAHFP32ScaleLinear)
        self.assertNotIn('proj.weight',dict(model.named_parameters()))
        model.proj.weight.add_(1)
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_qdq_already_corrupt_before_rebuild_rejected(self):
        guard,model,_,_=self.fixture(case='a8w4_fp32');self.load(guard,model)
        model.proj=ScalePathIAHFP32ScaleLinear(model.proj,module_name='proj',op_name='up_proj',hadamard_block=32,group_size=32,act_bits=8,weight_bits=4,compute_dtype=torch.bfloat16)
        model.proj.weight.add_(1)
        with self.assertRaises(IntegrityError):guard.observe('attached',model)
    def test_external_hadamard_cache_content_corruption_rejected(self):
        guard,model,_,_=self.fixture(case='a8w4_fp32');self.attach(guard,model,ScalePathIAHFP32ScaleLinear)
        next(iter(scalepath._H_CACHE.values())).add_(1)
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_external_hadamard_cache_new_entry_rejected(self):
        guard,model,_,_=self.fixture(case='a8w4_fp32');self.attach(guard,model,ScalePathIAHFP32ScaleLinear)
        scalepath.hadamard(64,torch.device('cpu'),torch.float32)
        with self.assertRaises(IntegrityError):guard.check('verification_after')
    def test_bf16_does_not_adopt_unrelated_global_cache(self):
        scalepath.hadamard(32,torch.device('cpu'),torch.float32)
        guard,model,_,_=self.fixture();self.freeze(guard,model)
        self.assertEqual(guard.data['coverage']['external_cache_names'],[])
    def test_scalar_tensor_full_bytes(self):
        self.assertEqual(tensor_descriptor(torch.tensor(1.,dtype=torch.bfloat16),'buffer')['shape'],[])
    def test_bad_phase_order_rejected(self):
        guard,model,_,_=self.fixture()
        with self.assertRaises(IntegrityError):guard.observe('gpu_loaded',model)

if __name__=='__main__':unittest.main()
