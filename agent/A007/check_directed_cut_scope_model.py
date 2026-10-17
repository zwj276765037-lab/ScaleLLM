"""Exhaustive small graph check of a proposed scope, not Vivado validation.

The caller's native role inventory and actual candidate-leaf membership are
explicit assumptions. No production extractor, EDA tool or native API is used.
"""
from itertools import product
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

def select(endpoints, role_membership_complete):
    drivers=[i for i,e in enumerate(endpoints) if e['role']=='DRIVER']
    unresolved=any(e['role'] in ('INOUT','UNKNOWN') for e in endpoints)
    reduce=(role_membership_complete and not unresolved and len(drivers)==1
            and not endpoints[drivers[0]]['inside'])
    if not reduce:
        return set(range(len(endpoints))), 'FULL_FALLBACK_OR_CANDIDATE_DRIVER'
    return {i for i,e in enumerate(endpoints)
            if e['inside'] or e['raw_candidate'] or e['kind']=='TOP_PORT'
            or e['role']=='DRIVER'}, 'COMPLETE_DIRECTED_CUT_INGRESS_PEERS_OMITTED'

def cross_edges(endpoints, retained):
    return {(d,l) for d in retained for l in retained
            if endpoints[d]['role']=='DRIVER' and endpoints[l]['role']=='LOAD'
            and endpoints[d]['inside'] != endpoints[l]['inside']}

def timing_scope(endpoints, retained):
    drivers=[i for i in retained if endpoints[i]['role']=='DRIVER']
    if len(drivers)!=1 or any(endpoints[i]['role'] in ('INOUT','UNKNOWN') for i in retained):
        return 'UNRESOLVED', {i for i in retained if endpoints[i]['inside']}
    inside_driver=endpoints[drivers[0]]['inside']
    direction='EGRESS' if inside_driver else 'INGRESS'
    return direction, {i for i in retained if endpoints[i]['role']=='LOAD'
                       and endpoints[i]['inside'] != inside_driver}

variants=[dict(kind=kind,inside=inside,raw_candidate=raw,role=role)
          for kind,inside,raw in [('LEAF_PIN',False,False),('LEAF_PIN',False,True),
                                  ('LEAF_PIN',True,True),('TOP_PORT',False,False)]
          for role in ('DRIVER','LOAD','INOUT','UNKNOWN')]
counts=Counter();examples={}
for n in range(1,5):
    for endpoints in product(variants,repeat=n):
        full=set(range(n))
        for complete in (False,True):
            kept,scope=select(endpoints,complete)
            counts['cases']+=1;counts[scope]+=1
            assert cross_edges(endpoints,kept)==cross_edges(endpoints,full)
            assert timing_scope(endpoints,kept)==timing_scope(endpoints,full)
            assert all(i in kept for i,e in enumerate(endpoints)
                       if e['inside'] or e['raw_candidate'] or e['kind']=='TOP_PORT'
                       or e['role'] in ('DRIVER','INOUT','UNKNOWN'))
            assert all(not endpoints[i]['inside'] and endpoints[i]['kind']=='LEAF_PIN'
                       and endpoints[i]['role']=='LOAD' for i in full-kept)
            if not complete or any(e['role'] in ('INOUT','UNKNOWN') for e in endpoints):
                assert kept==full
            if kept!=full:
                counts['cases_with_actual_peer_omission']+=1
                examples.setdefault('ingress_with_peer_omission',dict(endpoints=endpoints,retained_indices=sorted(kept),omitted_indices=sorted(full-kept)))
path=Path(__file__)
result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),execution='CPU_finite_model_exhaustive_check_complete',
            verdict='directed_cut_edges_and_existing_directional_timing_scopes_preserved_under_explicit_assumptions',
            applicability='All 1..4 endpoint graphs with DRIVER/LOAD/INOUT/UNKNOWN and inside leaf/outside leaf/RAW-only leaf/top-port ownership; no native graph qualification or speed claim',
            counts=dict(counts),examples=examples,
            assumptions=['Complete canonical alias and leaf/top role inventory','Exact same-stage candidate leaf membership derived from actual S/P including physical DSP children and native-origin copies','Any role/membership/query ambiguity falls back to original full enumeration'],
            implementation_status='PROPOSAL_NOT_IMPLEMENTED; R004 and E008 b59 unchanged',
            producer=dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
out=path.with_name('directed_cut_scope_model_check_20261017.json')
with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(output=str(out),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),counts=dict(counts)),indent=2))
