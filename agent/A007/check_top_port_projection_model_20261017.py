#!/usr/bin/env python3
"""Finite incidence transpose check; no native tool equivalence/performance claim."""
from itertools import product
from pathlib import Path
import hashlib
import json


def partitions(items):
    if not items:
        yield []
        return
    head, *tail = items
    for rest in partitions(tail):
        yield [{head}, *rest]
        for i in range(len(rest)):
            yield [group | {head} if j == i else group for j, group in enumerate(rest)]


segments = set(range(4))
subsets = [{n for n in segments if bits & (1 << n)} for bits in range(16)]
ports = ['data[0]', 'data[1]']
cases = 0
partitions_seen = 0
for groups in partitions(list(range(4))):
    partitions_seen += 1
    for attached in product(subsets, repeat=len(ports)):
        incidence = dict(zip(ports, attached))
        closure = {p: set().union(*(g for g in groups if g & incidence[p])) for p in ports}
        for group in groups:
            direct = {p for p in ports if incidence[p] & group}
            projected = {p for p in ports if closure[p] & group}
            assert direct == projected
            cases += 1

def role(direction):
    return {'IN': 'DRIVER', 'OUT': 'LOAD', 'INOUT': 'INOUT'}.get(direction, 'UNKNOWN')

directions = ['IN', 'OUT', 'INOUT', 'MIXED', 'UNKNOWN', '']
role_cases = []
for a, b in product(directions, repeat=2):
    direct = [('TOP_PORT', ports[0], a, role(a)), ('TOP_PORT', ports[1], b, role(b))]
    projected = [('TOP_PORT', p, d, role(d)) for p, d in zip(ports, [a, b])]
    assert direct == projected
    role_cases.append([a, b])

# Each violates one necessary qualification and demonstrates why it matters.
counterexamples = {
    'partial_candidate_alias_scope': dict(full_group=['top', 'child'], direct_port_segment='top',
                                         partial_query=['child'], direct_has_port=False, closure_join_has_port=True),
    'one_representative_without_complete_closure': dict(full_group=['a', 'z'], canonical='a',
                                                       port_attached_segment='z', full_join=True, representative_only_join=False),
    'bus_name_collapse': dict(real_ports=['data[0]', 'data[1]'], real_attached=['net0', 'net1'],
                              collapsed='data', preserved_endpoint_identities=False),
    'missing_global_port': dict(native_ports=['a', 'b'], global_inventory=['a'],
                                candidate_net_port='b', projection_wrongly_empty=True),
    'buffer_or_clock_relation_substituted': dict(port_net='external_clk', candidate_net='buffered_clk',
                                                same_clock_object=True, same_electrical_alias_group=False,
                                                clock_source_join_wrongly_adds_port=True),
    'unknown_direction_filter': dict(native_direction='MIXED', expected_role='UNKNOWN',
                                     filtering_to_known_directions_loses_boundary=True),
    'cache_crosses_design_mutation': dict(before_port_net='old', after_port_net='new',
                                         reused_old_index_omits_current_boundary=True),
}
result = dict(execution='pure_finite_graph_model', partitions=partitions_seen,
              complete_incidence_alias_comparisons=cases, direction_identity_comparisons=len(role_cases),
              all_complete_projection_equal=True, counterexamples=counterexamples,
              statement='For a complete port universe P, reciprocal incidence R, equivalence-class alias closure C, and complete candidate group S=C(s), {p: exists n in S, R(p,n)} equals {p: union(C(n) for R(p,n)) intersects S}.',
              limitations='Mathematical finite model only; native Vivado API universe/reciprocity/bus/closure qualification and performance are not tested.')
root = Path(__file__).resolve().parents[2]
out = root / 'agent/A007/top_port_projection_model_20261017.json'
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(path=str(out), bytes=out.stat().st_size, sha256=hashlib.sha256(out.read_bytes()).hexdigest(), cases=cases)))
