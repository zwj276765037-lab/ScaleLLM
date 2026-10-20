"""Bounded interim extraction: EXACT G001..G029, no monitoring/final pipeline."""
from collections import Counter
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path

RUN = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('mlp_summary.json')
PROJECTIONS = ('gate_proj', 'up_proj', 'down_proj')
EXTENDED = {'whole_mlp': 'whole_mlp_local', 'fixed_residual': 'mlp_fixed_residual_local',
            'gating_exit_loss': 'gating_multiply_total'}
KEYS = (*PROJECTIONS, *EXTENDED)


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


def metric_bound(metric):
    E, S = metric.get('error_energy'), metric.get('signal_energy')
    original = metric.get('relative_l2_percent')
    if (E is None or S is None or metric.get('nonfinite_elements', 0) != 0
            or metric.get('valid_elements', 0) <= 0):
        return dict(state='unestimable', value=None, value_decimal=None, original_relative_ratio=original)
    e, s = Decimal(str(E)), Decimal(str(S))
    if not e.is_finite() or not s.is_finite() or e < 0 or s < 0:
        return dict(state='unestimable', value=None, value_decimal=None, original_relative_ratio=original)
    if s == 0:
        require(original is None, 'zero-reference original ratio must remain null')
        return dict(state='exact_zero_match' if e == 0 else 'unbounded', value=None, value_decimal=None, original_relative_ratio=None)
    with localcontext() as ctx:
        ctx.prec = 60
        ratio = Decimal(100) * (e / s).sqrt()
    require(original is not None and math.isclose(float(ratio), original, rel_tol=1e-11, abs_tol=1e-13), 'raw energies/recorded ratio differ')
    return dict(state='finite', value=float(ratio), value_decimal=str(ratio), original_relative_ratio=original)


def maximum(sites):
    require(len(sites) == 32 and {x['layer'] for x in sites} == set(range(32)), 'missing or duplicate required layer')
    states = Counter(x['bound']['state'] for x in sites)
    common = dict(required_layers=32, site_state_counts=dict(states))
    if states['unestimable']:
        return dict(state='unestimable', value=None, value_decimal=None, observed_unbounded=bool(states['unbounded']), **common)
    if states['unbounded']:
        return dict(state='unbounded', value=None, value_decimal=None, **common)
    number = lambda x: Decimal(0) if x['bound']['state'] == 'exact_zero_match' else Decimal(x['bound']['value_decimal'])
    largest = max(map(number, sites))
    winners = sorted([x for x in sites if number(x) == largest], key=lambda x: x['layer'])
    return dict(state='finite', value=float(largest), value_decimal=str(largest), all_zero_exact=states['exact_zero_match'] == 32,
                argmax_layer=winners[0]['layer'], tie_count=len(winners), argmax_original_ratio=winners[0]['bound'],
                argmax_metrics=winners[0]['metric'], **common)


def quantile(points, probability):
    if any(x['state'] == 'unestimable' for x in points):
        return dict(state='unestimable', value=None, value_decimal=None)
    values = sorted(Decimal('Infinity') if x['state'] == 'unbounded' else Decimal(x['value_decimal']) for x in points)
    with localcontext() as ctx:
        ctx.prec = 60
        rank = Decimal(probability) * (len(values) - 1)
        lo, fraction = int(rank), rank - int(rank)
        if not fraction:
            number = values[lo]
        elif values[lo].is_infinite() or values[lo + 1].is_infinite():
            number = Decimal('Infinity')
        else:
            number = values[lo] + fraction * (values[lo + 1] - values[lo])
    return dict(state='unbounded' if number.is_infinite() else 'finite', value=None if number.is_infinite() else float(number),
                value_decimal=None if number.is_infinite() else str(number))


def main():
    documents, sources, groups = {}, [], []
    common_code, common_shared = None, None
    source_cache = {}
    for g in range(1, 30):
        attempt = RUN / 'attempts' / f'AT{g+2:03d}_formal_resident_b{g:03d}'
        receipt_path = attempt / 'execution_receipt.json'
        receipt = json.loads(receipt_path.read_text())  # Missing G029 is an error, never skipped.
        require(receipt['schema'] == 'm005_r005_persistent_group_receipt_v1' and receipt['group_id'] == f'G{g:03d}'
                and receipt['execution_state'] == 'completed' and receipt['exit_code'] == 0
                and receipt['coverage_complete'] is True and receipt['source_unchanged'] is True, 'required group not completed/unchanged')
        ids = receipt['doc_ids']
        require(len(ids) == len(set(ids)) == 16 and ids == receipt['completed_doc_ids'], 'incomplete16-document group')
        require(common_shared in (None, receipt['shared_worker_identity']), 'shared worker changed')
        common_shared = receipt['shared_worker_identity']
        code = {x['path']: x['sha256'] for x in receipt['code']}
        require(common_code in (None, code), 'source identity set changed between selected groups')
        common_code = code
        for path, sha in code.items():
            if path not in source_cache:
                source_cache[path] = identity(path)
            require(source_cache[path]['sha256'] == sha, 'actual frozen source differs: ' + path)
        require(identity(receipt['session_launch_identity']['path'])['sha256'] == receipt['session_launch_identity']['sha256'], 'session launch identity changed')
        worker_path = attempt / 'paired_worker_manifest.json'
        worker = json.loads(worker_path.read_text())
        selected = worker['selected_documents']
        require([x['doc_id'] for x in selected] == ids, 'paired selected-document identity differs')
        for doc in selected:
            require(doc['doc_id'] not in documents, 'duplicate selected document')
            documents[doc['doc_id']] = dict(**doc, group_id=receipt['group_id'], columns={key: [] for key in KEYS})
        declared = {row['path']: row['sha256'] for row in receipt['output_identities']}
        for name in ('local_tensor_metrics.jsonl', 'mlp_metrics.jsonl'):
            path = attempt / name
            h, count = hashlib.sha256(), 0
            with path.open('rb') as stream:
                for line in stream:
                    h.update(line)
                    row = json.loads(line)
                    require(row['doc_id'] in ids, 'metric belongs to another group')
                    count += 1
                    if name.startswith('local'):
                        if row['op'] not in PROJECTIONS:
                            continue
                        require(row['trajectory'] == 'v5_current_local_paired' and row['node_metadata']['comparison'] == 'current_vs_output_only_common_exit', 'incorrect projection comparison')
                        key, metric = row['op'], row['metrics']['current_vs_reference']
                    else:
                        if row['arm'] != 'current' or row['op'] not in EXTENDED.values():
                            continue
                        key = next(key for key, op in EXTENDED.items() if op == row['op'])
                        metric = row['metrics']
                    documents[row['doc_id']]['columns'][key].append(dict(layer=row['layer'], bound=metric_bound(metric), metric=metric))
            require(count == 16 * (384 if name.startswith('local') else 416), 'unexpected full metric coordinate count')
            actual = dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())
            require(actual['sha256'] == declared[str(path)], 'metric file differs from completed group output identity')
            sources.append(actual)
        sources.extend([identity(receipt_path), identity(worker_path)])
        groups.append(dict(group_id=receipt['group_id'], attempt=str(attempt), documents=16, receipt=identity(receipt_path)))
    require(len(documents) == 464 and len({d['duplicate_cluster'] for d in documents.values()}) == 464, 'not exactly464 unique document clusters')
    all_site_counts = {key: Counter() for key in KEYS}
    for doc in documents.values():
        for key, sites in doc['columns'].items():
            all_site_counts[key].update(x['bound']['state'] for x in sites)
            doc['columns'][key] = maximum(sites)
    distributions = {}
    for key in KEYS:
        points = [doc['columns'][key] for doc in documents.values()]
        distributions[key] = dict(documents=464, document_state_counts=dict(Counter(x['state'] for x in points)),
            site_state_counts=dict(all_site_counts[key]), all_zero_exact_documents=sum(x.get('all_zero_exact', False) for x in points),
            p50=quantile(points, '.5'), p95=quantile(points, '.95'), maximum=quantile(points, '1'))
    output = dict(schema='m005_r005_interim464_mlp_v1', execution_state='completed', measured_documents=464,
        planned_documents=1024, missing_documents=560, selected_groups='EXACT G001..G029 / AT003..AT031', group_count=29,
        scope='bounded interim descriptive extraction; global native exit/final independent audits not asserted; no monitoring or final figure',
        statistics='each document maximum across32 layers, then linear descriptive quantiles; fixed-quota pool only; no CI',
        units='percent', comparisons={
            'gate_proj/up_proj/down_proj':'same-input current integer projection vs retained-intermediate-precision common-exit reference',
            'whole_mlp':'same actual MLP input, full current branch vs reference branch, both recompute own dynamic codes and use shared Host exit',
            'fixed_residual':'same second-residual base plus current/reference wholeMLP branches, compared after FP32 sum',
            'gating_exit_loss':'actual S32/F16 product vs exact same-LUT SiLU integer times up integer /2^32; includes shared exit rounding loss'},
        zero_policy='original local0/0 remains null; exact-zero positions impose no max constraint; all-zero max0 flagged; infinity and invalid never dropped',
        domain_counts=dict(Counter(doc['domain'] for doc in documents.values())), distributions=distributions,
        documents=list(documents.values()), groups=groups, raw_source_identities=sources,
        frozen_source_identities=list(source_cache.values()), script_identity=identity(__file__))
    with OUTPUT.open('x') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(distributions, indent=2))
    print('OUTPUT', identity(OUTPUT))


if __name__ == '__main__':
    main()
