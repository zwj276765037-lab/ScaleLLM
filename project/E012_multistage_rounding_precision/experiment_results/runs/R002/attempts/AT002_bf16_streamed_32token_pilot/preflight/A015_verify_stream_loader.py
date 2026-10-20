"""Independent CPU semantic check of A016's streaming loader; no GPU allowed."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import importlib
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
import torch
from safetensors import safe_open
from safetensors.torch import save_file
from transformers import AutoModelForCausalLM, LlamaConfig

EXPERIMENT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment')
sys.path.insert(0, str(EXPERIMENT))
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
assert not torch.cuda.is_initialized()
module = importlib.import_module('capture_real_inputs')
loader = module.load_streamed_bf16_model
start = time.monotonic()
checks = []
for tied in (False, True):
    torch.manual_seed(20261019)
    config = LlamaConfig(vocab_size=97, hidden_size=32, intermediate_size=64,
                         num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                         max_position_embeddings=64, attention_dropout=0.0,
                         tie_word_embeddings=tied)
    source = AutoModelForCausalLM.from_config(config, dtype=torch.bfloat16,
                                             attn_implementation='eager').eval()
    with tempfile.TemporaryDirectory(prefix='A015_stream_loader_') as directory:
        directory = Path(directory)
        config.to_json_file(directory/'config.json', use_diff=False)
        # Clone only this tiny model to provide a causal checkpoint with model.* prefix.
        checkpoint = {name: value.detach().clone() for name, value in source.state_dict().items()}
        keys = sorted(checkpoint)
        partitions = [keys[::2], keys[1::2]]
        weight_map = {}
        for index, selected in enumerate(partitions, 1):
            filename = f'model-{index:05d}-of-00002.safetensors'
            save_file({key: checkpoint[key] for key in selected}, directory/filename,
                      metadata={'format': 'pt'})
            weight_map.update({key: filename for key in selected})
        (directory/'model.safetensors.index.json').write_text(json.dumps({
            'metadata': {'total_size': sum(x.numel()*x.element_size() for x in checkpoint.values())},
            'weight_map': weight_map}))
        stage_dir = directory/'stages'
        stage_dir.mkdir()
        loaded = loader(directory, 'cpu', stage_dir)
        if isinstance(loaded, tuple):
            loaded = loaded[0]
        expected = dict(source.model.named_parameters(remove_duplicate=False))
        actual = dict(loaded.named_parameters(remove_duplicate=False))
        assert set(actual) == set(expected), (set(actual)-set(expected), set(expected)-set(actual))
        for name in expected:
            assert actual[name].device.type == 'cpu', name
            assert actual[name].dtype == torch.bfloat16, (name, actual[name].dtype)
            assert actual[name].shape == expected[name].shape, name
            assert torch.equal(actual[name], expected[name]), name
        buffers = dict(loaded.named_buffers())
        reference_buffers = dict(source.model.named_buffers())
        assert set(buffers) == set(reference_buffers)
        for name, value in buffers.items():
            assert value.dtype == torch.float32, (name, value.dtype)
            assert value.device.type == 'cpu', name
            assert torch.equal(value, reference_buffers[name]), name
        inputs = torch.tensor([[1,2,3,4,5]], dtype=torch.int64)
        with torch.inference_mode():
            reference = source.model(input_ids=inputs, use_cache=False).last_hidden_state
            observed = loaded(input_ids=inputs, use_cache=False).last_hidden_state
        assert torch.equal(reference, observed), torch.max(torch.abs(reference-observed)).item()
        # Verify exact bytes of selected original checkpoint rows, not only dtype.
        matrix = 'model.layers.0.self_attn.q_proj.weight'
        with safe_open(directory/weight_map[matrix], framework='pt', device='cpu') as handle:
            expected_rows = handle.get_tensor(matrix)[[0,3,7]].contiguous().view(torch.uint8)
            actual_rows = actual[matrix.removeprefix('model.')].detach()[[0,3,7]].contiguous().view(torch.uint8)
            assert torch.equal(expected_rows, actual_rows)
        checks.append({'tied_checkpoint_config': tied, 'base_parameter_count': len(actual),
                       'checkpoint_keys': len(keys), 'skipped_lm_head': 'lm_head.weight' in keys,
                       'parameter_exact_equal': True, 'all_bf16': True,
                       'buffers': {name: {'dtype': str(value.dtype), 'shape': list(value.shape)} for name,value in buffers.items()},
                       'forward_bit_equal': True, 'selected_rows_byte_equal': True})
assert not torch.cuda.is_initialized()
print(json.dumps({'checks': checks, 'wall_seconds': time.monotonic()-start,
                  'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'cuda_initialized': torch.cuda.is_initialized(),
                  'python': sys.executable}, sort_keys=True))
