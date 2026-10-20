"""Bounded, preselected same-input witnesses for independent CPU arithmetic audit.

This module never selects by observed error.  A witness includes the complete
integer dependency of each selected output (whole rows/pairs where needed),
not just the two rounded results.  It observes the first call at each frozen
document/layer/node/site coordinate and patches only an observer instance's
``_record`` method.  Production symbols and tensors are never modified.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np

NODES = frozenset(('linear', 'rope', 'qk', 'softmax', 'pv'))
COMMON_EXITS = {
    'linear': 'F16 half-away-from-zero then profile S24/S32 saturation',
    'rope': 'F16 half-away-from-zero then S24 saturation',
    'qk': 'F14 floor then shared score clip to [-16,16]',
    'softmax': 'same integer LUT; U16 half-up then cap 65535',
    'pv': 'F16 half-away-from-zero then S24 saturation',
}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def deterministic_indices(size, count=16, *, seed=0, coordinate=()):
    """Sorted boundary + SHA256-seeded positions, independent of tensor values.

    Interior positions use rejection sampling from a 256-bit uniform integer;
    results do not depend on Python's process-randomized ``hash`` or RNG state.
    Boundaries are deliberate coverage, so the full set is not an IID sample.
    """
    if type(size) is not int or size < 0 or type(count) is not int or count < 1:
        raise ValueError('size must be nonnegative and count positive integers')
    if type(seed) is not int:
        raise TypeError('seed must be an integer')
    wanted = min(size, count)
    if not wanted:
        return np.empty(0, dtype=np.int64)
    if wanted == size:
        return np.arange(size, dtype=np.int64)
    chosen = {0}
    if wanted > 1:
        chosen.add(size - 1)
    prefix = _json([seed, list(coordinate), size])
    limit = (1 << 256) - ((1 << 256) % size)
    counter = 0
    while len(chosen) < wanted:
        value = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(8, 'big')).digest(), 'big')
        counter += 1
        if value < limit:
            chosen.add(value % size)
    return np.asarray(sorted(chosen), dtype=np.int64)


def _numpy(tensor):
    return np.ascontiguousarray(tensor.detach().cpu().numpy()).copy()


def _indices(ids, shape, device):
    import torch
    coordinates = np.unravel_index(np.asarray(ids, dtype=np.int64), shape)
    return tuple(torch.as_tensor(value, device=device, dtype=torch.int64) for value in coordinates)


def _flat_take(tensor, ids):
    shape = tuple(np.asarray(ids).shape)
    selected = tensor[_indices(np.asarray(ids).reshape(-1), tuple(tensor.shape), tensor.device)]
    return _numpy(selected).reshape(shape)


def _rows(tensor, ids):
    return tensor[_indices(ids, tuple(tensor.shape[:-1]), tensor.device) + (slice(None),)]


def _shape(tensor):
    return tuple(int(value) for value in tensor.shape)


def extract_witness(node, current, reference, arguments, selected):
    """Extract only selected dependencies on-device, then copy that slice to CPU.

    ``selected`` indexes scalar outputs except RoPE pair units and Softmax rows.
    Returned input names are the frozen ``policy.evaluate_node`` array schema.
    This extraction recomputes integer dots on CPU; it uses no oracle rounding.
    """
    import torch
    if node not in NODES:
        raise ValueError('unsupported witness node: ' + str(node))
    if _shape(current) != _shape(reference):
        raise ValueError('current/reference output shapes differ')
    if current.dtype not in (torch.int16, torch.int32, torch.int64) or reference.dtype not in (torch.int16, torch.int32, torch.int64):
        raise TypeError('witness common exits must be signed integer tensors')
    selected = np.asarray(selected, dtype=np.int64)
    if selected.ndim != 1 or not selected.size or np.any(selected < 0):
        raise ValueError('selected units must be a nonempty nonnegative index vector')
    shape = _shape(current)
    config = {}
    metadata = dict(original_output_shape=list(shape), selection_unit='scalar_output')
    if node == 'linear':
        activation = arguments['activation']
        weights = arguments['weight_s8']
        columns, groups, lanes = _shape(weights)
        if lanes != 32 or groups != int(activation.groups) or groups > 448:
            raise ValueError('Linear requires production Group32 with G<=448')
        if not shape or shape[-1] != columns or math.prod(shape[:-1]) != int(activation.rows):
            raise ValueError('Linear output geometry does not match prepared activation')
        row, channel = selected // columns, selected % columns
        ri = torch.as_tensor(row, dtype=torch.int64, device=weights.device)
        ci = torch.as_tensor(channel, dtype=torch.int64, device=weights.device)
        arrays = dict(q_a=_numpy(activation.values_u8[ri]), q_w=_numpy(weights[ci]),
                      zero_point=_numpy(activation.zero_points_u8[ri]),
                      act_code=_numpy(activation.codes_u8[ri]), act_shift=_numpy(activation.shifts_u8[ri]),
                      weight_code=_numpy(arguments['weight_codes_u8'][ci]),
                      weight_shift=_numpy(arguments['weight_shifts_u8'][ci]))
        arrays['dot'] = np.sum((arrays['q_a'].astype(np.int64) - arrays['zero_point'][..., None]) * arrays['q_w'].astype(np.int64), axis=-1, dtype=np.int64)
        profiles = {(26, 47): 'attention', (20, 44): 'mlp_gate_up', (12, 44): 'mlp_down'}
        key = (arguments['shift_min'], arguments['shift_max'])
        if key not in profiles:
            raise ValueError('unknown production Linear profile')
        config['profile'] = profiles[key]
        metadata.update(activation_rows=row.tolist(), output_channels=channel.tolist(), groups=groups, lanes=32)
        flat = selected
    elif node == 'rope':
        raw = arguments['raw']
        if len(shape) != 4 or shape[-1] != 128 or _shape(raw) != shape:
            raise ValueError('RoPE requires [B,T,H,128] raw/output')
        b, t, h, lane = _indices(selected, shape[:-1] + (64,), raw.device)
        arrays = dict(raw_pair=_numpy(torch.stack((raw[b, t, h, lane], raw[b, t, h, lane + 64]), dim=-1)),
                      cos_q16=_numpy(arguments['cos_q16'][b, t, lane]),
                      sin_q16=_numpy(arguments['sin_q16'][b, t, lane]))
        prefix, pair = selected // 64, selected % 64
        flat = np.stack((prefix * 128 + pair, prefix * 128 + pair + 64), axis=-1)
        metadata['selection_unit'] = 'complete_rope_pair'
    elif node == 'qk':
        query, keys = arguments['query_s24'], arguments['keys']
        ratio = arguments['num_key_value_groups']
        if len(shape) != 4 or type(ratio) is not int or ratio < 1:
            raise ValueError('QK requires [B,H,Q,K] and positive GQA ratio')
        b, h, q, k = _indices(selected, shape, query.device)
        if _shape(query) != (shape[0], shape[2], shape[1], 128) or _shape(keys.values_s12) != (shape[0], shape[3], shape[1] // ratio, 4, 32) or shape[1] % ratio:
            raise ValueError('QK query/key/output geometry mismatch')
        arrays = dict(query_s24=_numpy(query[b, q, h]).reshape(-1, 4, 32),
                      key_s12=_numpy(keys.values_s12[b, k, h // ratio]),
                      kv_code=_numpy(keys.codes_u8[b, k, h // ratio]),
                      kv_shift=_numpy(keys.shifts_u8[b, k, h // ratio]))
        arrays['dot'] = np.sum(arrays['query_s24'].astype(np.int64) * arrays['key_s12'].astype(np.int64), axis=-1, dtype=np.int64)
        metadata['num_key_value_groups'] = ratio
        flat = selected
    elif node == 'softmax':
        score, mask = arguments['score_s20'], arguments['valid_mask']
        if len(shape) < 2 or not 1 <= shape[-1] <= 128 or _shape(score) != shape:
            raise ValueError('Softmax requires [...,K], K<=128')
        full_mask = torch.broadcast_to(mask, shape)
        arrays = dict(score_q14=_numpy(_rows(score, selected)),
                      valid_mask=_numpy(_rows(full_mask, selected)),
                      lut_u17=_numpy(arguments['lut_u17']))
        if arrays['lut_u17'].shape != (257,):
            raise ValueError('Softmax requires complete LUT[257]')
        flat = selected[:, None] * shape[-1] + np.arange(shape[-1], dtype=np.int64)[None, :]
        metadata['selection_unit'] = 'complete_softmax_row'
    else:
        prob, values = arguments['probability_u16'], arguments['values']
        ratio = arguments['num_key_value_groups']
        if len(shape) != 4 or shape[-1] != 128 or type(ratio) is not int or ratio < 1:
            raise ValueError('PV requires [B,H,Q,128] and positive GQA ratio')
        b, h, q, channel = _indices(selected, shape, prob.device)
        group, lane = channel // 32, channel % 32
        length = int(prob.shape[-1])
        if _shape(prob)[:3] != shape[:3] or not 1 <= length <= 128 or _shape(values.values_s12) != (shape[0], length, shape[1] // ratio, 4, 32) or shape[1] % ratio:
            raise ValueError('PV probability/cache/output geometry mismatch')
        key = torch.arange(length, device=prob.device)[None, :]
        arrays = dict(probability_u16=_numpy(prob[b, h, q]),
                      value_s12=_numpy(values.values_s12[b[:, None], key, (h // ratio)[:, None], group[:, None], lane[:, None]]),
                      kv_code=_numpy(values.codes_u8[b[:, None], key, (h // ratio)[:, None], group[:, None]]),
                      kv_shift=_numpy(values.shifts_u8[b[:, None], key, (h // ratio)[:, None], group[:, None]]))
        metadata['num_key_value_groups'] = ratio
        flat = selected
    arrays['_witness_current_code'] = _flat_take(current, flat)
    arrays['_witness_reference_code'] = _flat_take(reference, flat)
    arrays['_witness_output_flat_indices'] = np.asarray(flat, dtype=np.int64)
    arrays['_witness_unit_flat_indices'] = selected
    metadata.update(selected_unit_count=int(selected.size), actual_scalar_count=int(np.asarray(flat).size),
                    selected_output_coordinates=np.stack(np.unravel_index(np.asarray(flat).reshape(-1), shape), axis=-1).tolist())
    return arrays, config, metadata


class NodeWitnesses:
    """Write bounded NPZ dependencies and an explicit saved/skipped manifest.

    Callbacks synchronize only the small selected slices on audit documents.
    ``samples_per_coordinate`` targets scalar output points.  RoPE pairs and
    Softmax rows containing those points are expanded and deduplicated; planned
    point counts, saved unit counts and expanded scalar counts remain separate.
    Capacity is disk bytes including the JSON manifest.  A reserved metadata
    allowance keeps budget-skipped coordinates visible instead of hiding later
    layers; exhaustion of even that allowance raises an explicit error.
    """
    def __init__(self, directory, audit_doc_ids, *, samples_per_coordinate=16, seed=0,
                 max_doc_bytes=64 << 20, max_at_bytes=256 << 20):
        if type(samples_per_coordinate) is not int or not 1 <= samples_per_coordinate <= 256:
            raise ValueError('samples_per_coordinate must be integer 1..256')
        if type(seed) is not int:
            raise TypeError('seed must be integer')
        if isinstance(audit_doc_ids, str):
            raise TypeError('audit_doc_ids must be a collection, not one string')
        docs = tuple(audit_doc_ids)
        if not docs or len(set(docs)) != len(docs) or any(not isinstance(x, str) or not x for x in docs):
            raise ValueError('audit_doc_ids must be distinct nonempty strings')
        if any(type(x) is not int or x < 4096 for x in (max_doc_bytes, max_at_bytes)):
            raise ValueError('byte budgets must be integers >=4096')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        if any(self.directory.iterdir()):
            raise FileExistsError('witness directory must be empty; previous evidence is never overwritten')
        self.docs, self.samples, self.seed = frozenset(docs), samples_per_coordinate, seed
        self.max_doc_bytes, self.max_at_bytes = max_doc_bytes, max_at_bytes
        self._doc_payload_bytes = {doc: 0 for doc in docs}
        self._payload_bytes = 0
        self._seen = set()
        self._calls = {}
        self._active = False
        self.manifest = dict(schema_version=1, selection='predeclared_boundaries_plus_sha256_seed',
                             selection_is_iid=False, error_based_selection=False, diagnostic_extrema_included=False,
                             seed=seed, samples_per_coordinate=samples_per_coordinate, audit_doc_ids=list(docs),
                             coverage_nodes=sorted(NODES), excluded_nodes=['swiglu', 'host'],
                             first_call_only=True, common_exits=COMMON_EXITS,
                             max_doc_bytes=max_doc_bytes, max_at_bytes=max_at_bytes,
                             source_files=[dict(path=str(Path(__file__).resolve()), sha256=_sha_file(__file__))],
                             records=[], execution_state='initialized')
        self._write_manifest()

    def _manifest_bytes(self):
        return _json(self.manifest) + b'\n'

    def _write_manifest(self):
        raw = self._manifest_bytes()
        if self._payload_bytes + 2 * len(raw) > self.max_at_bytes:
            raise RuntimeError('witness manifest exhausted AT budget; capture cannot silently omit coordinates')
        for doc, size in self._doc_payload_bytes.items():
            # Charge shared manifest plus its atomic-write temporary to every doc.
            if size + 2 * len(raw) > self.max_doc_bytes:
                raise RuntimeError('witness manifest exhausted document budget: ' + doc)
        temporary = self.directory / 'manifest.json.tmp'
        temporary.write_bytes(raw)
        temporary.replace(self.directory / 'manifest.json')

    def record(self, coordinate, bits, current, reference, arguments,
               current_delta=None, reference_delta=None):
        doc, layer, node, op = coordinate
        if doc not in self.docs or node not in NODES:
            return None
        if type(layer) is not int or not 0 <= layer <= 31:
            raise ValueError('witness layer must be integer 0..31')
        coordinate = (doc, layer, node, op)
        self._calls[coordinate] = self._calls.get(coordinate, 0) + 1
        if coordinate in self._seen:
            return None
        self._seen.add(coordinate)
        shape = _shape(current)
        if not shape or not math.prod(shape):
            raise ValueError('cannot witness empty output')
        points = deterministic_indices(math.prod(shape), self.samples, seed=self.seed, coordinate=coordinate)
        if node == 'softmax':
            units = math.prod(shape[:-1])
            selected = np.unique(points // shape[-1])
        elif node == 'rope':
            units = math.prod(shape[:-1]) * 64
            selected = np.unique((points // 128) * 64 + points % 64)
        else:
            units = math.prod(shape)
            selected = points
        row = dict(doc_id=doc, layer=layer, node=node, op_name=op, call_ordinal=0,
                   planned=True, status='planned', fractional_bits=int(bits),
                   original_output_shape=list(shape), population_units=units,
                   population_scalar_count=math.prod(shape),
                   planned_output_flat_indices=points.tolist(), planned_scalar_count=int(points.size),
                   planned_unit_indices=selected.tolist(), planned_unit_count=int(selected.size),
                   selection_unit=('complete_softmax_row' if node == 'softmax' else 'complete_rope_pair' if node == 'rope' else 'scalar_output'),
                   common_exit=COMMON_EXITS[node], comparison='current_vs_output_only_common_exit',
                   exact_pre_output_saved=False, source_identity='manifest_source_files',
                   budget_exhausted=False)
        self.manifest['records'].append(row)
        arrays, config, metadata = extract_witness(node, current, reference, arguments, selected)
        buffer = io.BytesIO()
        np.savez(buffer, **arrays)
        payload = buffer.getvalue()
        row.update(metadata)
        # Reserve up to 4 MiB per document / 16 MiB per AT for later skip records.
        doc_limit = self.max_doc_bytes - min(4 << 20, self.max_doc_bytes // 4)
        at_limit = self.max_at_bytes - min(16 << 20, self.max_at_bytes // 4)
        name = 'witness_' + hashlib.sha256(_json(list(coordinate))).hexdigest()[:24] + '.npz'
        row.update(status='saved', path=name, sha256=hashlib.sha256(payload).hexdigest(),
                   payload_bytes=len(payload), saved_scalar_count=metadata['actual_scalar_count'], config=config,
                   arrays={key: dict(shape=list(value.shape), dtype=str(value.dtype),
                                     sha256=hashlib.sha256(value.tobytes(order='C')).hexdigest())
                           for key, value in arrays.items()})
        prospective_manifest = 2 * len(self._manifest_bytes())
        fits_manifest = self._payload_bytes + len(payload) + prospective_manifest <= self.max_at_bytes
        fits_manifest &= all(size + (len(payload) if owner == doc else 0) + prospective_manifest <= self.max_doc_bytes
                             for owner, size in self._doc_payload_bytes.items())
        if self._doc_payload_bytes[doc] + len(payload) > doc_limit or self._payload_bytes + len(payload) > at_limit or not fits_manifest:
            for key in ('path', 'sha256', 'payload_bytes', 'arrays'):
                row.pop(key, None)
            row.update(status='skipped', skip_reason='byte_budget', budget_exhausted=True,
                       candidate_payload_bytes=len(payload), saved_scalar_count=0)
            self._write_manifest()
            return row
        path = self.directory / name
        with path.open('xb') as handle:
            handle.write(payload)
        self._payload_bytes += len(payload)
        self._doc_payload_bytes[doc] += len(payload)
        self._write_manifest()
        return row

    @contextmanager
    def context(self, observer):
        """Wrap only this observer's record callback, restoring on every exit."""
        if self._active or getattr(observer, '_m005_node_witnesses_active', False):
            raise RuntimeError('node witness contexts cannot nest')
        had_instance = '_record' in observer.__dict__
        saved_instance = observer.__dict__.get('_record')
        original = observer._record
        for owner in (getattr(observer, 'v5', None), getattr(observer, 'backend', None)):
            file = getattr(owner, '__file__', None)
            if file and Path(file).is_file():
                identity = dict(path=str(Path(file).resolve()), sha256=_sha_file(file))
                if identity not in self.manifest['source_files']:
                    self.manifest['source_files'].append(identity)
        def recording(coordinate, bits, current, reference, arguments, current_delta, reference_delta):
            result = original(coordinate, bits, current, reference, arguments, current_delta, reference_delta)
            self.record(coordinate, bits, current, reference, arguments, current_delta, reference_delta)
            return result
        try:
            self._active = True
            observer._m005_node_witnesses_active = True
            observer._record = recording
            self.manifest['execution_state'] = 'running'
            self._write_manifest()
            yield self
        finally:
            if had_instance:
                observer._record = saved_instance
            else:
                observer.__dict__.pop('_record', None)
            observer.__dict__.pop('_m005_node_witnesses_active', None)
            self._active = False
            self.manifest['execution_state'] = 'context_exited'
            self._write_manifest()


def load_witness(directory, record):
    """Verify a saved record and return CPU arrays/config for evaluate_node."""
    if record.get('status') != 'saved':
        raise ValueError('record is not a saved witness')
    root = Path(directory).resolve()
    path = (root / record['path']).resolve()
    if path.parent != root or _sha_file(path) != record['sha256']:
        raise ValueError('witness path or file identity mismatch')
    with np.load(path, allow_pickle=False) as payload:
        values = {key: payload[key].copy() for key in payload.files}
    if set(values) != set(record['arrays']):
        raise ValueError('witness array set mismatch')
    for key, value in values.items():
        spec = record['arrays'][key]
        if list(value.shape) != spec['shape'] or str(value.dtype) != spec['dtype'] or hashlib.sha256(value.tobytes(order='C')).hexdigest() != spec['sha256']:
            raise ValueError('witness array identity mismatch: ' + key)
    return dict(node=record['node'], arrays={k: v for k, v in values.items() if not k.startswith('_witness_')},
                config=record['config'], current_code=values['_witness_current_code'],
                reference_code=values['_witness_reference_code'],
                output_flat_indices=values['_witness_output_flat_indices'],
                unit_flat_indices=values['_witness_unit_flat_indices'])
