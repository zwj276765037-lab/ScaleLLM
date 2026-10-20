"""Same-input common-exit observations along a production-current trajectory.

No GPU work starts at import. The context computes original current results,
then the independent output-only backend with shadow counters, accumulates
statistics on the tensor device, and returns only the original current value.
Statistics include all accepted real coordinates; aggregate audit counters do
not establish a per-output strict-valid domain. The backend output is a rounded
common-exit reference, never an exact pre-output rational value.
"""
from __future__ import annotations
from contextlib import contextmanager
from functools import wraps
import inspect
import math

AUDIT_FIELDS = {'rope':('rope_output_saturation',), 'qk':('qk_score_clip',), 'pv':('pv_output_saturation',), 'softmax':(), 'linear':()}

NODES = {
    'grouped_linear_s24': ('linear', 'grouped_linear_exact', 16),
    '_fixed_rope': ('rope', 'rope_exact', 16),
    '_qk_scores_s20': ('qk', 'qk_exact', 14),
    '_softmax_u16': ('softmax', 'softmax_exact', 16),
    '_pv_s24': ('pv', 'pv_exact', 16),
}


class LocalObserver:
    """One sequential observer, with per-document/layer/node device reductions."""
    def __init__(self, v5, *, backend=None, sink=None, track_linear_modules=True):
        if backend is None:
            from . import gpu_reference
            backend = gpu_reference
        self.v5, self.backend, self.sink = v5, backend, sink
        self.track_linear_modules = track_linear_modules
        self.doc_id = None
        self.layer = None
        self.op_name = None
        self._stats = {}
        self._shadow_audits = {}
        self._shadow_counters = {}
        self._active = False
        self._rope_sites = {}

    def set_context(self, *, doc_id=None, layer=None, op_name=None):
        if doc_id is not None:
            if not isinstance(doc_id, str) or not doc_id:
                raise ValueError('doc_id must be a nonempty string')
            self.doc_id = doc_id
        if layer is not None:
            if type(layer) is not int or not 0 <= layer <= 31:
                raise ValueError('layer must be integer 0..31')
            self.layer = layer
        self.op_name = op_name
        return self

    def set_document(self, doc_id):
        return self.set_context(doc_id=doc_id, layer=self.layer, op_name=self.op_name)

    def set_layer(self, layer):
        return self.set_context(doc_id=self.doc_id, layer=layer, op_name=self.op_name)

    @contextmanager
    def operation(self, op_name):
        old = self.op_name
        self.op_name = op_name
        try:
            yield self
        finally:
            self.op_name = old

    def _coordinate(self, node):
        if self.doc_id is None or self.layer is None:
            raise RuntimeError('set observer doc_id and layer before a node call')
        op=self.op_name or node
        if node=='rope' and self.op_name is None:
            key=(self.doc_id,self.layer)
            ordinal=self._rope_sites.get(key,0)
            self._rope_sites[key]=ordinal+1
            op='query_rope' if ordinal%2==0 else 'key_rope'
        return self.doc_id, self.layer, node, op

    @staticmethod
    def _audit_values(audit):
        return getattr(audit, 'values', {}) if audit is not None else {}

    def _shadow_arguments(self, arguments, node):
        shadow = dict(arguments)
        if 'audit' in arguments and arguments['audit'] is not None:
            audit = arguments['audit']
            key = (type(audit), str(audit.device))
            if key not in self._shadow_audits:
                self._shadow_audits[key] = type(audit)(audit.device)
            replacement = self._shadow_audits[key]
            for name in AUDIT_FIELDS[node]:
                if name in self._audit_values(replacement):
                    self._audit_values(replacement)[name].zero_()
            shadow['audit'] = replacement
        for name, value in arguments.items():
            if name.endswith('_count') and hasattr(value, 'zero_'):
                import torch
                key = (name, str(value.device), str(value.dtype), tuple(value.shape))
                if key not in self._shadow_counters:
                    self._shadow_counters[key] = torch.zeros_like(value)
                replacement = self._shadow_counters[key]
                replacement.zero_()
                shadow[name] = replacement
        return shadow

    def _counter_values(self, arguments, node):
        values=self._audit_values(arguments.get('audit'))
        counters={name:values[name] for name in AUDIT_FIELDS[node] if name in values}
        for name, value in arguments.items():
            if name.endswith('_count') and hasattr(value, 'clone'):
                counters[name] = value
        return counters

    def _record(self, coordinate, bits, current, reference, arguments,
                current_delta, reference_delta):
        import torch
        if not isinstance(current, torch.Tensor) or not isinstance(reference, torch.Tensor):
            raise TypeError('node observer requires tensor outputs')
        if current.shape != reference.shape or current.device != reference.device:
            raise ValueError('current/reference output shape or device differs')
        if current.dtype not in (torch.int16, torch.int32, torch.int64) or reference.dtype not in (torch.int16, torch.int32, torch.int64):
            raise TypeError('common node exits must be signed integer tensors')
        mask = torch.ones_like(current, dtype=torch.bool)
        if coordinate[2] == 'softmax':
            valid = arguments.get('valid_mask')
            if valid is None or valid.dtype != torch.bool:
                raise ValueError('Softmax observation requires bool valid_mask')
            mask = torch.broadcast_to(valid, current.shape)
        # Subtract integer codes before converting, avoiding cancellation of
        # a small code difference between large floating reference values.
        delta = (current.to(torch.int64)-reference.to(torch.int64)).to(torch.float64) * (2.0**-bits)
        signal = reference.to(torch.float64) * (2.0**-bits)
        delta = torch.where(mask, delta, torch.zeros_like(delta))
        signal = torch.where(mask, signal, torch.zeros_like(signal))
        count = mask.to(torch.int64).sum()
        entry = self._stats.get(coordinate)
        if entry is None:
            entry = dict(fractional_bits=bits, calls=0, total_shape_elements=0,
                         count=torch.zeros((),dtype=torch.int64,device=current.device),
                         sum_signal2=torch.zeros((),dtype=torch.float64,device=current.device),
                         sum_diff2=torch.zeros((),dtype=torch.float64,device=current.device),
                         sum_diff=torch.zeros((),dtype=torch.float64,device=current.device),
                         max_abs=torch.zeros((),dtype=torch.float64,device=current.device),
                         audit_current={},audit_reference={})
            self._stats[coordinate] = entry
        if entry['fractional_bits'] != bits or entry['count'].device != current.device:
            raise ValueError('one coordinate cannot mix formats/devices')
        entry['calls'] += 1
        entry['total_shape_elements'] += current.numel()
        entry['count'].add_(count)
        entry['sum_signal2'].add_((signal*signal).sum())
        entry['sum_diff2'].add_((delta*delta).sum())
        entry['sum_diff'].add_(delta.sum())
        if delta.numel():
            entry['max_abs'] = torch.maximum(entry['max_abs'], delta.abs().max())
        for target, values in (('audit_current',current_delta),('audit_reference',reference_delta)):
            for name, value in values.items():
                if name not in entry[target]:
                    entry[target][name] = torch.zeros_like(value)
                entry[target][name].add_(value)

    def _wrap(self, original, name):
        node, exact_name, bits = NODES[name]
        exact = getattr(self.backend, exact_name)
        signature = inspect.signature(original)
        @wraps(original)
        def observed(*args, **kwargs):
            coordinate = self._coordinate(node)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            current_counters = self._counter_values(arguments,node)
            before = {key:value.clone() for key,value in current_counters.items()}
            current = original(*args, **kwargs)
            current_delta = {key:value-before[key] for key,value in current_counters.items()}
            shadow = self._shadow_arguments(arguments,node)
            reference = exact(**shadow)
            reference_delta = {key:value.clone() for key,value in self._counter_values(shadow,node).items()}
            self._record(coordinate,bits,current,reference,arguments,current_delta,reference_delta)
            return current
        return observed

    @contextmanager
    def context(self):
        marker = '_m005_local_observer_active'
        if self._active or getattr(self.v5,marker,False) or getattr(self.v5,'_m005_arithmetic_context_active',False):
            raise RuntimeError('local observations require one unpatched current trajectory')
        originals = {name:getattr(self.v5,name) for name in NODES}
        linear_cls = getattr(self.v5,'V5ProductionLinear',None)
        original_project = getattr(linear_cls,'project_prepared',None) if self.track_linear_modules else None
        observer = self
        if original_project is not None:
            @wraps(original_project)
            def project(module,*args,**kwargs):
                with observer.operation(module.op_name):
                    return original_project(module,*args,**kwargs)
        try:
            setattr(self.v5,marker,True)
            self._active=True
            for name,original in originals.items():
                setattr(self.v5,name,self._wrap(original,name))
            if original_project is not None:
                linear_cls.project_prepared=project
            yield self
        finally:
            for name,original in originals.items():
                setattr(self.v5,name,original)
            if original_project is not None:
                linear_cls.project_prepared=original_project
            self._active=False
            if hasattr(self.v5,marker):
                delattr(self.v5,marker)

    def flush(self, doc_id=None):
        """Synchronize only at an explicit document boundary and send summaries."""
        records=[]
        for coordinate in list(self._stats):
            if doc_id is not None and coordinate[0] != doc_id:
                continue
            entry=self._stats.pop(coordinate)
            # Device-to-host sync is explicit here, never hidden in each call.
            count=int(entry['count'].detach().cpu().item())
            numbers={name:float(entry[name].detach().cpu().item()) for name in ('sum_signal2','sum_diff2','sum_diff','max_abs')}
            current={name:int(value.detach().cpu().item()) for name,value in entry['audit_current'].items()}
            reference={name:int(value.detach().cpu().item()) for name,value in entry['audit_reference'].items()}
            incomparable={name for name in set(current)|set(reference) if 'guard' in name or 'accumulator' in name}
            reference={name:(None if name in incomparable else value) for name,value in reference.items()}
            energy=numbers['sum_signal2']
            bias=numbers['sum_diff']/count if count else None
            row=dict(doc_id=coordinate[0],layer=coordinate[1],node=coordinate[2],op_name=coordinate[3],
                     calls=entry['calls'],count=count,total_shape_elements=entry['total_shape_elements'],
                     fractional_bits=entry['fractional_bits'],**numbers,bias=bias,
                     relative_l2_percent=100*math.sqrt(numbers['sum_diff2']/energy) if count and energy>0 else None,
                     normalized_bias=bias/math.sqrt(energy/count) if count and energy>0 else None,
                     audit_current_delta=current,audit_reference_delta=reference,
                     audit_delta_current_minus_reference={name:(None if name in incomparable else current.get(name,0)-reference.get(name,0)) for name in set(current)|set(reference)},
                     audit_not_comparable_fields=sorted(incomparable),
                     site_assignment=('frozen_V5_query_then_key_order' if coordinate[2]=='rope' and coordinate[3] in ('query_rope','key_rope') else 'explicit_or_node_family'),
                     rope_site_pair_complete=(self._rope_sites.get(coordinate[:2],0)%2==0 if coordinate[2]=='rope' and coordinate[3] in ('query_rope','key_rope') else None),
                     denominator_kind='all_accepted_real_coordinates',strict_per_output_domain=False,
                     comparison='current_vs_output_only_common_exit',exact_pre_output_comparison=False,
                     reference_finite_guard_acc_audit='not_applicable_wider_arithmetic',
                     zero_signal=bool(count and energy==0))
            records.append(row)
            if self.sink is not None:
                self.sink(row)
        for key in list(self._rope_sites):
            if doc_id is None or key[0]==doc_id:
                del self._rope_sites[key]
        return records


@contextmanager
def local_observer_context(v5, *, backend=None, sink=None, doc_id=None, layer=None,
                           track_linear_modules=True):
    observer=LocalObserver(v5,backend=backend,sink=sink,track_linear_modules=track_linear_modules)
    observer.set_context(doc_id=doc_id,layer=layer)
    with observer.context():
        yield observer
