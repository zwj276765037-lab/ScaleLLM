"""Experimental KV12 lifecycle and long RoPE adapter around unchanged V5 ops.

This is a software experiment, not a claim of a >128-key hardware interface.
Only per-token KV12 objects are retained. No floating-point KV is substituted.
"""
from __future__ import annotations
import hashlib
import numpy as np
import torch
import torch.nn as nn


def array_hash(tensor):
    return hashlib.sha256(tensor.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()


def extend_rope(v5, raw_config, max_context, device):
    if not 128 <= max_context <= 32768:
        raise ValueError('Experimental context must be between 128 and 32768')
    # These are the same production frequency and rounding functions. The only
    # change is the number of positions; all existing entries must match.
    inv_freq = v5.llama3_inv_freq(raw_config)
    angles = np.arange(max_context, dtype=np.float64)[:, None] * inv_freq[None, :]
    cos = np.clip(v5.numpy_round_away(np.cos(angles) * v5.Q16), -v5.Q16, v5.Q16)
    sin = np.clip(v5.numpy_round_away(np.sin(angles) * v5.Q16), -v5.Q16, v5.Q16)
    cos = torch.from_numpy(cos.astype(np.int32)).to(device)
    sin = torch.from_numpy(sin.astype(np.int32)).to(device)
    original = v5._rope_tables(raw_config, device)
    for actual, old in zip((cos, sin), original):
        if not torch.equal(actual[:128], old):
            raise ValueError('Extended RoPE changed a production entry')
    return cos, sin, dict(max_context=max_context, first128_bitwise_equal=True,
                         cos_sha256=array_hash(cos), sin_sha256=array_hash(sin),
                         algorithm='production llama3_inv_freq/numpy_round_away, float64 angles, Q16 int32',
                         deployment_scope='experimental software; production remains max128')


class CachedAttention(nn.Module):
    def __init__(self, core, v5, cos, sin, max_context):
        super().__init__()
        self.core = core
        self.v5 = v5
        # One shared table allocation, no alteration of the original core.
        self.cos = cos
        self.sin = sin
        self.max_context = max_context
        self.reset()

    def reset(self, enabled=True):
        self.key = self.value = None
        self.cache_enabled = enabled

    @property
    def cache_length(self):
        return 0 if self.key is None else self.key.values_s12.shape[1]

    def join(self, old, new):
        if old is None:
            return new
        return self.v5.KV12(*(torch.cat((getattr(old, n), getattr(new, n)), dim=1).contiguous()
                              for n in ('values_s12', 'codes_u8', 'shifts_u8')))

    def forward(self, hidden_states, position_ids=None, attention_mask=None,
                past_key_values=None, past_key_value=None, use_cache=False, **kwargs):
        del kwargs
        if use_cache or past_key_values is not None or past_key_value is not None:
            raise ValueError('Only adapter-owned KV12 caches are supported')
        c = self.core
        batch, tokens, _ = hidden_states.shape
        if batch != 1:
            raise ValueError('Response-quality experiment is unpadded batch1')
        offset = self.cache_length if self.cache_enabled else 0
        if offset + tokens > self.max_context:
            raise ValueError('Context limit exceeded')
        expected = torch.arange(offset, offset + tokens, device=hidden_states.device)[None, :]
        if position_ids is None:
            position_ids = expected
        if not torch.equal(position_ids, expected):
            raise ValueError('Positions must be the contiguous independently decoded prefix')
        if attention_mask is not None:
            raise ValueError('Adapter accepts only unpadded batch1 with its own causal mask')
        prepared = c.q_proj.prepare_float(hidden_states)
        query = c.q_proj.project_prepared(prepared).reshape(batch, tokens, c.num_heads, c.head_dim)
        key = c.k_proj.project_prepared(prepared).reshape(batch, tokens, c.num_key_value_heads, c.head_dim)
        value = c.v_proj.project_prepared(prepared).reshape(batch, tokens, c.num_key_value_heads, c.head_dim)
        cos, sin = self.cos[position_ids], self.sin[position_ids]
        query = self.v5._logical_to_interleaved_head(self.v5._fixed_rope(query, cos, sin, c.audit))
        key = self.v5._logical_to_interleaved_head(self.v5._fixed_rope(key, cos, sin, c.audit))
        key, value = self.v5._kv12_quantize(key, c.audit), self.v5._kv12_quantize(value, c.audit)
        if self.cache_enabled:
            key, value = self.join(self.key, key), self.join(self.value, value)
            self.key, self.value = key, value
        scores = self.v5._qk_scores_s20(query, key, c.num_key_value_groups, c.audit)
        valid = torch.arange(offset + tokens, device=hidden_states.device)[None, :] <= expected[0, :, None]
        valid = valid[None, None, :, :].expand(batch, c.num_heads, tokens, offset + tokens)
        probability = self.v5._softmax_u16(scores, valid, c.softmax_lut_u17)
        context = self.v5._pv_s24(probability, value, c.num_key_value_groups, c.audit)
        context = context.permute(0, 2, 1, 3).reshape(batch, tokens, c.hidden_size)
        output = c.o_proj.forward_raw_fixed(context.to(torch.int64)).to(torch.float32) / self.v5.Q16
        if c.output_dtype is not None:
            output = output.to(c.output_dtype)
        return output, None


class CacheManager:
    def __init__(self, model, v5, raw_config, max_context, device):
        cos, sin, self.rope_identity = extend_rope(v5, raw_config, max_context, device)
        self.layers = []
        self.originals = []
        for layer in model.layers:
            original = layer.self_attn
            if not hasattr(original, 'core'):
                raise ValueError('Requires the previously qualified HF5/V5 core adapter')
            adapter = CachedAttention(original.core, v5, cos, sin, max_context)
            self.originals.append(original)
            self.layers.append(adapter)
            layer.self_attn = adapter
        self.model = model

    def reset(self, enabled=True):
        for layer in self.layers:
            layer.reset(enabled)

    def length(self):
        lengths = {int(x.cache_length) for x in self.layers}
        if len(lengths) != 1:
            raise ValueError('Incomplete 32-layer cache')
        return lengths.pop()

    def cache_identity(self):
        return [dict(layer=i, tokens=x.cache_length,
                     key={n:array_hash(getattr(x.key,n)) for n in ('values_s12','codes_u8','shifts_u8')},
                     value={n:array_hash(getattr(x.value,n)) for n in ('values_s12','codes_u8','shifts_u8')})
                for i,x in enumerate(self.layers)]

    def original_mode(self, enabled):
        for layer, original, adapter in zip(self.model.layers, self.originals, self.layers):
            layer.self_attn = original if enabled else adapter
