"""Strict, document-level aggregation of explicitly listed completed GPU attempts.

No model or GPU imports.  Failed/changed/misidentified/incomplete attempts are
rejected, never dropped to manufacture a successful subset.  Partial mode only
permits unmeasured documents from the immutable target.  Relative ratios retain
0/0 as null; document constraint bounds use the extended nonnegative reals.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path

DOMAIN_COUNTS = {'web': 512, 'news': 256, 'reviews': 256}
FAMILIES = ('linear', 'rope', 'qk', 'softmax', 'pv')
SITES = {('linear', op) for op in ('q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj')}
SITES |= {('rope', 'query_rope'), ('rope', 'key_rope'), ('qk', 'qk'), ('softmax', 'softmax'), ('pv', 'pv')}
LOCAL_KEYS = {(layer, node, op) for layer in range(32) for node, op in SITES}
DYNAMIC_KEYS = {(arm, layer, function, ordinal) for arm in ('current', 'reference') for layer in range(32)
                for function, count in (('prepare_fixed_activation', 4), ('_kv12_quantize', 2)) for ordinal in range(count)}
CORE_SOURCES = {'v5_fullchain.py', 'gpu_reference.py', 'local_observer.py', 'chunked_quantization.py',
                'model_compat.py', 'policy.py', 'current_nodes.py', 'exact_reductions.py',
                'export_scalellm_llama31_artifacts.py', 'fixbit_v2.py'}
CONSUMED_SOURCES = CORE_SOURCES | {'run_paired_numerical_model.py', 'run_numerical_fidelity.py',
    'numerical_model_stream.py', 'formal_numerical_inputs.py', 'formal_storage_plan.py', 'capture_real_inputs.py',
    'prepare_replay_data.py', 'run_local_experiment.py', 'node_witnesses.py', 'production_replay.py',
    'modeling_llama.py', 'modeling.py'}
IDENTITY_FIELDS = ('doc_id', 'domain', 'split', 'evidence_role', 'text_sha256', 'duplicate_cluster')


class AggregateValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AggregateValidationError(message)


def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


class Evidence:
    def __init__(self):
        self.files = {}

    def json(self, path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        self.files[str(path)] = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        return json.loads(raw)

    def rows(self, path):
        path = Path(path).resolve()
        digest, size = hashlib.sha256(), 0
        with path.open('rb') as handle:
            for raw in handle:
                digest.update(raw); size += len(raw)
                if raw.strip():
                    yield json.loads(raw)
        self.files[str(path)] = {'path': str(path), 'bytes': size, 'sha256': digest.hexdigest()}

    def verify(self, spec, path=None):
        actual = identity(path if path is not None else spec['path'])
        require(actual['sha256'] == spec['sha256'], 'file SHA mismatch: ' + actual['path'])
        require('bytes' not in spec or actual['bytes'] == spec['bytes'], 'file size mismatch: ' + actual['path'])
        self.files[actual['path']] = actual
        return actual


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _encoded(value):
    """JSON-safe finite Decimal or an explicit positive-infinity flag."""
    if value.is_infinite():
        return {'value': None, 'value_decimal': None, 'unbounded': True}
    as_float = float(value)
    return {'value': as_float if math.isfinite(as_float) else None,
            'value_decimal': str(value), 'unbounded': False,
            'finite_decimal_only': not math.isfinite(as_float)}


def classify_metric(metric):
    """Preserve raw ratio semantics independently of the document max rule."""
    if not isinstance(metric, dict):
        return dict(state='unestimable', value=None, reason='missing_metric')
    signal, error = metric.get('signal_energy'), metric.get('error_energy')
    if not _number(signal) or not _number(error):
        return dict(state='unestimable', value=None, reason='invalid_or_nonfinite_energy')
    count = metric.get('valid_elements')
    if type(count) is not int or count <= 0:
        return dict(state='unestimable', value=None, reason='empty_or_invalid_metric_domain')
    if metric.get('nonfinite_elements', 0) != 0:
        return dict(state='unestimable', value=None, reason='nonfinite_output_elements')
    result = dict(signal_energy=signal, error_energy=error, accepted_elements=count)
    reported = metric.get('relative_l2_percent')
    if signal == 0:
        if reported is not None:
            return dict(result, state='unestimable', value=None, reason='zero_signal_ratio_was_not_null')
        if error == 0:
            return dict(result, state='exact_zero_match', value=None, reason='zero_reference_zero_error', relative_ratio_undefined=True)
        return dict(result, state='unbounded', value=None, unbounded=True,
                    reason='zero_reference_nonzero_error', relative_ratio_undefined=True)
    with localcontext() as ctx:
        ctx.prec = 60
        ratio = Decimal(100) * (Decimal(str(error)) / Decimal(str(signal))).sqrt()
    if not _number(reported) or not math.isclose(float(ratio), reported, rel_tol=1e-10, abs_tol=1e-13):
        return dict(result, state='unestimable', value=None, reason='missing_or_inconsistent_reported_ratio')
    return dict(result, state='finite', reason=None, **_encoded(ratio))


def constraint_bound(components):
    """Smallest M>=0 satisfying every required norm constraint, without imputation."""
    components = list(components)
    states = Counter(row['state'] for row in components)
    common = dict(required_positions=len(components), exact_zero_match_count=states['exact_zero_match'],
                  invalid_position_count=states['unestimable'], observed_unbounded=bool(states['unbounded']),
                  definition='minimum M>=0 such that every required ||error|| <= (M/100)*||reference||')
    if not components or states['unestimable']:
        return dict(common, state='unestimable', value=None, unbounded=False,
                    reason='missing_or_invalid_required_position', all_zero_exact=False)
    if states['unbounded']:
        return dict(common, state='unbounded', value=None, unbounded=True,
                    reason='zero_reference_nonzero_error', all_zero_exact=False)
    finite = [Decimal(row['value_decimal']) for row in components if row['state'] == 'finite']
    all_zero = not finite
    maximum = max(finite, default=Decimal(0))
    return dict(common, state='finite', reason=None, all_zero_exact=all_zero, **_encoded(maximum))


def _extended_value(row):
    return Decimal('Infinity') if row['state'] == 'unbounded' else Decimal(row['value_decimal'])


def position_metric(row):
    metric = row.get('metrics', {}).get('current_vs_reference')
    classified = classify_metric(metric)
    context = dict(signal_rms=None, absolute_max=None, signed_bias=None, normalized_signed_bias_percent=None)
    if isinstance(metric, dict):
        signal, count = metric.get('signal_energy'), metric.get('valid_elements')
        if _number(signal) and type(count) is int and count > 0:
            context['signal_rms'] = math.sqrt(signal/count)
        maximum, signed = metric.get('absolute_max'), metric.get('signed_error_sum')
        context['absolute_max'] = maximum if _number(maximum) else None
        if type(signed) in (int, float) and math.isfinite(signed) and type(count) is int and count > 0:
            context['signed_bias'] = signed/count
        bias = metric.get('normalized_signed_bias_percent')
        if type(bias) in (int, float) and math.isfinite(bias):
            context['normalized_signed_bias_percent'] = bias
    return dict(classified, coordinate=dict(layer=row['layer'], node=row['node'], op=row['op']), context=context)


def position_bound(components):
    components = list(components)
    bound = constraint_bound(components)
    bound.update(max_coordinate=None, tie_count=0, argmax_position_context=None,
                 tie_rule='lexicographically first (layer,node,op) among all exact ties',
                 bias_scope='mean signed error at the argmax position, not a bias of the maximum statistic')
    if bound['state'] == 'unestimable':
        return bound
    def value(row):
        return Decimal(0) if row['state'] == 'exact_zero_match' else _extended_value(row)
    maximum = Decimal('Infinity') if bound['state'] == 'unbounded' else Decimal(bound['value_decimal'])
    ties = [row for row in components if value(row) == maximum]
    ties.sort(key=lambda row: tuple(row['coordinate'][key] for key in ('layer', 'node', 'op')))
    if ties:
        bound.update(max_coordinate=ties[0]['coordinate'], tie_count=len(ties),
                     argmax_position_context=ties[0]['context'], argmax_relative_ratio_state=ties[0]['state'])
    return bound


def descriptive_distribution(records, *, complete_target, fixed_quota_pool, iid_assumed=True):
    """Linear descriptive quantiles; rank CIs retain genuine infinite endpoints."""
    records = list(records)
    counts = Counter(row['state'] for row in records)
    out = dict(document_count=len(records), finite_documents=counts['finite'],
               unbounded_documents=counts['unbounded'], unestimable_documents=counts['unestimable'],
               all_zero_exact_documents=sum(bool(row.get('all_zero_exact')) for row in records),
               point_estimator='linear interpolation in extended nonnegative reals',
               fixed_quota_pool=fixed_quota_pool, ci_assumption='within-domain iid documents; assumed, not verified',
               simultaneous_family_size=1, family_scope='pointwise metric and quantile; no all-domain/all-family joint guarantee',
               quantiles={})
    if counts['unestimable'] or not records:
        out.update(state='unestimable', quantile_status='missing_or_invalid_document_metric; no successful-subset estimate',
                   interval_status='not_reported_for_unestimable_collection')
        return out
    ordered = sorted(_extended_value(row) for row in records)
    for label, p in (('p50', Decimal('.50')), ('p95', Decimal('.95')), ('p99', Decimal('.99'))):
        location = p * (len(ordered) - 1)
        left = int(location)
        fraction = location - left
        if not fraction:
            value = ordered[left]
        else:
            a, b = ordered[left], ordered[left + 1]
            value = Decimal('Infinity') if a.is_infinite() or b.is_infinite() else a + fraction * (b-a)
        point = dict(state='unbounded' if value.is_infinite() else 'finite', **_encoded(value), interval=None)
        if complete_target and not fixed_quota_pool and iid_assumed:
            from metric_uncertainty import rank_interval
            ranks = rank_interval(len(ordered), str(p), alpha='0.05', family_size=1)
            low, high = ranks['lower_rank'], ranks['upper_rank']
            # The predeclared support is [0,+infinity], not the sample extrema.
            lower = ordered[low-1] if low else Decimal(0)
            upper = ordered[high-1] if high <= len(ordered) else Decimal('Infinity')
            point['interval'] = dict(ranks, lower=_encoded(lower), upper=_encoded(upper),
                                     known_support_lower=0, lower_support_applied=low == 0,
                                     upper_rank_outside_sample=high > len(ordered))
        out['quantiles'][label] = point
    out.update(state='defined', quantile_status='all_document_metrics_included_in_extended_sort',
               interval_status=('descriptive_fixed_quota_pool_only' if fixed_quota_pool else
                                'not_reported_for_partial_target' if not complete_target else
                                'conditional_on_unverified_within_domain_iid' if iid_assumed else 'iid_not_assumed'))
    return out


def _check_identity(row, expected, context):
    require(all(row.get(key) == expected[key] for key in IDENTITY_FIELDS), 'document identity mismatch: ' + context)


def _check_coordinates(rows, expected, key, context):
    coordinates = [key(row) for row in rows]
    require(len(coordinates) == len(expected) and set(coordinates) == expected, 'missing/duplicate/unexpected coordinates: ' + context)


def _check_metric_counts(row, tokens):
    node, op = row['node'], row['op']
    if node == 'linear':
        channels = 1024 if op in ('k_proj', 'v_proj') else 14336 if op in ('gate_proj', 'up_proj') else 4096
        total = accepted = tokens * channels
    elif node == 'rope':
        total = accepted = tokens * (1024 if op == 'key_rope' else 4096)
    elif node in ('qk', 'softmax'):
        total = 32 * tokens * tokens
        accepted = 16 * tokens * (tokens + 1) if node == 'softmax' else total
    else:
        total = accepted = tokens * 4096
    metric = row.get('metrics', {}).get('current_vs_reference', {})
    require(metric.get('total_elements') == total and metric.get('valid_elements') == accepted,
            'metric output/accepted element count differs from frozen unpadded geometry')


def _validate_plan(plan_path, stream_path, evidence):
    plan = evidence.json(plan_path)
    require(plan.get('schema') == 'm005_formal_numerical_batch_plan_v1' and plan.get('phase') == 'formal_numerical_evaluation', 'wrong formal plan schema/phase')
    stream_identity = evidence.verify(plan['input_stream_manifest'], stream_path)
    stream = evidence.json(stream_path)
    docs = stream['documents']
    require(stream.get('schema') == 'm005_numerical_document_stream_v1', 'wrong frozen stream schema')
    require(plan.get('full_target_documents') == len(docs) == 1024, 'formal target is exactly1024 documents')
    require(plan.get('domain_counts') == DOMAIN_COUNTS and Counter(row['domain'] for row in docs) == Counter(DOMAIN_COUNTS), 'formal domain quotas differ')
    require(len({row['doc_id'] for row in docs}) == len(docs) and len({row['duplicate_cluster'] for row in docs}) == len(docs), 'duplicate target document/cluster')
    require(all(row['split'] == 'eval' and row['evidence_role'] == 'formal_eval' for row in docs), 'nonformal target role')
    require(all(type(row['tokens']) is int and 1 <= row['tokens'] <= 128 for row in docs), 'invalid frozen token length')
    batches = plan['batches']
    require(len({row['batch_id'] for row in batches}) == len(batches), 'duplicate planned batch')
    ordered = []
    for batch in batches:
        indices = batch['source_indices']
        require(all(type(index) is int and 0 <= index < len(docs) for index in indices), 'invalid batch source index')
        selected = [docs[index] for index in indices]
        require([row['doc_id'] for row in selected] == batch['doc_ids'] and len(selected) == batch['selected_documents'], 'batch plan identities differ')
        require(batch['actual_token_lengths'] == [row['tokens'] for row in selected], 'batch plan token lengths differ')
        require(Counter(row['domain'] for row in selected) == Counter(batch['domain_counts']), 'batch domain quota differs')
        ordered.extend(indices)
    require(ordered == plan['ordered_source_indices'] and sorted(ordered) == list(range(1024)), 'batch plan loses/repeats target documents')
    return plan, stream, {row['doc_id']: row for row in docs}, stream_identity


def _validate_input(directory, doc, evidence):
    import numpy as np
    row = evidence.json(directory / 'input_identity.json')
    require(row.get('doc_id') == doc['doc_id'] and row.get('text_sha256') == doc['text_sha256'] and row.get('tokens') == doc['tokens'], 'input document/length identity differs')
    require(row.get('retokenized') is False and row.get('token_artifact') == doc['token_artifact'], 'input was retokenized or artifact identity changed')
    evidence.verify(doc['token_artifact'])
    with np.load(doc['token_artifact']['path'], allow_pickle=False) as archive:
        require(set(archive.files) == {'input_ids', 'attention_mask', 'position_ids'}, 'frozen token array fields differ')
        arrays = {name: archive[name] for name in archive.files}
        require(all(value.dtype == np.int64 and value.shape == (doc['tokens'],) for value in arrays.values()), 'frozen token dtype/shape differs')
        require(np.all(arrays['attention_mask'] == 1) and np.array_equal(arrays['position_ids'], np.arange(doc['tokens'])), 'frozen input is padded/repositioned')
        require(row.get('input_ids') == arrays['input_ids'][None, :].tolist() and row.get('attention_mask') == arrays['attention_mask'][None, :].tolist(), 'actual model input differs from frozen token arrays')


def _consume_attempt(path, plan, targets, evidence):
    path = Path(path).resolve()
    receipt = evidence.json(path / 'gpu_receipt.json')
    require(receipt.get('execution_state') == 'completed' and receipt.get('exit_code') == 0 and receipt.get('native_exit_code') == 0
            and receipt.get('stop_reason') is None and receipt.get('source_unchanged') is True
            and receipt.get('worker_reaped') is True, 'attempt failed/incomplete/source changed/not reaped: ' + str(path))
    result = evidence.json(path / 'paired_result.json')
    require(result.get('execution_state') == 'completed' and result.get('source_unchanged') is True
            and result.get('shared_weight_buffers_unchanged') is True, 'worker incomplete/changed source or weights: ' + str(path))
    manifest = evidence.json(path / 'paired_worker_manifest.json')
    launch = evidence.json(path / 'gpu_launch_manifest.json')
    plan_identity = evidence.files[str(Path(plan['_path']).resolve())]
    require(manifest['document_source']['sha256'] == plan_identity['sha256'], 'attempt consumed another formal plan')
    require(result.get('full_formal_target') == manifest.get('full_formal_target') == 1024, 'wrong worker target')
    batch_ids = result.get('formal_batch_ids')
    require(batch_ids and batch_ids == manifest.get('formal_batch_ids') and len(batch_ids) == len(set(batch_ids)), 'worker batch identities differ')
    by_batch = {row['batch_id']: row for row in plan['batches']}
    require(all(key in by_batch for key in batch_ids), 'unknown logical batch')
    order = [row['batch_id'] for row in plan['batches']]
    positions = [order.index(key) for key in batch_ids]
    require(positions == list(range(positions[0], positions[0]+len(positions))), 'worker logical batches are not consecutive frozen order')
    selected = [doc for key in batch_ids for doc in by_batch[key]['doc_ids']]
    reports = result['documents']
    require([row['doc_id'] for row in reports] == selected and [row['doc_id'] for row in manifest['selected_documents']] == selected, 'worker selected document list/order differs')
    require(result.get('measured_documents') == result.get('formal_eval_documents') == len(selected) and result.get('layers') == 32, 'worker formal counts differ')
    for row in manifest['selected_documents']:
        _check_identity(row, targets[row['doc_id']], 'worker manifest')
    declared = {row['path']: row['sha256'] for row in manifest['code']}
    launched = {row['path']: row['sha256'] for row in launch['source_identity']}
    require(declared and all(launched.get(key) == value for key, value in declared.items()), 'worker/supervisor source identity mismatch')
    require(len(manifest['code']) == len(declared) == 22 and {Path(key).name for key in declared} == CONSUMED_SOURCES,
            'formal consumed-source boundary must contain all frozen22 sources')
    core = {Path(key).name: value for key, value in declared.items() if Path(key).name in CORE_SOURCES}
    require(set(core) == CORE_SOURCES, 'core numerical source identity incomplete')
    loader = evidence.json(path / 'stream_loader_validation.json')
    require(loader.get('all_keys_loaded') is True and loader.get('no_meta_parameters_or_buffers') is True
            and loader.get('source_model_keys_match_exactly') is True, 'base weight loader validation failed')
    weight_identity = loader.get('consumed_base_model_identity_sha256')
    require(isinstance(weight_identity, str) and len(weight_identity) == 64, 'base weight identity missing')
    tokenizer = evidence.json(path / 'tokenizer_identity.json')
    require(tokenizer.get('tokenization_performed') is False and tokenizer['document_source']['sha256'] == plan['input_stream_manifest']['sha256'], 'wrong token stream/retokenization')
    groups = []
    for filename in ('tensor_metrics.jsonl', 'local_tensor_metrics.jsonl', 'dynamic_metadata.jsonl'):
        by_doc = defaultdict(list)
        for row in evidence.rows(path / filename):
            require(row.get('doc_id') in selected, 'unexpected document in ' + filename)
            by_doc[row['doc_id']].append(row)
        groups.append(by_doc)
    hidden, local, dynamic = groups
    documents = []
    for offset, report in enumerate(reports):
        doc_id = report['doc_id']; doc = targets[doc_id]
        require(report.get('tokens') == doc['tokens'], 'reported document token length differs')
        h, l, d = hidden[doc_id], local[doc_id], dynamic[doc_id]
        _check_coordinates(h, set(range(32)), lambda row: row['layer'], doc_id + ' hidden')
        _check_coordinates(l, LOCAL_KEYS, lambda row: (row['layer'], row['node'], row['op']), doc_id + ' local')
        _check_coordinates(d, DYNAMIC_KEYS, lambda row: (row['arm'], row['layer'], row['function'], row['ordinal']), doc_id + ' dynamic')
        for row in h + l:
            _check_identity(row, doc, 'metric ' + doc_id)
            _check_metric_counts(row, doc['tokens'])
        for row in h:
            require(row['node'] == 'decoder_hidden' and row['trajectory'] == 'v5_continuous_paired'
                    and row.get('output_shape') == [1, doc['tokens'], 4096], 'wrong hidden node/trajectory/shape')
        require(all(row['trajectory'] == 'v5_current_local_paired' for row in l), 'wrong local trajectory')
        for row in d:
            fields = {'codes_u8', 'shifts_u8', 'zero_points_u8', 'values_u8'} if row['function'] == 'prepare_fixed_activation' else {'codes_u8', 'shifts_u8', 'values_s12'}
            require(set(row.get('identity', {})) == fields, 'dynamic identity fields differ')
            require(all(isinstance(spec.get('sha256'), str) and len(spec['sha256']) == 64 and spec.get('shape') for spec in row['identity'].values()), 'invalid dynamic array identities')
            if row['function'] == 'prepare_fixed_activation':
                groups = 448 if row['ordinal'] == 3 else 128
                shapes = {name: ([doc['tokens'], groups, 32] if name == 'values_u8' else [doc['tokens'], groups]) for name in fields}
            else:
                shapes = {name: ([1, doc['tokens'], 8, 4, 32] if name == 'values_s12' else [1, doc['tokens'], 8, 4]) for name in fields}
            require(all(row['identity'][name]['shape'] == shapes[name] for name in fields), 'dynamic input geometry differs')
        directory = path / 'documents' / f'doc{offset:04d}'
        _validate_input(directory, doc, evidence)
        final_raw = evidence.json(directory / 'final_norm_comparison.json')
        _check_identity(final_raw, doc, 'final normalization')
        _check_metric_counts(final_raw, doc['tokens'])
        require(final_raw.get('node') == 'final_norm' and final_raw.get('trajectory') == 'v5_continuous_paired'
                and final_raw.get('output_shape') == [1, doc['tokens'], 4096], 'wrong final normalization geometry')
        family_bounds = {}
        all_positions = [position_metric(row) for row in l]
        for family in FAMILIES:
            family_bounds[family] = position_bound(row for row in all_positions if row['coordinate']['node'] == family)
        # Combine original positions, retaining exact-zero/invalid counts and precedence.
        total_bound = position_bound(all_positions)
        layers = []
        for row in sorted(h, key=lambda row: row['layer']):
            ratio = classify_metric(row.get('metrics', {}).get('current_vs_reference'))
            layers.append(dict(layer=row['layer'], relative_error=ratio, constraint_bound=constraint_bound([ratio])))
        final_ratio = classify_metric(final_raw.get('metrics', {}).get('current_vs_reference'))
        documents.append({**{key: doc[key] for key in IDENTITY_FIELDS}, 'tokens': doc['tokens'], 'attempt': str(path),
                          'local_family_bounds': family_bounds, 'local_five_family_bound': total_bound,
                          'propagation': layers, 'propagation_max_bound': constraint_bound(row['relative_error'] for row in layers),
                          'final_normalization': dict(relative_error=final_ratio, constraint_bound=constraint_bound([final_ratio])),
                          'coverage': dict(hidden_layers=32, local_coordinates=384, dynamic_coordinates=384, final_norm=1),
                          'strict_per_output_domain_available': False, 'exact_preoutput_reference': False})
    return documents, dict(path=str(path), batches=batch_ids, documents=len(documents), receipt=receipt,
                           consumed_sources=manifest['code'], consumed_source_identity=declared,
                           arithmetic_sources=core, base_model_identity=weight_identity)


def aggregate_formal(plan_path, stream_path, attempt_paths, *, allow_partial=False, domain_iid_assumed=True):
    evidence = Evidence()
    plan, stream, targets, _ = _validate_plan(plan_path, stream_path, evidence)
    plan['_path'] = str(Path(plan_path).resolve())
    paths = [Path(path).resolve() for path in attempt_paths]
    require(paths and len(set(paths)) == len(paths), 'explicit unique completed attempt paths required')
    documents, attempts, seen, clusters, batches = [], [], set(), set(), set()
    base_identity = core_identity = None
    for path in paths:
        rows, attempt = _consume_attempt(path, plan, targets, evidence)
        if core_identity is None:
            core_identity, base_identity = attempt['consumed_source_identity'], attempt['base_model_identity']
        require(attempt['consumed_source_identity'] == core_identity and attempt['base_model_identity'] == base_identity, 'incompatible consumed-source or base-weight identities across attempts; explicit version equivalence qualification required')
        require(not batches.intersection(attempt['batches']), 'logical batch repeated across attempts')
        batches.update(attempt['batches'])
        for row in rows:
            require(row['doc_id'] not in seen and row['duplicate_cluster'] not in clusters, 'document/cluster repeated across attempts')
            seen.add(row['doc_id']); clusters.add(row['duplicate_cluster']); documents.append(row)
        attempts.append(attempt)
    missing = [doc_id for doc_id in targets if doc_id not in seen]
    complete = not missing
    require(complete or allow_partial, 'target incomplete: explicitly allow a partial report; missing ' + str(len(missing)))
    order = {row['doc_id']: index for index, row in enumerate(stream['documents'])}
    documents.sort(key=lambda row: order[row['doc_id']])
    distributions = {}
    selectors = {**{'local_' + name: (lambda row, name=name: row['local_family_bounds'][name]) for name in FAMILIES},
                 'local_five_family_bound': lambda row: row['local_five_family_bound'],
                 'propagation_max_bound': lambda row: row['propagation_max_bound'],
                 'final_normalization_bound': lambda row: row['final_normalization']['constraint_bound']}
    selectors.update({'propagation_layer_' + f'{layer:02d}': (lambda row, layer=layer: row['propagation'][layer]['constraint_bound']) for layer in range(32)})
    for domain in (*DOMAIN_COUNTS, 'fixed_quota_pool'):
        selected = documents if domain == 'fixed_quota_pool' else [row for row in documents if row['domain'] == domain]
        distributions[domain] = {name: descriptive_distribution([selector(row) for row in selected], complete_target=complete,
                                                                fixed_quota_pool=domain == 'fixed_quota_pool', iid_assumed=domain_iid_assumed)
                                 for name, selector in selectors.items()}
    estimable = all(selector(row)['state'] != 'unestimable' for row in documents for selector in selectors.values())
    return dict(schema='m005_formal_numerical_aggregate_v1', execution_state='completed',
                target_state=('complete' if estimable else 'complete_with_unestimable_metrics') if complete else 'partial',
                collection_complete=complete, full_target_achieved=complete and estimable,
                planned_documents=1024, completed_documents=len(documents), missing_documents=len(missing), missing_doc_ids=missing,
                failed_supplied_attempts=0, invalid_supplied_attempts=0, invalid_attempt_policy='raise, never drop or silently treat as completed',
                unprovided_document_execution_status='unknown; missing does not imply failed',
                domain_counts_planned=DOMAIN_COUNTS, domain_counts_completed=dict(Counter(row['domain'] for row in documents)),
                ci_eligible_target_complete=complete, domain_iid_assumed=domain_iid_assumed, iid_verified=False,
                estimand='document maximum constraint bound over the five measured local node families; not all software operations',
                relative_ratio_zero_zero='null exact_zero_match; all-zero document constraint bound is0, separately identified',
                fixed_quota_pool_inference='descriptive_only', documents=documents, distributions=distributions,
                accepted_attempts=attempts, evidence_files=list(evidence.files.values()), aggregator_source=identity(__file__))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--stream', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, action='append', required=True)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--no-domain-iid-assumption', action='store_true')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    report = aggregate_formal(args.plan, args.stream, args.attempt, allow_partial=args.allow_partial,
                              domain_iid_assumed=not args.no_domain_iid_assumption)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    require(not any(args.output_dir.iterdir()), 'use a new empty aggregate directory')
    target = args.output_dir / 'formal_aggregate.json'
    with target.open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({key: report[key] for key in ('target_state', 'planned_documents', 'completed_documents', 'missing_documents', 'domain_counts_completed')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
