"""Strict, streaming R005 analysis. Final1024 only; no model execution."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal, localcontext
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import sys

LOCAL_COLUMNS = {
    'attention_linear': ('q_proj', 'k_proj', 'v_proj', 'o_proj'),
    'rope': ('query_rope', 'key_rope'), 'qk': ('qk',), 'softmax': ('softmax',), 'pv': ('pv',),
    'gate_proj': ('gate_proj',), 'up_proj': ('up_proj',), 'down_proj': ('down_proj',),
}
MLP_COLUMNS = {'gating_exit_loss': 'gating_multiply_total', 'whole_mlp': 'whole_mlp_local',
               'fixed_residual': 'mlp_fixed_residual_local'}
KEYS = (*LOCAL_COLUMNS, *MLP_COLUMNS, 'final_hidden', 'logits')
PER_ARM = ('silu_lookup', 'gating_multiply_total', 'gating_multiply_extra', 'down_host_total')
CURRENT = ('whole_mlp_local', 'mlp_fixed_residual_local')
PAIRED = ('mlp_branch_propagation', 'mlp_residual_input_propagation', 'mlp_residual_sum_propagation')
DOMAINS = {'web': 512, 'news': 256, 'reviews': 256}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def verified(source):
    current = identity(source['path'])
    require(current['sha256'] == source['sha256'], 'source SHA mismatch: ' + str(source['path']))
    return Path(current['path'])


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    # One JSONL row at a time; never read all group raw/metrics into memory.
    with Path(path).open() as stream:
        for number, line in enumerate(stream, 1):
            require(line.strip(), f'blank JSONL line {path}:{number}')
            yield json.loads(line)


def value(state, number=None, **metadata):
    return dict(state=state, value=float(number) if number is not None else None,
                value_decimal=str(number) if number is not None else None, **metadata)


def relative(metric, *, signal_key='signal_energy'):
    e, s = metric.get('error_energy'), metric.get(signal_key)
    if e is None or s is None:
        return value('unestimable', reason='missing_energy')
    E, S = Decimal(str(e)), Decimal(str(s))
    n = metric.get('valid_elements', metric.get('score_pairs'))
    if (not E.is_finite() or not S.is_finite() or E < 0 or S < 0
            or type(n) is not int or n <= 0
            or metric.get('nonfinite_elements', metric.get('nonfinite', 0)) != 0):
        return value('unestimable', reason='invalid_energy_or_coordinates')
    original = metric.get('relative_l2_percent')
    if S == 0:
        require(original is None, 'undefined original relative ratio must stay null')
        return value('exact_zero_match' if E == 0 else 'unbounded', reason='zero_reference',
                     original_relative_l2_percent=None)
    with localcontext() as ctx:
        ctx.prec = 60
        ratio = 100 * (E / S).sqrt()
    require(isinstance(original, (int, float)) and math.isclose(float(ratio), original, rel_tol=1e-11, abs_tol=1e-13),
            'reported relative ratio differs from original energies')
    return value('finite', ratio, original_relative_l2_percent=original)


def maximum(sites, required):
    require(len(sites) == required, 'missing required coordinates cannot be filled from successful subset')
    if any(s['bound']['state'] == 'unestimable' for s in sites):
        return value('unestimable', reason='required_position_unestimable',
                     observed_unbounded=any(s['bound']['state'] == 'unbounded' for s in sites))
    if any(s['bound']['state'] == 'unbounded' for s in sites):
        return value('unbounded', reason='zero_reference_nonzero_error')
    finite = [(Decimal(0) if s['bound']['state'] == 'exact_zero_match' else Decimal(s['bound']['value_decimal']), s) for s in sites]
    largest = max(x[0] for x in finite)
    winners = [site for number, site in finite if number == largest]
    first = min(winners, key=lambda site: tuple(site['coordinate']))
    return value('finite', largest, all_zero_exact=all(s['bound']['state'] == 'exact_zero_match' for s in sites),
                 exact_zero_match_positions=sum(s['bound']['state'] == 'exact_zero_match' for s in sites),
                 required_positions=required, max_coordinate=first['coordinate'], tie_count=len(winners),
                 argmax_context=first.get('context'), original_argmax_relative_ratio=first['bound'])


def quantile(points, p):
    if any(x['state'] == 'unestimable' for x in points):
        return value('unestimable', reason='required_document_unestimable')
    ordered = sorted(Decimal('Infinity') if x['state'] == 'unbounded' else Decimal(x['value_decimal']) for x in points)
    with localcontext() as ctx:
        ctx.prec = 60
        rank = Decimal(p) * (len(ordered) - 1)
        lo, fraction = int(rank), rank - int(rank)
        if not fraction:
            number = ordered[lo]
        elif ordered[lo].is_infinite() or ordered[lo + 1].is_infinite():
            number = Decimal('Infinity')
        else:
            number = ordered[lo] + fraction * (ordered[lo + 1] - ordered[lo])
    return value('unbounded', reason='positive_quantile_weight_on_infinity') if number.is_infinite() else value('finite', number)


@lru_cache(maxsize=16)
def _ranks(n, p):
    experiment = Path(__file__).resolve().parents[7] / 'project/software/0_Software/rounding_precision/experiment'
    if str(experiment) not in sys.path:
        sys.path.insert(0, str(experiment))
    from metric_uncertainty import rank_interval
    return rank_interval(n, p, alpha='0.05', family_size=1)


def describe(points, *, domain_conditional=False):
    out = dict(documents=len(points), finite=sum(x['state'] == 'finite' for x in points),
                unbounded=sum(x['state'] == 'unbounded' for x in points),
                unestimable=sum(x['state'] == 'unestimable' for x in points),
                all_zero_exact=sum(x.get('all_zero_exact', False) for x in points),
                p50=quantile(points, '.5'), p95=quantile(points, '.95'), p99=quantile(points, '.99'), maximum=quantile(points, '1'),
                conditional_intervals={}, iid_verified=False,
                interval_scope='within-domain iid assumed, not verified; pointwise metric and quantile, family_size=1' if domain_conditional else 'fixed-quota pool descriptive only; no CI')
    if domain_conditional and not out['unestimable']:
        ordered = sorted(Decimal('Infinity') if x['state'] == 'unbounded' else Decimal(x['value_decimal']) for x in points)
        for name, p in [('p50', '.5'), ('p95', '.95'), ('p99', '.99')]:
            ranks = _ranks(len(ordered), p)
            low, high = ranks['lower_rank'], ranks['upper_rank']
            lower = ordered[low-1] if low else Decimal(0)
            upper = ordered[high-1] if high <= len(ordered) else Decimal('Infinity')
            encode = lambda x: value('unbounded', reason='infinite_rank_or_value_endpoint') if x.is_infinite() else value('finite', x)
            out['conditional_intervals'][name] = dict(ranks, lower=encode(lower), upper=encode(upper),
                support_lower=0, upper_rank_outside_sample=high > len(ordered), confidence=.95,
                assumption='conditional on unverified within-domain iid document sampling; not a joint guarantee across categories/domains')
    return out


def _audit(source, attempt, ids, kind, expected_sha, session):
    audit = read(verified(source))
    require(audit['execution_state'] == 'completed' and audit['review'] == 'limited_evidence_verified', 'independent audit not completed')
    require(Path(audit['attempt']).resolve() == attempt, 'independent audit attempt identity differs')
    require(audit['source_identity']['sha256'] == expected_sha, 'independent audit source version differs')
    verified(audit['source_identity'])
    runtime = audit['runtime_binding']
    require(runtime['canonical_group'] == str(attempt) and runtime['shared_process'] is True
            and runtime['shared_worker_identity'] == session['shared_worker_identity'], 'independent audit runtime binding differs')
    require(Path(runtime['session']).resolve() == Path(session['receipt_path']).parent
            and runtime['global_receipt']['sha256'] == session['session_gpu_receipt']['sha256']
            and runtime['global_launch']['sha256'] == session['session_launch_manifest']['sha256'],
            'independent audit global receipt/launch identity differs')
    require(verified(runtime['group_receipt']) == attempt / 'execution_receipt.json', 'independent audit group receipt differs')
    if kind == 'core':
        require(audit['adapter_source_identity']['sha256'] == session['expected_extension_auditor_sha256'],
                'core runtime adapter auditor differs')
        verified(audit['adapter_source_identity'])
    records = audit['final_norm_by_doc'] if kind == 'core' else audit['documents']
    audited = [row['doc_id'] for row in records]
    require(len(audited) == len(set(audited)) and set(audited) == set(ids), 'independent review document coverage differs')
    require(audit['formal_eval_documents'] == len(ids), 'development audit cannot qualify final formal data')
    for key in ('code_mismatches', 'raw_theory_violations'):
        require(audit.get(key) in (None, 0), 'independent audit reported failure')
    return dict(source=identity(source['path']), auditor=audit['source_identity'], audit_doc_ids=audit['audit_doc_ids'])


def session_binding(source, expected_docs, expected_extension_sha):
    session = read(verified(source))
    require(session['schema'] == 'm005_r005_analysis_manifest_v1' and session['model_execution_complete'] is True
            and session['expected_documents'] == session['completed_documents'] == 1024 and session['missing_doc_ids'] == [],
            'completed full resident-session manifest required')
    require(session['actual_doc_ids'] == session['expected_doc_ids'] and set(session['actual_doc_ids']) == set(expected_docs)
            and len(session['actual_doc_ids']) == len(set(session['actual_doc_ids'])) == 1024,
            'resident-session target membership incomplete/duplicate')
    receipt_path, launch_path = verified(session['session_gpu_receipt']), verified(session['session_launch_manifest'])
    receipt, launch = read(receipt_path), read(launch_path)
    shared = session['shared_worker_identity']
    require(receipt['execution_state'] == 'completed' and receipt['native_exit_code'] == receipt['exit_code'] == 0
            and receipt['worker_reaped'] is True and receipt['source_unchanged'] is True and receipt.get('stop_reason') is None
            and receipt['shared_worker_identity'] == launch['shared_worker_identity'] == shared,
            'global worker must complete natively and be reaped before final aggregation')
    runtime_plan = read(verified(session['plan']))
    launched = {row['path']: row['sha256'] for row in launch['source_identity']}
    for item in runtime_plan['source_identities']:
        verified(item)
        require(launched.get(item['path']) == item['sha256'], 'session plan/global launch sources differ')
    groups = {row['group_id']: row for row in session['ordered_groups']}
    require(len(groups) == len(session['ordered_groups']) and groups, 'duplicate/empty session groups')
    require([g['group_id'] for g in runtime_plan['groups']] == [g['group_id'] for g in session['ordered_groups']]
            and [doc for g in runtime_plan['groups'] for doc in g['doc_ids']] == session['expected_doc_ids'],
            'completed session group order/target differs from frozen execution plan')
    for group in runtime_plan['groups']:
        require(Path(group['attempt_path']).resolve() == Path(groups[group['group_id']]['attempt_path']).resolve(),
                'completed session attempt path differs from frozen execution plan')
    return dict(**session, receipt_path=str(receipt_path), launch_path=str(launch_path), groups_by_id=groups,
                expected_extension_auditor_sha256=expected_extension_sha, source_identity=identity(source['path']))


def coverage_and_top1(documents):
    count = len(documents)
    require(count > 0, 'nonempty document set required')
    thresholds = documents[0]['logits']['score_thresholds']
    require(all(doc['logits']['score_thresholds'] == thresholds for doc in documents), 'threshold grid changed across groups')
    score_total = sum(doc['logits']['score_pairs'] for doc in documents)
    coverage = [dict(epsilon=epsilon, score_within_count=sum(doc['logits']['score_within_threshold_counts'][i] for doc in documents),
                     score_total_count=score_total, document_within_count=sum(doc['logits']['max_abs_logit_delta'] <= epsilon for doc in documents),
                     document_total_count=count) for i, epsilon in enumerate(thresholds)]
    matches = sum(doc['logits']['top1_match_count'] for doc in documents)
    tokens = sum(doc['logits']['top1_total_count'] for doc in documents)
    all_match = sum(doc['logits']['all_positions_top1_match'] for doc in documents)
    top1 = dict(document_equal_weight_mean=math.fsum(doc['logits']['top1_match_count'] / doc['logits']['top1_total_count'] for doc in documents) / count,
                token_weighted_match_count=matches, token_weighted_total_count=tokens, token_weighted_agreement=matches / tokens,
                all_positions_match_documents=all_match, total_documents=count, all_positions_match_document_fraction=all_match / count)
    return coverage, top1


def aggregate(manifest_path):
    m = read(manifest_path)
    require(m['schema'] == 'm005_r005_analysis_inputs_v1', 'explicit R005 analysis manifest required')
    plan_path, stream_path = verified(m['formal_plan']), verified(m['formal_stream'])
    plan, stream = read(plan_path), read(stream_path)
    require(plan['full_target_documents'] == 1024 and plan['domain_counts'] == DOMAINS, 'formal target differs')
    require(plan['input_stream_manifest']['sha256'] == m['formal_stream']['sha256'], 'formal plan/stream identity mismatch')
    target = {doc['doc_id']: doc for doc in stream['documents']}
    require(len(target) == 1024 and Counter(x['domain'] for x in target.values()) == Counter(DOMAINS), 'complete fixed quota target required')
    require(len({x['duplicate_cluster'] for x in target.values()}) == 1024, 'target duplicate clusters')
    session = session_binding(m['session_analysis_manifest'], target, m['expected_extension_auditor_sha256'])
    require([g['group_id'] for g in m['groups']] == [g['group_id'] for g in session['ordered_groups']],
            'analysis group order differs from completed resident-session declaration')
    expected_code = {x['path']: x['sha256'] for x in m['expected_worker_sources']}
    require(len(expected_code) == len(m['expected_worker_sources']) and expected_code, 'explicit unique worker source identities required')
    completed, accepted, evidence = {}, [], []
    seen_attempts, all_audits = set(), set()
    common_head = common_weights = common_rope_config = None
    for group in m['groups']:
        attempt = Path(group['attempt']).resolve()
        require(attempt not in seen_attempts, 'duplicate declared group attempt')
        seen_attempts.add(attempt)
        declared_group = session['groups_by_id'][group['group_id']]
        require(Path(declared_group['attempt_path']).resolve() == attempt, 'canonical group path differs')
        group_receipt_path = verified(declared_group['receipt'])
        require(group_receipt_path == attempt / 'execution_receipt.json', 'canonical group receipt path differs')
        receipt, worker, result = read(group_receipt_path), read(attempt / 'paired_worker_manifest.json'), read(attempt / 'paired_result.json')
        require(receipt['schema'] == 'm005_r005_persistent_group_receipt_v1'
                and receipt['execution_state'] == 'completed' and receipt['exit_code'] == 0
                and receipt['runtime_kind'] == 'segment_of_shared_gpu_worker' and receipt['coverage_complete'] is True
                and receipt['source_unchanged'] is True and receipt['shared_worker_identity'] == session['shared_worker_identity']
                and Path(receipt['global_receipt_path']).resolve() == Path(session['receipt_path'])
                and receipt['session_launch_identity']['sha256'] == session['session_launch_manifest']['sha256'],
                'group receipt is not a complete unchanged segment of the completed global worker')
        for output_identity in receipt['output_identities']:
            verified(output_identity)
        require(worker['schema'] == 'm005_r005_extended_document_stream_v1' and result['schema'] == 'm005_r005_extended_result_v1', 'wrong R005 worker/result schema')
        require(result['execution_state'] == 'completed' and result['required_extension_complete'] is True
                and result['source_unchanged'] is True and result['shared_weight_buffers_unchanged'] is True, 'incomplete changed worker')
        require(result['formal_eval_documents'] == result['measured_documents'] and result['full_formal_target'] == 1024, 'development/partial worker cannot qualify full target')
        code = {x['path']: x['sha256'] for x in worker['code']}
        require(len(code) == len(worker['code']) and code == expected_code, 'all declared worker sources must match across groups')
        launched = {x['path']: x['sha256'] for x in read(session['launch_path'])['source_identity']}
        require(all(launched.get(path) == sha for path, sha in code.items()), 'source launch/worker mismatch')
        for source in worker['code']:
            verified(source)
        loader_path = Path(receipt['session_path']) / 'stream_loader_validation.json'
        loader = read(loader_path)
        require(loader.get('all_keys_loaded') is True and loader.get('no_meta_parameters_or_buffers') is True
                and loader.get('source_model_keys_match_exactly') is True, 'base loader qualification incomplete')
        weights = loader.get('consumed_base_model_identity_sha256')
        require(isinstance(weights, str) and len(weights) == 64 and common_weights in (None, weights),
                'missing/different consumed base-weight identities')
        common_weights = weights
        attach = read(attempt / 'v5_attach_metadata.json')
        rope_source = attach['rope_config_adapter']['source']
        verified(rope_source)
        require(common_rope_config in (None, rope_source['sha256']), 'different frozen RoPE checkpoint config')
        common_rope_config = rope_source['sha256']
        require(attach['mlp_full_format_id'] == '0x48384605' and attach['mlp_down_output_width'] == 32
                and attach['mlp_down_accumulator_compute_width'] == 54 and attach['mlp_group_guard_compute_width'] == 45
                and attach['strict_total_shift'] is True and attach['total_shift_policy'] == 'strict_rtl',
                'actual format05 attach contract differs')
        tokenizer = read(attempt / 'tokenizer_identity.json')
        require(tokenizer['tokenization_performed'] is False and tokenizer['document_source']['sha256'] == m['formal_stream']['sha256'],
                'retokenized/different frozen input stream')
        head = read(verified(result['output_head_source']))
        require(worker['document_source']['sha256'] == m['formal_plan']['sha256'], 'group selected different formal plan')
        selected = worker['selected_documents']
        ids = [x['doc_id'] for x in selected]
        require(ids == group['doc_ids'] == [x['doc_id'] for x in result['documents']], 'declared group membership/order differs')
        require(ids == receipt['doc_ids'] == receipt['completed_doc_ids'], 'resident receipt membership differs')
        require(len(ids) == len(set(ids)) == result['measured_documents'], 'duplicate/incomplete group document IDs')
        for doc in selected:
            require(doc['doc_id'] in target and doc['doc_id'] not in completed, 'duplicate/unknown completed document')
            original = target[doc['doc_id']]
            require(all(doc.get(k) == original.get(k) for k in ('domain', 'split', 'evidence_role', 'text_sha256', 'duplicate_cluster')), 'frozen document identity differs')
            require(doc['split'] == 'eval' and doc['evidence_role'] == 'formal_eval', 'nonformal document')
            verified(original['token_artifact'])
        audit_core = _audit(group['core_audit'], attempt, ids, 'core', m['expected_core_auditor_sha256'], session)
        audit_extension = _audit(group['extension_audit'], attempt, ids, 'extension', m['expected_extension_auditor_sha256'], session)
        expected_raw = {doc_id for doc_id in ids if target[doc_id]['raw_tensor_audit_selected']}
        require(set(audit_core['audit_doc_ids']) == set(audit_extension['audit_doc_ids']) == expected_raw, 'predeclared raw-audit coverage differs')
        all_audits |= expected_raw
        states = {doc_id: dict(local_seen=set(), mlp_seen=set(), hidden_seen=set(), dynamic_seen=set(),
                              columns={key: [] for key in KEYS}, propagation=[], silu_semantic_counts=Counter()) for doc_id in ids}
        def check_identity(row):
            doc_id = row['doc_id']
            require(doc_id in states, 'metric document outside declared group')
            for field in ('domain', 'text_sha256', 'duplicate_cluster'):
                if field in row:
                    require(row[field] == target[doc_id][field], 'metric document identity differs')
            return states[doc_id]
        for row in rows(attempt / 'local_tensor_metrics.jsonl'):
            st = check_identity(row)
            coordinate = row['layer'], row['node'], row['op']
            require(coordinate not in st['local_seen'], 'duplicate local coordinate')
            st['local_seen'].add(coordinate)
            require(row['trajectory'] == 'v5_current_local_paired' and row['node_metadata']['comparison'] == 'current_vs_output_only_common_exit', 'wrong local trajectory/reference')
            for key, ops in LOCAL_COLUMNS.items():
                if row['op'] in ops:
                    metric = row['metrics']['current_vs_reference']
                    st['columns'][key].append(dict(coordinate=coordinate, bound=relative(metric), context={k: metric.get(k) for k in ('signal_rms', 'absolute_max', 'normalized_signed_bias_percent')}))
        for row in rows(attempt / 'mlp_metrics.jsonl'):
            st = check_identity(row)
            coordinate = row['layer'], row['op'], row['arm']
            require(coordinate not in st['mlp_seen'], 'duplicate MLP coordinate')
            st['mlp_seen'].add(coordinate)
            require(row['node'] == 'mlp_extension', 'wrong MLP node')
            require(row['qualifiers']['mlp_audit_raw_metadata_bytes_per_document'] <= 8 << 20,
                    'MLP evidence budget exceeded')
            if row['op'] == 'silu_lookup':
                counts = row['metadata']['counts']
                require(counts['product_s32_overflow'] == counts['product_common_exit_mismatch'] == 0, 'MLP actual semantic mismatch/overflow')
                st['silu_semantic_counts'].update(counts)
            for key, op in MLP_COLUMNS.items():
                if row['op'] == op and row['arm'] == 'current':
                    st['columns'][key].append(dict(coordinate=coordinate, bound=relative(row['metrics']), context={k: row['metrics'].get(k) for k in ('signal_rms', 'absolute_max', 'normalized_signed_bias_percent')}))
        for row in rows(attempt / 'tensor_metrics.jsonl'):
            st = check_identity(row)
            require(row['layer'] not in st['hidden_seen'], 'duplicate hidden layer')
            st['hidden_seen'].add(row['layer'])
            st['propagation'].append(dict(layer=row['layer'], ratio=relative(row['metrics']['current_vs_reference'])))
        for row in rows(attempt / 'dynamic_metadata.jsonl'):
            st = check_identity(row)
            coordinate = row['arm'], row['layer'], row['function'], row['ordinal']
            require(coordinate not in st['dynamic_seen'], 'duplicate dynamic frontend coordinate')
            st['dynamic_seen'].add(coordinate)
        logit_ids = set()
        for logit in rows(attempt / 'logit_metrics.jsonl'):
            st = check_identity(logit)
            doc_id = logit['doc_id']
            require(doc_id not in logit_ids, 'duplicate logit document')
            logit_ids.add(doc_id)
            T, V = logit['tokens'], logit['vocab_size']
            require(T == target[doc_id]['tokens'] and V == 128256 and logit['score_pairs'] == T * V
                    and logit['nonfinite'] == logit['missing_positions'] == 0, 'incomplete full-vocabulary score coverage')
            require(logit['schema'] == 'm005_r005_full_vocab_v1' and logit['tie_break'] == 'smallest vocabulary ID', 'wrong logit/tie schema')
            thresholds, counts = logit['score_thresholds'], logit['score_within_threshold_counts']
            require(len(thresholds) == len(counts) and thresholds == sorted(set(thresholds))
                    and all(math.isfinite(x) and x >= 0 for x in thresholds), 'invalid threshold grid')
            require(all(type(x) is int and 0 <= x <= T * V for x in counts) and counts == sorted(counts), 'invalid score coverage counts')
            require(logit['top1_total_count'] == T and 0 <= logit['top1_match_count'] <= T
                    and logit['all_positions_top1_match'] == (logit['top1_match_count'] == T), 'invalid Top1 integer counts')
            require(sum(logit['per_token']['top1_matches']) == logit['top1_match_count'], 'Top1 per-token mismatch')
            require(math.isclose(logit['top1_agreement'], logit['top1_match_count'] / T, rel_tol=1e-13), 'Top1 fraction differs')
            E = logit['max_abs_logit_delta']
            require(math.isfinite(E) and E >= 0 and E == max(logit['per_token']['max_abs_logit_delta']), 'invalid full-vocabulary max absolute delta')
            require(common_head in (None, logit['head_sha256']), 'different shared output-head weights across documents/groups')
            require(logit['head_sha256'] == head['consumed_tensor_sha256'], 'actual head identity differs from logit row')
            common_head = logit['head_sha256']
            st['columns']['logits'].append(dict(coordinate=['logits'], bound=relative(logit, signal_key='reference_signal_energy')))
            st['logits'] = {k: logit[k] for k in ('tokens', 'vocab_size', 'score_pairs', 'score_thresholds', 'score_within_threshold_counts',
                'max_abs_logit_delta', 'max_abs_logprob_delta', 'top1_match_count', 'top1_total_count', 'all_positions_top1_match',
                'current_tied_positions', 'reference_tied_positions', 'margin_certified_count', 'relative_l2_percent', 'relative_l2_state')}
        require(logit_ids == set(ids), 'missing logit document')
        local_expected = {(layer, node, op) for layer in range(32) for key, ops in LOCAL_COLUMNS.items()
                          for op in ops for node in [('linear' if key in ('attention_linear', 'gate_proj', 'up_proj', 'down_proj') else key)]}
        mlp_expected = {(layer, op, arm) for layer in range(32) for arm, ops in [('current', PER_ARM), ('reference', PER_ARM), ('current', CURRENT), ('paired', PAIRED)] for op in ops}
        dynamic_expected = {(arm, layer, function, ordinal) for arm in ('current', 'reference') for layer in range(32)
                            for function, total in [('prepare_fixed_activation', 4), ('_kv12_quantize', 2)] for ordinal in range(total)}
        for index, doc_id in enumerate(ids):
            st, original = states[doc_id], target[doc_id]
            require(st['local_seen'] == local_expected and st['mlp_seen'] == mlp_expected and st['hidden_seen'] == set(range(32))
                    and st['dynamic_seen'] == dynamic_expected, 'incomplete32hidden/384local/416MLP/384dynamic coordinates')
            directory = attempt / 'documents' / f'doc{index:04d}'
            norm = read(directory / 'final_norm_comparison.json')
            require(norm['doc_id'] == doc_id, 'final normalization document pairing differs')
            evidence.append(identity(directory / 'final_norm_comparison.json'))
            evidence.append(identity(directory / 'input_identity.json'))
            st['columns']['final_hidden'].append(dict(coordinate=['final_hidden'], bound=relative(norm['metrics']['current_vs_reference'])))
            output = {key: original[key] for key in ('doc_id', 'domain', 'duplicate_cluster', 'text_sha256', 'tokens')}
            output['columns'] = {key: maximum(sites, 32 * len(LOCAL_COLUMNS[key]) if key in LOCAL_COLUMNS else (32 if key in MLP_COLUMNS else 1)) for key, sites in st['columns'].items()}
            output.update(logits=st['logits'], propagation=sorted(st['propagation'], key=lambda row: row['layer']),
                          silu_semantic_counts=dict(st['silu_semantic_counts']), attempt=str(attempt))
            completed[doc_id] = output
        accepted.append(dict(group_id=group['group_id'], attempt=str(attempt), doc_ids=ids, core_audit=audit_core, extension_audit=audit_extension))
        evidence.append(identity(loader_path))
        evidence.append(identity(group_receipt_path))
        for name in ('paired_worker_manifest.json', 'paired_result.json',
                     'local_tensor_metrics.jsonl', 'mlp_metrics.jsonl', 'tensor_metrics.jsonl', 'dynamic_metadata.jsonl', 'logit_metrics.jsonl',
                     'v5_attach_metadata.json', 'tokenizer_identity.json'):
            evidence.append(identity(attempt / name))
    require(set(completed) == set(target), 'final figure requires complete1024; missing/extra documents are not silently removed')
    require(len({group['group_id'] for group in accepted}) == len(accepted), 'duplicate actual group identifier')
    require(all_audits == set(plan['audit_candidate_doc_ids']), 'missing predeclared raw-audit documents')
    documents = [completed[doc_id] for doc_id in target]
    distributions = {'fixed_quota_pool': {key: describe([doc['columns'][key] for doc in documents]) for key in KEYS},
                     'domains': {domain: {key: describe([doc['columns'][key] for doc in documents if doc['domain'] == domain], domain_conditional=True) for key in KEYS} for domain in DOMAINS}}
    coverage, top1 = coverage_and_top1(documents)
    return dict(schema='m005_r005_final_precision_aggregate_v1', execution_state='completed', target_complete=True,
                planned_documents=1024, measured_documents=1024, missing_documents=0, domain_counts=DOMAINS,
                independent_unit='document source cluster; iid/semantic independence assumption not verified',
                fixed_quota_pool='descriptive only; no unconditional confidence intervals',
                quantile_definition='linear interpolation in extended nonnegative reals; unestimable never filtered',
                documents=documents, distributions=distributions, vocabulary_coverage=coverage, top1=top1,
                reference_notes=dict(gating_exit_loss='current common-exit product versus exact same-LUT multiplication, including shared exit loss',
                    other_local='same-input current versus retained-intermediate-precision reference with common exits',
                    overall='paired free-running final hidden/logits; fixed identical prefixes, not generated trajectory accuracy',
                    silu='same lookup/address semantics checked; not analytic SiLU loss and never a zero total-error plotted column'),
                actual_group_count=len(accepted), accepted_groups=accepted, raw_audit_documents=sorted(all_audits),
                input_manifest=identity(manifest_path), formal_plan=identity(plan_path), formal_stream=identity(stream_path),
                evidence_files=evidence, aggregator_source=identity(__file__), output_head_consumed_sha256=common_head,
                base_model_consumed_sha256=common_weights, rope_config_sha256=common_rope_config,
                resident_session_analysis=identity(m['session_analysis_manifest']['path']),
                uncertainty_source=identity(Path(__file__).resolve().parents[7] / 'project/software/0_Software/rounding_precision/experiment/metric_uncertainty.py'))


def write_outputs(data, directory):
    directory.mkdir(parents=True, exist_ok=True)
    require(not any(directory.iterdir()), 'new empty aggregate output directory required')
    with (directory / 'final_aggregate.json').open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    with (directory / 'document_values.csv').open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['doc_id', 'domain', 'tokens', 'category', 'state', 'value_percent', 'all_zero_exact'])
        for doc in data['documents']:
            for key, point in doc['columns'].items():
                writer.writerow([doc['doc_id'], doc['domain'], doc['tokens'], key, point['state'], point['value_decimal'], point.get('all_zero_exact', False)])
    with (directory / 'quantiles.csv').open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['scope', 'category', 'N', 'statistic', 'state', 'value_percent',
                         'conditional_ci_lower_state', 'conditional_ci_lower_percent', 'conditional_ci_upper_state', 'conditional_ci_upper_percent', 'iid_verified', 'interval_scope'])
        scopes = [('fixed_quota_pool', data['distributions']['fixed_quota_pool']), *data['distributions']['domains'].items()]
        for scope, values in scopes:
            for key, distribution in values.items():
                for stat in ('p50', 'p95', 'p99', 'maximum'):
                    point = distribution[stat]
                    interval = distribution['conditional_intervals'].get(stat)
                    writer.writerow([scope, key, distribution['documents'], stat, point['state'], point['value_decimal'],
                                     interval['lower']['state'] if interval else '', interval['lower']['value_decimal'] if interval else '',
                                     interval['upper']['state'] if interval else '', interval['upper']['value_decimal'] if interval else '',
                                     False, distribution['interval_scope']])
    with (directory / 'quantiles.md').open('x') as stream:
        stream.write('文档级统计；固定配额合池仅描述，非无条件置信保证。所有数值单位为%。\n\n|类别|P50|P95|P99|最大值|\n|---|---:|---:|---:|---:|\n')
        for key, distribution in data['distributions']['fixed_quota_pool'].items():
            cells = [f"{distribution[stat]['value']:.7g}" if distribution[stat]['state'] == 'finite' else distribution[stat]['state'] for stat in ('p50', 'p95', 'p99', 'maximum')]
            stream.write('|' + '|'.join([key, *cells]) + '|\n')
    with (directory / 'conditional_intervals.md').open('x') as stream:
        stream.write('域内95%次序统计量区间，条件为域内文档IID（未验证），每个指标/分位逐点family_size=1；不提供跨域或所有类别联合保证。固定配额合池仅描述。∞为真实无穷上端点，不以样本最大值代替。\n\n')
        for domain, distributions in data['distributions']['domains'].items():
            stream.write(f'域：{domain}\n\n|类别|分位|N|条件下界(%)|条件上界(%)|\n|---|---|---:|---:|---:|\n')
            for key, dist in distributions.items():
                for stat in ('p50', 'p95', 'p99'):
                    interval = dist['conditional_intervals'].get(stat)
                    labels = ['不可估', '不可估'] if interval is None else [
                        f"{interval[side]['value']:.7g}" if interval[side]['state'] == 'finite' else '∞' for side in ('lower', 'upper')]
                    stream.write(f"|{key}|{stat}|{dist['documents']}|{labels[0]}|{labels[1]}|\n")
            stream.write('\n')
    return [identity(path) for path in sorted(directory.iterdir()) if path.is_file()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    data = aggregate(args.manifest)
    outputs = write_outputs(data, args.output_dir)
    with (args.output_dir / 'output_manifest.json').open('x') as stream:
        json.dump(dict(schema='m005_r005_final_aggregate_outputs_v1', outputs=outputs, input=data['input_manifest'], source=data['aggregator_source']), stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
