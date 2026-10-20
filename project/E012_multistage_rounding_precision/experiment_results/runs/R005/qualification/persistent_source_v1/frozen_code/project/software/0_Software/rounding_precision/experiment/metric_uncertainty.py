"""Document-level distribution-free quantile intervals with explicit assumptions.

Frozen fixed-quota domain pools are descriptive, not iid pooled samples.
No interpolation, fake finite tail endpoint, scalar sample count or implicit
simultaneous coverage is used. Exact binomial tail ranks use integer arithmetic.
"""
from __future__ import annotations
from fractions import Fraction
from functools import lru_cache
import math


@lru_cache(maxsize=64)
def binomial_ranks(n,p='0.99',confidence='0.95',family_size=1):
    """A014 1-based ranks; x_0=-infinity, x_(n+1)=+infinity."""
    if type(n) is not int or n<1 or type(family_size) is not int or family_size<1:
        raise ValueError('positive document count and family size required')
    p=Fraction(str(p));confidence=Fraction(str(confidence))
    if not 0<p<1 or not 0<confidence<1:raise ValueError('probabilities must lie in (0,1)')
    tail=(1-confidence)/(2*family_size)
    numerator,denominator=p.numerator,p.denominator
    complement=denominator-numerator
    total=denominator**n
    weight=complement**n
    cumulative=0;lower=0;upper=n+1;lower_tail=0;upper_tail=0
    # At k, cumulative is P(B<=k-1) expressed with denominator total.
    for k in range(n+2):
        if k<=n and cumulative*tail.denominator<=total*tail.numerator:
            lower=k;lower_tail=cumulative
        if k>=1 and (total-cumulative)*tail.denominator<=total*tail.numerator:
            upper=k;upper_tail=total-cumulative
            break
        if k<=n:
            cumulative+=weight
            if k<n:
                product=weight*(n-k)*numerator
                divisor=(k+1)*complement
                weight,remainder=divmod(product,divisor)
                if remainder:raise ArithmeticError('binomial integer recurrence failed')
    coverage=Fraction(total-lower_tail-upper_tail,total)
    return dict(n=n,p=str(p),confidence=str(confidence),family_size=family_size,
                lower_rank=lower,upper_rank=upper,upper_unbounded=upper==n+1,
                lower_unbounded=lower==0,binomial_coverage=float(coverage),
                lower_tail_probability=float(Fraction(lower_tail,total)),
                upper_tail_probability=float(Fraction(upper_tail,total)),
                scope='pointwise' if family_size==1 else 'Bonferroni over explicitly supplied family',
                assumptions='independent identically distributed document units; continuous exact coverage, ties conservative')


def quantile_interval(values,p='0.99',confidence='0.95',family_size=1,*,iid_documents=False,
                      fixed_quota_pool=False,known_support=(None,None),pointwise_layers=True,estimator="linear"):
    """Null values are undefined zero-signal ratios, never imputed as zero."""
    values=list(values)
    if any(value is not None and (isinstance(value,bool) or not math.isfinite(float(value))) for value in values):
        raise ValueError('metrics must be finite numeric values or explicit null')
    ordered=sorted(float(value) for value in values if value is not None)
    if len(known_support)!=2 or any(v is not None and not math.isfinite(float(v)) for v in known_support):
        raise ValueError('known support endpoints must be finite or null')
    low,high=known_support
    if low is not None and high is not None and low>high:raise ValueError('support endpoints reversed')
    if ordered and ((low is not None and ordered[0]<low) or (high is not None and ordered[-1]>high)):
        raise ValueError('observed metrics contradict declared support')
    n=len(ordered);p_fraction=Fraction(str(p))
    if not 0<p_fraction<1:raise ValueError('quantile must lie in (0,1)')
    rank=(n*p_fraction.numerator+p_fraction.denominator-1)//p_fraction.denominator if n else None
    if estimator not in ('linear','nearest_rank'):raise ValueError('unknown descriptive quantile estimator')
    if n and estimator=='linear':
        location=float(p_fraction)*(n-1);left=int(math.floor(location));right=int(math.ceil(location))
        point=ordered[left]+(ordered[right]-ordered[left])*(location-left)
    else:point=ordered[rank-1] if n else None
    result=dict(document_count=len(values),defined_document_count=n,undefined_metric_documents=len(values)-n,
                zero_signal_handling='undefined relative ratios stay null; original zero/empty cause counts reported separately by runner',
                estimate=point,estimate_method=estimator,nearest_rank=rank,
                interval=None,iid_assumption_declared=iid_documents and not fixed_quota_pool,assumptions_verified=False,
                pooling='fixed-quota domains; descriptive only' if fixed_quota_pool else 'single specified document population',
                layer_coverage='pointwise; not simultaneous across32 layers' if family_size==1 else f'simultaneous only within the explicitly predeclared family of {family_size} comparisons')
    if not n:
        result['interval_status']='no_defined_document_metrics';return result
    if not result['iid_assumption_declared']:
        result['interval_status']='not_reported_without_iid_document_assumption';return result
    ranks=binomial_ranks(n,str(p_fraction),str(confidence),family_size)
    lower,upper=ranks['lower_rank'],ranks['upper_rank']
    lower_value=ordered[lower-1] if lower else known_support[0]
    upper_value=ordered[upper-1] if upper<=n else known_support[1]
    result['interval']={**ranks,'lower':lower_value,'upper':upper_value,
                        'lower_unbounded':lower==0 and known_support[0] is None,
                        'upper_unbounded':upper==n+1 and known_support[1] is None,
                        'known_support_applied':{'lower':lower==0 and known_support[0] is not None,
                                                 'upper':upper==n+1 and known_support[1] is not None}}
    result['interval_status']='conditional_on_stated_iid_document_assumption'
    return result


def planned_rank_table():
    return [dict(population=('pooled1024 iid hypothetical only; not the current fixed-quota pool' if n==1024 else f'within-domain n={n}; conditional iid'),
                 **binomial_ranks(n,p)) for n in (256,512,1024) for p in ('0.95','0.99')]


def rank_interval(n,p,alpha='0.05',family_size=1):
    result=binomial_ranks(n,str(p),str(1-Fraction(str(alpha))),family_size)
    return {**result,'actual_coverage_under_iid':result['binomial_coverage'],
            'family_scope':result['scope'],
            'family_coverage_lower_bound_under_iid':float(1-Fraction(str(alpha)))}


def order_statistic_interval(records,p='0.99',alpha='0.05',family_size=1,*,
                             sampling_model='descriptive_fixed_quota',estimator='linear',known_support=(None,None)):
    """One metric per explicit source-document ID; never accept repeated IDs as N."""
    records=list(records);seen=set()
    allowed={'single_domain_iid_assumed','descriptive_fixed_quota','descriptive_no_iid'}
    if sampling_model not in allowed:raise ValueError('explicit supported document sampling model required')
    reason_counts={};failed_collection=False
    for row in records:
        doc=row.get('doc_id')
        if not isinstance(doc,str) or not doc or doc in seen:raise ValueError('missing or duplicate document ID')
        seen.add(doc)
        status=row.get('status','ok')
        failed_collection |= status in ('failed','missing')
        if row.get('empty_valid_domain') and row['value'] is not None:
            raise ValueError('empty valid domain metric must be null')
        if row.get('zero_signal') and row['value'] is not None:
            raise ValueError('zero signal relative ratio must be null')
        if row['value'] is None:
            status=row.get('status','ok')
            reason=('zero_signal' if row.get('zero_signal') else 'empty_valid_domain' if row.get('empty_valid_domain')
                    else status if status in ('failed','missing') else row.get('undefined_reason'))
            if not reason:raise ValueError('null metric requires an explicit undefined/missing/failure reason')
            reason_counts[reason]=reason_counts.get(reason,0)+1
            failed_collection |= status in ('failed','missing')
    result=quantile_interval([row['value'] for row in records],str(p),str(1-Fraction(str(alpha))),family_size,
                             iid_documents=sampling_model=='single_domain_iid_assumed',
                             fixed_quota_pool=sampling_model=='descriptive_fixed_quota',
                             known_support=known_support,estimator=estimator)
    result.update(sampling_model=sampling_model,document_ids_verified_unique=True,
                  n_selected=len(records),n_defined=result['defined_document_count'],undefined_reason_counts=reason_counts,
                  target='document metric distribution conditional on defined ratio; no imputation for zero/empty signal',
                  support_source='caller-declared support must be frozen independently of observed sample extrema',
                  zero_signal_documents=sum(bool(row.get('zero_signal')) for row in records),
                  empty_valid_documents=sum(bool(row.get('empty_valid_domain')) for row in records),
                  family_scope='pointwise' if family_size==1 else f'Bonferroni predeclared M={family_size}; no wider family claim')
    if failed_collection:
        result['interval']=None
        result['interval_status']='not_reported_for_incomplete_predeclared_collection'
        result['target']='successful subset cannot stand for failed/missing predeclared documents'
    if not result['n_defined']:result['interval_status']='not_estimable'
    return result
