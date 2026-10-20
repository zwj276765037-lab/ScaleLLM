"""Fail-closed checkpoint/CPU/GPU and effective static-tensor identity guards.

This module observes the original BF16 loader and original full-shape GPU QDQ
constructors. It does not alter weights, quantization arithmetic, or generation.
"""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from gsm8k_protocol import INTEGRITY_CONTRACT_ID, atomic_json, canonical_hash, sha256_file

SCHEMA = 'scalellm_gsm8k_weight_integrity_v1'
QDQ_CLASSES = {'ScalePathIAHScaleCodeLinear', 'ScalePathIAHFP16ScaleLinear', 'ScalePathIAHFP32ScaleLinear'}


class IntegrityError(RuntimeError):
    pass


def tensor_descriptor(tensor: Any, role: str) -> dict[str, Any]:
    import torch
    # .cpu() is deliberately blocking. No version-counter or sampled-content proxy.
    if tensor.device.type == 'cuda':
        torch.cuda.synchronize(tensor.device)
    value = tensor.detach().contiguous().cpu()
    digest = hashlib.sha256(value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()
    return {'sha256': digest, 'shape': list(value.shape), 'dtype': str(value.dtype), 'role': role}


def storage_identity(tensor: Any) -> dict[str, Any]:
    return {'object_id': id(tensor), 'data_ptr': tensor.data_ptr(),
            'storage_base_ptr': tensor.untyped_storage().data_ptr(),
            'storage_offset': tensor.storage_offset(), 'stride': list(tensor.stride()),
            'device': str(tensor.device), 'shape': list(tensor.shape), 'dtype': str(tensor.dtype)}


def model_tensors(model: Any) -> dict[str, tuple[Any, str]]:
    result = {name: (value, 'parameter') for name, value in model.named_parameters(remove_duplicate=False)}
    for name, value in model.named_buffers(remove_duplicate=False):
        if name in result:
            raise IntegrityError(f'parameter/buffer name collision: {name}')
        result[name] = (value, 'static_buffer')
    return result


class CheckpointTensors:
    """Read verified safetensors, retaining no whole-model CPU/GPU duplicate."""
    def __init__(self, model: Path, identity: dict[str, Any]):
        self.root, self.identity = Path(model), identity
        files = {row['name'] for row in identity['files']}
        index = self.root / 'model.safetensors.index.json'
        if index.name in files:
            self.key_to_file = json.loads(index.read_text())['weight_map']
        else:
            from safetensors import safe_open
            shards = sorted(name for name in files if name.endswith('.safetensors'))
            if len(shards) != 1:
                raise IntegrityError('integrity requires an unambiguous safetensors tensor index')
            with safe_open(str(self.root / shards[0]), framework='pt', device='cpu') as handle:
                self.key_to_file = {name: shards[0] for name in handle.keys()}
        if not self.key_to_file or any(name not in files or Path(name).name != name for name in self.key_to_file.values()):
            raise IntegrityError('checkpoint tensor index is outside verified files')

    def verify_files(self):
        expected = self.identity['files']
        if sorted(row['name'] for row in expected) != sorted(p.name for p in self.root.iterdir() if p.is_file()):
            raise IntegrityError('checkpoint file inventory changed during execution')
        for row in expected:
            path = self.root / row['name']
            if path.stat().st_size != row['bytes'] or sha256_file(path) != row['sha256']:
                raise IntegrityError(f'checkpoint file identity changed: {row["name"]}')

    def get(self, name: str, dtype: Any) -> Any:
        from safetensors import safe_open
        if name not in self.key_to_file:
            raise IntegrityError(f'checkpoint tensor absent: {name}')
        with safe_open(str(self.root / self.key_to_file[name]), framework='pt', device='cpu') as handle:
            # Conversion follows the original CPU loader dtype, never a CPU QDQ transform.
            return handle.get_tensor(name).to(dtype=dtype)


class StaticContentIntegrity:
    def __init__(self, model_path: Path, model_identity: dict[str, Any], output: Path,
                 identity: dict[str, Any], *, device: str):
        self.output = Path(output)
        self.identity = dict(identity)
        self.device = device
        self.reader = CheckpointTensors(model_path, model_identity)
        self.model = None
        self.cpu_storage = {}
        self.runtime_storage = {}
        self.roles = {}
        self.qdq_modules = {}
        self.checks = []
        self.cache_module = None
        self.data = {'schema': SCHEMA, 'contract_id': INTEGRITY_CONTRACT_ID,
                     'state': 'running', 'qualified': False, 'identity': self.identity,
                     'checkpoint_manifest': {}, 'checkpoint_key_map': {}, 'baseline_manifest': {},
                     'coverage': {'checkpoint_tensor_names': sorted(self.reader.key_to_file)},
                     'dynamic_state_policy': {
                         'native_kv': 'Explicit native DynamicCache forward state is outside registered parameters/buffers and is verified by native_cache_call_parity_v2.',
                         'rope': 'All six frozen models use default/llama3 static RoPE. Every registered RoPE buffer is guarded; unqualified dynamic/longrope types are rejected.',
                         'unregistered_static_cache': 'scalepath4_method_inference._H_CACHE is inventoried and guarded explicitly.'},
                     'qdq_reconstruction': [], 'source_sha256': sha256_file(Path(__file__))}
        self.log_path = self.output / 'integrity_checks.jsonl'
        self.log_path.touch(exist_ok=False)
        self._save()

    def _save(self, terminal=False):
        value = dict(self.data)
        value['phase_count'] = len(self.checks)
        if terminal:
            value['phase_checks'] = self.checks
            value['checks_jsonl_sha256'] = sha256_file(self.log_path)
        atomic_json(self.output / 'integrity.json', value)

    def fail(self, error: BaseException):
        self.data.update(state='failed', qualified=False, error={'type': type(error).__name__, 'message': str(error)})
        self._save(terminal=True)

    def _phase(self, label, observed, trusted, *, identity_errors=None, loading=False):
        exact = observed == trusted and not identity_errors
        row = {'label': label, 'complete': True, 'exact': bool(exact),
               'checked_names': sorted(observed), 'observed_root_sha256': canonical_hash(observed)}
        if loading:
            row['trusted_root_sha256'] = canonical_hash(trusted)
        if not exact:
            row['missing_names'] = sorted(set(trusted) - set(observed))
            row['unexpected_names'] = sorted(set(observed) - set(trusted))
            row['changed_names'] = sorted(name for name in set(observed) & set(trusted) if observed[name] != trusted[name])
            row['identity_errors'] = identity_errors or []
        self.checks.append(row)
        with self.log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
            handle.flush(); os.fsync(handle.fileno())
        self._save()
        if not exact:
            error = IntegrityError(f'static-content integrity failed at {label}: {row}')
            self.fail(error)
            raise error

    def observe(self, stage: str, model: Any):
        """Read-only observer for load_model(args, integrity_observer=None)."""
        try:
            if stage == 'cpu_loaded':
                self._cpu_loaded(model)
            elif stage == 'gpu_loaded':
                self._gpu_loaded(model)
            elif stage == 'attached':
                self._attached(model)
            else:
                raise IntegrityError(f'unknown loader observer stage: {stage}')
        except BaseException as exc:
            self.fail(exc)
            raise

    def _cpu_loaded(self, model):
        if self.checks:
            raise IntegrityError('CPU load observation repeated or out of order')
        self.reader.verify_files()
        tensors = model_tensors(model)
        if not tensors:
            raise IntegrityError('empty loaded model tensor inventory')
        # Tied aliases may be omitted from a checkpoint, but must reference the
        # same actual CPU tensor as a recorded checkpoint name.
        aliases = {}
        for name, (tensor, role) in tensors.items():
            aliases.setdefault(id(tensor), []).append(name)
        modules = dict(model.named_modules())
        derived_modules = {}
        expected, actual, keymap = {}, {}, {}
        for name, (tensor, role) in sorted(tensors.items()):
            if tensor.device.type != 'cpu':
                raise IntegrityError(f'CPU checkpoint stage contains a non-CPU tensor: {name}')
            key = name if name in self.reader.key_to_file else next(
                (alias for alias in aliases[id(tensor)] if alias in self.reader.key_to_file), None)
            if key is not None:
                reference = self.reader.get(key, tensor.dtype)
            elif role == 'static_buffer':
                owner_name, _, attr = name.rpartition('.')
                owner = modules[owner_name]
                if (attr not in {'inv_freq', 'original_inv_freq'} or
                        not type(owner).__name__.endswith('RotaryEmbedding') or
                        not type(owner).__module__.startswith('transformers.models.') or
                        getattr(owner, 'rope_type', None) not in {'default', 'llama3'}):
                    raise IntegrityError(f'unqualified checkpoint-derived buffer: {name}')
                if owner_name not in derived_modules:
                    derived_modules[owner_name] = type(owner)(config=copy.deepcopy(owner.config), device='cpu')
                reference = getattr(derived_modules[owner_name], attr).to(dtype=tensor.dtype)
                role = 'derived_static_buffer'
            else:
                raise IntegrityError(f'loaded parameter absent from checkpoint: {name}')
            keymap[name] = key
            expected[name] = tensor_descriptor(reference, role)
            actual[name] = tensor_descriptor(tensor, role)
            self.roles[name] = role
            self.cpu_storage[name] = storage_identity(tensor)
        if {key for key in keymap.values() if key is not None} != set(self.reader.key_to_file):
            raise IntegrityError('checkpoint contains unconsumed tensor keys')
        self.data.update(checkpoint_manifest=expected, checkpoint_key_map=keymap)
        self.data['coverage'].update(checkpoint_names=sorted(expected), cpu_checked_names=sorted(actual))
        self._phase('cpu_loaded', actual, expected, loading=True)

    def _gpu_loaded(self, model):
        if [row['label'] for row in self.checks] != ['cpu_loaded']:
            raise IntegrityError('GPU load observation out of order')
        actual = {}
        for name, (tensor, role) in sorted(model_tensors(model).items()):
            if str(tensor.device) != self.device:
                raise IntegrityError(f'loaded tensor is on unexpected device: {name}: {tensor.device}')
            actual[name] = tensor_descriptor(tensor, self.roles.get(name, role))
        self.data['coverage']['gpu_checked_names'] = sorted(actual)
        self._phase('gpu_loaded', actual, self.data['checkpoint_manifest'], loading=True)

    def _cache_entries(self):
        if self.cache_module is None:
            return {}
        out = {}
        for key, tensor in self.cache_module._H_CACHE.items():
            if not isinstance(key, tuple) or len(key) != 3:
                raise IntegrityError('unexpected Hadamard cache key')
            name = 'external_cache:scalepath4_method_inference._H_CACHE:' + json.dumps([str(v) for v in key], separators=(',', ':'))
            out[name] = tensor
        return out

    def _attached(self, model):
        import torch
        if [row['label'] for row in self.checks] != ['cpu_loaded', 'gpu_loaded']:
            raise IntegrityError('attached observation out of order')
        self.model = model
        for name, module in model.named_modules():
            if type(module).__module__ in {'mlp4_method_inference', 'scalepath4_method_inference'}:
                if type(module).__name__ not in QDQ_CLASSES:
                    raise IntegrityError(f'unqualified QDQ class: {name}')
                self.qdq_modules[name] = module
        if bool(self.qdq_modules) != (self.identity['case'] != 'bf16'):
            raise IntegrityError('actual QDQ coverage differs from case')
        rebuilt = {}
        if self.qdq_modules:
            self.cache_module = importlib.import_module('scalepath4_method_inference')
            # Materialize the original function's two effective cache dtypes before
            # freezing inventory: weight folding is FP32, native activations BF16.
            blocks = sorted({module.hadamard_block for module in self.qdq_modules.values()})
            for block in blocks:
                for dtype in (torch.float32, torch.bfloat16):
                    self.cache_module.hadamard(block, torch.device(self.device), dtype)
            actual_cache = self.cache_module._H_CACHE
            try:
                self.cache_module._H_CACHE = {}
                for key, tensor in actual_cache.items():
                    fresh = self.cache_module.hadamard(key[1], torch.device(key[0]), key[2])
                    name = 'external_cache:scalepath4_method_inference._H_CACHE:' + json.dumps([str(v) for v in key], separators=(',', ':'))
                    rebuilt[name] = tensor_descriptor(fresh, 'external_cache')
            finally:
                self.cache_module._H_CACHE = actual_cache
            for name, module in sorted(self.qdq_modules.items()):
                weight_name = name + '.weight'
                key = self.data['checkpoint_key_map'].get(weight_name)
                if key is None:
                    raise IntegrityError(f'QDQ source is not checkpoint-bound: {weight_name}')
                source_cpu = self.reader.get(key, module.weight.dtype)
                source = source_cpu.to(device=self.device)
                if tensor_descriptor(source, 'parameter') != self.data['checkpoint_manifest'][weight_name]:
                    raise IntegrityError(f'QDQ rebuild source copy differs from checkpoint: {weight_name}')
                bias_name = name + '.bias'
                bias_key = self.data['checkpoint_key_map'].get(bias_name)
                bias = self.reader.get(bias_key, module.weight.dtype).to(device=self.device) if bias_key else None
                if bias is not None and tensor_descriptor(bias, 'parameter') != self.data['checkpoint_manifest'][bias_name]:
                    raise IntegrityError(f'QDQ rebuild bias differs from checkpoint: {bias_name}')
                holder = SimpleNamespace(weight=source, bias=bias, in_features=module.in_features, out_features=module.out_features)
                kwargs = {attr: getattr(module, attr) for attr in ('module_name', 'op_name', 'hadamard_block', 'group_size', 'act_bits', 'weight_bits')}
                if hasattr(module, 'scale_code_bits'):
                    kwargs['scale_code_bits'] = module.scale_code_bits
                replacement = type(module)(holder, compute_dtype=module.weight.dtype, **kwargs)
                record = {'module': name, 'source_key': key, 'source_shape': list(source.shape),
                          'device': str(source.device), 'class': type(module).__name__, 'fullshape': True, 'tensors': {}}
                for attr, tensor in replacement.named_buffers(recurse=False):
                    target = name + '.' + attr
                    rebuilt[target] = tensor_descriptor(tensor, 'qdq_buffer')
                    record['tensors'][target] = rebuilt[target]
                self.data['qdq_reconstruction'].append(record)
                del replacement, holder, source, source_cpu, bias
                if self.device.startswith('cuda:'):
                    torch.cuda.empty_cache()
        actual = self._current_manifest()
        expected = {}
        checkpoint = self.data['checkpoint_manifest']
        for name, desc in checkpoint.items():
            if name in rebuilt:
                expected[name] = rebuilt[name]
            else:
                expected[name] = desc
        expected.update({name: desc for name, desc in rebuilt.items() if name not in expected})
        # Verify all surviving parameters and all effective (including nonpersistent)
        # buffers; unknown additions/removals are errors, never silent exclusions.
        if actual != expected:
            self._phase('qdq_rebuild', actual, expected, loading=True)
            raise IntegrityError('effective static inventory failed')
        self.data['baseline_manifest'] = expected
        self.data['baseline_root_sha256'] = canonical_hash(expected)
        self.data['coverage'].update(effective_static_names=sorted(expected),
            qdq_expected_names=sorted(rebuilt), qdq_rebuilt_names=sorted(rebuilt), external_cache_names=sorted(self._cache_entries()))
        self.runtime_storage = {name: storage_identity(tensor) for name, tensor in self._current_tensors().items()}
        self.data['runtime_storage_manifest'] = self.runtime_storage
        subset = {name: actual[name] for name in sorted(rebuilt)}
        self._phase('qdq_rebuild', subset, rebuilt, loading=True)

    def _current_tensors(self):
        out = {name: tensor for name, (tensor, role) in model_tensors(self.model).items()}
        out.update(self._cache_entries())
        return out

    def _current_manifest(self):
        result = {}
        for name, (tensor, default_role) in sorted(model_tensors(self.model).items()):
            owner, _, attr = name.rpartition('.')
            role = 'qdq_buffer' if owner in self.qdq_modules else self.roles.get(name, default_role)
            result[name] = tensor_descriptor(tensor, role)
        result.update({name: tensor_descriptor(tensor, 'external_cache') for name, tensor in self._cache_entries().items()})
        return result

    def check(self, label: str):
        if not self.data['baseline_manifest'] or self.data['state'] != 'running':
            raise IntegrityError('static content baseline unavailable or already terminal')
        current = self._current_tensors()
        errors = [name for name in set(current) & set(self.runtime_storage)
                  if storage_identity(current[name]) != self.runtime_storage[name]]
        self._phase(label, self._current_manifest(), self.data['baseline_manifest'], identity_errors=sorted(errors))

    def finish(self):
        self.reader.verify_files()
        self.check('stage_complete')
        self.data.update(state='complete', qualified=True)
        self._save(terminal=True)
        return {'path': 'integrity.json', 'sha256': sha256_file(self.output / 'integrity.json'),
                'contract_id': INTEGRITY_CONTRACT_ID, 'baseline_root_sha256': self.data['baseline_root_sha256'], 'qualified': True}
