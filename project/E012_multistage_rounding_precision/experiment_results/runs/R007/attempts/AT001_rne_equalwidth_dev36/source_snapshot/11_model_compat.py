"""Small explicit HF5/V5 compatibility helpers; no checkpoint loading or CUDA."""
from __future__ import annotations
from types import SimpleNamespace


def attention_geometry(original):
    config=original.config
    result=dict(config=config,layer_idx=original.layer_idx,
                num_heads=int(config.num_attention_heads),
                num_key_value_heads=int(config.num_key_value_heads),
                hidden_size=int(config.hidden_size))
    result['head_dim']=int(getattr(original,'head_dim',config.hidden_size//config.num_attention_heads))
    result['num_key_value_groups']=result['num_heads']//result['num_key_value_heads']
    if result['num_heads']*result['head_dim']!=result['hidden_size']:
        raise ValueError('unsupported attention head geometry')
    for name in ('num_heads','num_key_value_heads','hidden_size','head_dim','num_key_value_groups'):
        if hasattr(original,name) and int(getattr(original,name))!=result[name]:
            raise ValueError('legacy/config geometry disagreement: '+name)
    return result


def v5_original_proxy(original):
    """Supply frozen legacy geometry without changing the original HF module."""
    return SimpleNamespace(**attention_geometry(original))


def normalize_attention_mask(mask):
    if mask is None:
        return None
    import torch
    if mask.ndim!=4:
        raise ValueError('V5 adapter requires explicit 4D attention mask')
    if mask.dtype==torch.bool:
        return torch.where(mask,torch.zeros((),device=mask.device,dtype=torch.float32),
                           torch.full((),float('-inf'),device=mask.device,dtype=torch.float32))
    if not mask.is_floating_point() or bool((mask>0).any().item()):
        raise ValueError('float attention mask must be additive nonpositive')
    return mask


def wrap_hf5_attention(core):
    """Return a two-result HF5 module around a three-result V5 core."""
    import torch.nn as nn
    class HF5AttentionAdapter(nn.Module):
        def __init__(self,core):
            super().__init__();self.core=core
        def __getattr__(self,name):
            try:
                return super().__getattr__(name)
            except AttributeError:
                return getattr(super().__getattr__('core'),name)
        def forward(self,hidden_states,attention_mask=None,position_ids=None,
                    past_key_values=None,past_key_value=None,use_cache=False,
                    cache_position=None,position_embeddings=None,**kwargs):
            if use_cache or past_key_values is not None or past_key_value is not None:
                raise ValueError('V5 compatibility contract requires no cache')
            output=self.core(hidden_states=hidden_states,
                             attention_mask=normalize_attention_mask(attention_mask),
                             position_ids=position_ids,past_key_value=None,use_cache=False,
                             cache_position=cache_position,position_embeddings=position_embeddings,**kwargs)
            if not isinstance(output,tuple) or len(output) not in (2,3):
                raise ValueError('Attention core must return two or three values')
            if len(output)==3 and output[2] is not None:
                raise ValueError('V5 core unexpectedly returned cache')
            return output[0],output[1]
    return HF5AttentionAdapter(core)


def production_module():
    """One canonical V5 module object for attach and arithmetic contexts."""
    from .current_nodes import _v5
    return _v5()


def attachment_context(v5=None, *, rope_config=None):
    """Temporarily adapt production V5Attention construction for HF5.

    This patches only this process's module symbol and always restores it. It
    performs no checkpoint loading or inference. Use sequentially, not from
    simultaneous threads with different arithmetic policies.
    """
    from contextlib import contextmanager
    @contextmanager
    def context():
        canonical=production_module()
        module=canonical if v5 is None else v5
        if module is not canonical:
            raise ValueError('attach/arithmetic contexts must share current_nodes._v5()')
        original_class=module.V5Attention
        original_rope=module._rope_tables
        def adapted(original,*args,**kwargs):
            return wrap_hf5_attention(original_class(v5_original_proxy(original),*args,**kwargs))
        try:
            module.V5Attention=adapted
            if rope_config is not None:
                # HF5 migrates/removes legacy RoPE fields. The frozen original
                # checkpoint dictionary is the production exporter authority.
                module._rope_tables=lambda _config,device: original_rope(rope_config,device)
            yield module
        finally:
            module.V5Attention=original_class
            module._rope_tables=original_rope
    return context()


def attach_v5_fullchain_compatible(model,*,checkpoint_dir,device,**kwargs):
    """Run the existing attach with explicit format05 and an HF5 constructor shim."""
    frozen=dict(strict_total_shift=True,software_extended=False,
                down_output_width=32,down_shift12_candidate=True)
    for key,value in frozen.items():
        if key in kwargs and kwargs[key]!=value:
            raise ValueError('format05 compatibility forbids override '+key)
        kwargs[key]=value
    import hashlib
    import json
    from pathlib import Path
    config_path=(Path(checkpoint_dir)/'config.json').resolve(strict=True)
    config_bytes=config_path.read_bytes()
    raw_config=json.loads(config_bytes)
    if not isinstance(raw_config,dict) or 'rope_theta' not in raw_config or 'rope_scaling' not in raw_config:
        raise ValueError('original checkpoint config lacks production RoPE fields')
    config_identity=dict(path=str(config_path),sha256=hashlib.sha256(config_bytes).hexdigest())
    with attachment_context(rope_config=raw_config) as v5:
        metadata,audit=v5.attach_v5_fullchain(model,checkpoint_dir=checkpoint_dir,device=device,**kwargs)
    metadata=dict(metadata)
    metadata['rope_config_adapter']=dict(source=config_identity,
        coefficient_generation='unchanged_production_rope_function_on_original_checkpoint_config',
        hf_config_modified=False)
    return metadata,audit
