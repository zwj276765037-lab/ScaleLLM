import json, hashlib, math, statistics
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
R=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
identities=[]
def read(p):
    b=p.read_bytes()
    identities.append({'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
    return json.loads(b)
def quantiles(xs):
    assert xs and all(x is not None and math.isfinite(x) and x>=0 for x in xs)
    s=sorted(xs)
    def q(p):
        h=(len(s)-1)*p; lo=math.floor(h); hi=math.ceil(h)
        return s[lo]+(s[hi]-s[lo])*(h-lo)
    return dict(n=len(xs),p50=q(.5),p95=q(.95),p99=q(.99),maximum=s[-1])
rows=[]; groups=[]
for i in range(1,30):
    a=R/'attempts'/f'AT{i+2:03d}_formal_resident_b{i:03d}'
    receipt=read(a/'execution_receipt.json')
    assert receipt['execution_state']=='completed' and receipt['exit_code']==0
    assert receipt['coverage_complete'] and receipt['source_unchanged']
    assert receipt['group_id']==f'G{i:03d}'
    paths=sorted((a/'documents').glob('*/document_result.json'))
    assert len(paths)==16
    group_ids=[]
    for p in paths:
        d=read(p); l=read(p.parent/'logit_metrics.json')
        assert d['doc_id']==l['doc_id']
        assert d['coverage']['complete'] and d['mlp_coverage']['complete'] and d['logit_coverage']['complete']
        assert l['nonfinite']==l['missing_positions']==0
        assert l['score_pairs']==l['tokens']*l['vocab_size'] and l['vocab_size']==128256
        assert l['top1_total_count']==l['tokens']
        assert l['top1_match_count']==sum(l['per_token']['top1_matches'])
        assert len(l['per_token']['current_top1_ids'])==l['tokens']
        assert d['output_head_relative_l2_percent']==l['relative_l2_percent']
        rows.append((d,l)); group_ids.append(d['doc_id'])
    assert set(group_ids)==set(receipt['doc_ids'])==set(receipt['completed_doc_ids'])
    groups.append(receipt['group_id'])
assert len(rows)==464 and len({d['doc_id'] for d,l in rows})==464
thresholds=rows[0][1]['score_thresholds']
assert all(l['score_thresholds']==thresholds for d,l in rows)
tokens=sum(l['tokens'] for d,l in rows); scores=sum(l['score_pairs'] for d,l in rows)
matches=sum(l['top1_match_count'] for d,l in rows)
coverage=[]
for j,t in enumerate(thresholds):
    count=sum(l['score_within_threshold_counts'][j] for d,l in rows)
    doc_count=sum(l['max_abs_logit_delta']<=t for d,l in rows)
    coverage.append(dict(epsilon=t,score_within=count,score_total=scores,score_percent=100*count/scores,
        whole_document_within=doc_count,document_total=len(rows),document_percent=100*doc_count/len(rows)))
def summary(subrows):
    return dict(documents=len(subrows),tokens=sum(l['tokens'] for d,l in subrows),
        final_hidden_relative_l2_percent=quantiles([d['final_norm_relative_l2_percent'] for d,l in subrows]),
        logits_relative_l2_percent=quantiles([l['relative_l2_percent'] for d,l in subrows]),
        per_document_max_absolute_logit_difference=quantiles([l['max_abs_logit_delta'] for d,l in subrows]),
        top1_token_weighted_percent=100*sum(l['top1_match_count'] for d,l in subrows)/sum(l['tokens'] for d,l in subrows),
        top1_document_equal_weight_percent=100*statistics.mean(l['top1_match_count']/l['tokens'] for d,l in subrows),
        all_positions_match_documents=sum(l['all_positions_top1_match'] for d,l in subrows))
result=dict(schema='m005_r005_interim_464_v1',created_at=datetime.now(timezone.utc).isoformat(),
    status='provisional_completed_prefix_pending_global_independent_audit',planned_documents=1024,
    measured_documents=464,completed_groups=groups,domains=dict(Counter(l['domain'] for d,l in rows)),
    fixed_prefix_selection='first29predeclared16docgroups, no metric-based selection',
    tokens=tokens,score_pairs=scores,summary=summary(rows),
    by_domain={domain:summary([(d,l) for d,l in rows if l['domain']==domain]) for domain in sorted({l['domain'] for d,l in rows})},
    vocabulary_coverage=coverage,top1_match_count=matches,top1_total_count=tokens,
    margin_certified_count=sum(l['margin_certified_count'] for d,l in rows),
    top1_changed_positions=tokens-matches,nonfinite_count=sum(l['nonfinite'] for d,l in rows),
    missing_position_count=sum(l['missing_positions'] for d,l in rows),
    source_identities=identities,
    limitations=['intermediate prefix only; not all1024', 'global independent audit pending',
      'teacher-forced shared prefixes; no task accuracy or free generation claim',
      'fixed-domain quotas pooled descriptively; no unconditional confidence interval',
      'score coverage counts all vocabulary entries and is not probability-mass weighted'])
with (OUT/'interim_summary.json').open('x') as f: json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k not in ('source_identities','by_domain')},ensure_ascii=False,indent=2))
