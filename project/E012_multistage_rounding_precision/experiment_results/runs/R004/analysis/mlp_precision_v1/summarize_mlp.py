"""Read-only MLP projection summary of explicitly reviewed local metrics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

OPS = ('gate_proj', 'up_proj', 'down_proj')


def identity(path):
    return dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def state(value, state_type=None, **extra):
    return dict(state='finite' if value is not None else state_type,
                value=value, **extra)


def site_bound(row):
    m = row['metrics']['current_vs_reference']
    n, e, s = m['valid_elements'], m['error_energy'], m['signal_energy']
    if (type(n) is not int or n <= 0 or m['nonfinite_elements'] != 0
            or not all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in (e, s))):
        return state(None, 'unestimable', reason='invalid_energy_or_domain')
    if s == 0:
        if e == 0:
            if m['relative_l2_percent'] is not None:
                raise ValueError('zero/zero original ratio must remain null')
            return state(0.0, exact_zero_match=True, original_relative_l2_percent=None)
        if m['relative_l2_percent'] is not None:
            raise ValueError('unbounded original ratio must remain null')
        return state(None, 'unbounded', reason='zero_reference_nonzero_error')
    ratio = 100 * math.sqrt(e / s)
    recorded = m['relative_l2_percent']
    if recorded is None or not math.isfinite(recorded) or not math.isclose(ratio, recorded, rel_tol=1e-12, abs_tol=1e-14):
        raise ValueError('recorded local ratio disagrees with original energies')
    return state(recorded, exact_zero_match=False, original_relative_l2_percent=recorded)


def document_max(rows):
    sites = [dict(layer=r['layer'], bound=site_bound(r), metrics=r['metrics']['current_vs_reference']) for r in rows]
    if any(x['bound']['state'] == 'unestimable' for x in sites):
        result = state(None, 'unestimable', reason='required_site_unestimable')
    elif any(x['bound']['state'] == 'unbounded' for x in sites):
        result = state(None, 'unbounded', reason='zero_reference_nonzero_error')
    else:
        value = max(x['bound']['value'] for x in sites)
        winners = [x for x in sites if x['bound']['value'] == value]
        winner = min(winners, key=lambda x: x['layer'])
        result = state(value, argmax_layer=winner['layer'], tie_count=len(winners),
                       argmax_metrics=winner['metrics'], all_zero_exact=all(x['bound'].get('exact_zero_match', False) for x in sites))
    result['sites'] = sites
    return result


def quantile(bounds, numerator, denominator):
    if any(x['state'] == 'unestimable' for x in bounds):
        return state(None, 'unestimable', reason='required_document_unestimable')
    values = sorted(math.inf if x['state'] == 'unbounded' else x['value'] for x in bounds)
    lo, rem = divmod((len(values) - 1) * numerator, denominator)
    hi = lo + bool(rem)
    if math.isinf(values[lo]) or (rem and math.isinf(values[hi])):
        return state(None, 'unbounded', reason='positive_quantile_weight_on_infinity')
    value = values[lo] if not rem else values[lo] + (values[hi] - values[lo]) * rem / denominator
    return state(value)


def summarize(attempt):
    local_path = attempt / 'local_tensor_metrics.jsonl'
    aggregate_path = attempt / 'aggregate_v1/formal_aggregate.json'
    audit_path = attempt / 'independent_audit/generic_v2.json'
    aggregate = json.loads(aggregate_path.read_text())
    audit = json.loads(audit_path.read_text())
    if audit['execution_state'] != 'completed' or audit['review'] != 'limited_evidence_verified':
        raise ValueError('reviewed B001 evidence required')
    if Path(audit['attempt']).resolve() != attempt.resolve():
        raise ValueError('audit attempt mismatch')
    documents = aggregate['documents']
    ids = {x['doc_id'] for x in documents}
    if len(ids) != aggregate['completed_documents'] or len(ids) != 16:
        raise ValueError('this qualification targets reviewed B00116')
    by_doc = {doc_id: {op: [] for op in OPS} for doc_id in ids}
    for line in local_path.read_text().splitlines():
        row = json.loads(line)
        if row['doc_id'] not in ids:
            raise ValueError('unreviewed local document')
        if row['op'] not in OPS:
            continue
        if row['node'] != 'linear' or row['trajectory'] != 'v5_current_local_paired':
            raise ValueError('incorrect projection comparison')
        if row['node_metadata']['comparison'] != 'current_vs_output_only_common_exit':
            raise ValueError('incorrect reference semantics')
        by_doc[row['doc_id']][row['op']].append(row)
    result_docs = []
    for doc in documents:
        record = {key: doc[key] for key in ('doc_id', 'domain', 'duplicate_cluster')}
        record['projections'] = {}
        for op in OPS:
            rows = by_doc[doc['doc_id']][op]
            if len(rows) != 32 or {r['layer'] for r in rows} != set(range(32)):
                raise ValueError('missing/duplicate MLP layer coordinate')
            record['projections'][op] = document_max(sorted(rows, key=lambda r: r['layer']))
        result_docs.append(record)
    summaries = {}
    for op in OPS:
        values = [x['projections'][op] for x in result_docs]
        summaries[op] = dict(documents=len(values), layer_sites=32 * len(values),
                             finite_documents=sum(x['state'] == 'finite' for x in values),
                             unbounded_documents=sum(x['state'] == 'unbounded' for x in values),
                             unestimable_documents=sum(x['state'] == 'unestimable' for x in values),
                             all_zero_exact_documents=sum(x.get('all_zero_exact', False) for x in values),
                             p50=quantile(values, 50, 100), p95=quantile(values, 95, 100),
                             maximum=quantile(values, 1, 1))
    return dict(schema='m005_b001_mlp_projection_precision_v1',
                execution_state='completed', research_verdict='descriptive_partial_only',
                planned_documents=aggregate['planned_documents'], completed_documents=len(ids),
                missing_documents=aggregate['missing_documents'], independent_unit='document_cluster; independence assumption not verified',
                units='percent', comparison='same-input current versus output-only common exit',
                estimand='per-document per-projection maximum over all 32 layers',
                denominator='all accepted real output coordinates; not a strict per-output-domain statistic',
                quantile_method='linear interpolation, extended nonnegative reals; unestimable never dropped',
                zero_rule='local 0/0 remains null; zero exact match adds no constraint; all-zero document constraint bound=0 with flag',
                confidence_intervals=None, documents=result_docs, projections=summaries,
                sources=[identity(p) for p in (local_path, aggregate_path, audit_path, Path(__file__))])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.attempt)
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result['projections'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
