"""Independent, CPU-only audit of the two closed native membership stages.

Only reads small native text tables and archives; never imports engineering
extractors, touches DCPs, controls processes, or mutates engineering sources.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import tkinter
from datetime import datetime, timezone

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RUN = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004'
ATT = RUN / 'attempts/AT001_exact_candidate_comparison'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R004_AT001_exact_candidate_comparison'
identities = {}


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    item = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    identities[str(path)] = item
    return item


def verify(item):
    actual = identity(item['path'])
    assert all(actual[k] == item[k] for k in ('bytes', 'sha256')), item['path']


def table(path, sep='\t', columns=None):
    identity(path)
    with Path(path).open() as stream:
        header = stream.readline().rstrip('\n').split('\t')
        if columns is not None:
            assert len(header) == columns
        result = []
        for line_no, line in enumerate(stream, 2):
            line = line.rstrip('\n')  # Preserve all spaces, including final empty field.
            assert sep != ' ' or '\t' not in line, (path, line_no)
            fields = line.split(sep)
            assert len(fields) == len(header), (path, line_no, len(fields), len(header))
            result.append(dict(zip(header, fields)))
    return result


def indexed(rows):
    result = {x['NAME']: x for x in rows}
    assert len(result) == len(rows)
    return result


def refmap(rows):
    return {name: row['REF_NAME'] for name, row in rows.items()}


def marker(path):
    identity(path)
    return dict(line.split('=', 1) for line in path.read_text().splitlines())


tcl = tkinter.Tcl()
assert tcl.eval('join [list a {} b] \t') == 'a  b'
assert tcl.eval('join [list a {} b] \\t') == 'a\t\tb'
results = {}
sets = {}
queries = table(REPORT / 'query_receipts.tsv')
for point in ('C01', 'C02'):
    fact_path = ATT / f'candidate_{point}_membership_resources_closed_facts.json'
    identity(fact_path)
    fact = json.loads(fact_path.read_text())
    for binding in [fact['input_bindings'], fact['target_authority'], fact['producer'], *fact['artifacts'], *fact['archived_sources_unchanged']]:
        verify(binding)
    raw, sem, phy = [indexed(table(REPORT / f'candidate_{tag}_{point}.tsv', columns=2)) for tag in ('RAW', 'S', 'P')]
    members = indexed(table(REPORT / f'candidate_membership_{point}.tsv', sep=' ', columns=24))
    parents = indexed(table(REPORT / f'candidate_physical_members_{point}.tsv', sep=' ', columns=18))
    sites = indexed(table(REPORT / f'candidate_site_members_{point}.tsv', sep=' ', columns=11))
    root = fact['target']['root']
    assert all(name.startswith(root + '/') for name in raw)
    assert refmap(sem) == {n: r['REF_NAME'] for n, r in raw.items() if r['REF_NAME'] not in ('GND', 'VCC')}
    assert refmap(members) == refmap(raw)
    assert refmap(parents) == refmap(phy)
    mapping, normalized = {}, []
    for name, row in members.items():
        ref = raw[name]['REF_NAME']
        parent = row['physical_parent']
        assert row['selected_RAW'] == '1'
        assert row['selected_S'] == str(int(name in sem))
        assert row['selected_P'] == str(int(parent in phy))
        assert row['mapping_reason'] == 'ACTUAL_NATIVE_MAPPING'
        if ref.startswith('DSP') and ref != 'DSP48E2':
            assert name.startswith(parent + '/') and phy[parent]['REF_NAME'] == 'DSP48E2'
            assert row['physical_REF'] == 'DSP48E2'
            normalized.append(dict(NAME=name, REF_NAME=ref, physical_parent=parent))
        else:
            assert parent == name and row['physical_REF'] == ref
        if name in sem:
            mapping[parent] = row['physical_REF']
    assert mapping == refmap(phy)
    # P and RAW observations of identical native objects must agree on common fields.
    for name, row in parents.items():
        if name in members:
            for key in set(row) & set(members[name]):
                assert row[key] == members[name][key], (point, name, key)
    assert set(parents) <= set(sites)
    touched = {row['LOC'] for row in parents.values()}
    assert '' not in touched
    site_members = defaultdict(list)
    for name, row in sites.items():
        assert row['LOC'] in touched
        assert row['selected_RAW'] == str(int(name in raw))
        assert row['selected_S'] == str(int(name in sem))
        assert row['selected_P'] == str(int(row['physical_parent'] in phy))
        assert row['mapping_reason'] == 'ACTUAL_NATIVE_MAPPING'
        if name in members:
            for key in ('REF_NAME', 'LOC', 'BEL', 'SLR', 'physical_parent'):
                assert row[key] == members[name][key], (point, name, key)
        site_members[row['LOC']].append(row)
    assert set(site_members) == touched
    site_counts = defaultdict(Counter)
    for site, rows in site_members.items():
        assert len({r['SLR'] for r in rows}) == 1
        family = 'CLB' if site.startswith('SLICE_') else site.split('_')[0]
        counts = site_counts[(rows[0]['SLR'], family)]
        counts['touched_sites'] += 1
        label = 'shared_with_outside_P' if any(r['physical_parent'] not in phy for r in rows) else 'currently_only_candidate_P'
        counts[label] += 1
    site_summary = [dict(SLR=k[0], site_family=k[1], **v) for k,v in sorted(site_counts.items())]
    assert site_summary == fact['P_touched_shared_exclusive_sites']
    native = REPORT / f'utilization_candidate_{point}_SLR.rpt'
    lines = native.read_text().splitlines()
    assert f'NAME == "{root}"' in lines[6]
    starts = [i for i,line in enumerate(lines) if line.lstrip().startswith('|') and [v.strip() for v in line.split('|')[1:5]] == ['Site Type','SLR0','SLR1','SLR2']]
    assert len(starts) == 1
    native_numbers = {}
    for i in range(starts[0] + 2, len(lines)):
        if not lines[i].startswith('|'):
            break
        fields = [v.strip() for v in lines[i].split('|')[1:-1]]
        native_numbers[fields[0]] = dict(native_line=i+1, **{f'SLR{j}': float(fields[j+1]) for j in range(3)})
    assert native_numbers == fact['native_exact_hierarchy_SLR_resources']
    raw_refs, phy_refs = dict(Counter(refmap(raw).values())), dict(Counter(refmap(phy).values()))
    assert raw_refs == fact['RAW_REF_counts'] and phy_refs == fact['P_REF_counts']
    counts = dict(RAW=len(raw), S=len(sem), P=len(phy))
    assert all(fact[k] == v for k,v in counts.items())
    closed = marker(REPORT / f'candidate_membership_{point}_closed.txt')
    assert closed['completed'] == '1' and closed['root'] == closed['actual_exact_root'] == root
    assert all(int(closed[k]) == v for k,v in counts.items())
    stage = marker(REPORT / f'stage_candidate_{point}_membership_resources_closed.txt')
    assert stage['native_tcl_code'] == '0' and stage['failed_queries'] == ''
    receipts = [q for q in queries if q['query'] in (f'candidate_{point}_membership',f'candidate_{point}_exact_native_resources')]
    assert receipts == fact['native_closed_query_receipts'] and len(receipts) == 2
    policy = {k: dict(Counter(r[k] for r in parents.values())) for k in ('IS_LOC_FIXED','IS_BEL_FIXED','USER_SLR_ASSIGNMENT','RLOC','RLOC_ORIGIN','MACRO_NAME','DONT_TOUCH','actual_PBLOCKS')}
    assert all(r['IS_LOC_FIXED'] in ('0','') and r['IS_BEL_FIXED'] in ('0','') for r in parents.values())
    assert all(not r[k] for r in parents.values() for k in ('USER_SLR_ASSIGNMENT','RLOC','RLOC_ORIGIN','MACRO_NAME','actual_PBLOCKS'))
    assert not fact['P_policy_anomalies']
    slrs = {'RAW':dict(Counter(r['SLR'] for r in members.values())), 'S':dict(Counter(members[n]['SLR'] for n in sem)), 'P':dict(Counter(r['SLR'] for r in parents.values()))}
    assert all(fact[k + '_actual_SLR_counts'] == v for k,v in slrs.items())
    sets[point] = {k:set(v) for k,v in (('RAW',raw),('S',sem),('P',phy))}
    results[point] = dict(root=root, counts=counts, actual_SLR=slrs, recovered_space_tables=[dict(table=k,rows=len(v),columns=c) for k,v,c in [('membership',members,24),('physical_members',parents,18),('site_members',sites,11)]], RAW_REF_counts=raw_refs, P_REF_counts=phy_refs, DSP_split_mapping=normalized, native_resources=native_numbers, sites=site_summary, P_policy_value_counts=policy, native_stage=stage, native_queries=receipts, all_bijections_and_cross_table_checks=True, hotspot_intersection_from_engineering_facts_not_recomputed_in_this_audit=fact['hotspot_intersection'])

assert all(not sets['C01'][k] & sets['C02'][k] for k in ('RAW','S','P'))
probe_path = ATT / 'actual_failed_batch_property_probe_closed_facts.json'
identity(probe_path)
probe = json.loads(probe_path.read_text())
for artifact in probe['artifacts']:
    verify(artifact)
vectors = table(REPORT / 'failed_batch_actual_property_vectors.tsv')
scalars = table(REPORT / 'failed_batch_actual_property_columns.tsv')
probe_result = []
def scalar(value):
    parts = tcl.splitlist(value)
    assert len(parts) == 1
    return parts[0]
for vector in vectors:
    prop = vector['property']
    values = list(tcl.splitlist(scalar(vector['actual_native_vector_Tcl_list'])))
    rows = [row for row in scalars if row['property'] == prop]
    scalar_values = [scalar(row['scalar_value']) for row in rows]
    assert len(values) == len(rows) == int(vector['expected_objects']) == int(vector['native_vector_list_length']) == 9
    assert scalar_values == values
    assert len({scalar(row['object']) for row in rows}) == 9
    assert all(row['scalar_is_empty'] == str(int(value == '')) for row,value in zip(rows,values))
    actual = next(x for x in probe['properties'] if x['property'] == prop)
    assert actual['native_vector_values'] == values
    probe_result.append(dict(property=prop, native_vector_count=len(values), scalar_count=len(rows), empty_scalar_count=values.count(''), vector_scalar_order_equal=True))
assert len(vectors) == 5 and len(scalars) == 45
assert next(q for q in queries if q['query']=='actual_failed_batch_property_diagnostics') == probe['native_query']
output = dict(observed_utc=datetime.now(timezone.utc).isoformat(), reviewer='A007', execution='closed_membership_resource_and_probe_audit_completed', verdict='closed_subsets_consistent_after_explicit_strict_space_decode', applicability='E006/R004/AT001 exact physopt graph, C01/C02 membership/resources and actual nine-object probe only; cut/timing/terminal not assessed', review='independent CPU raw-text checks; no EDA, DCP binary read, production mutation or process/lock control', format_anomaly=dict(native_export='TAB header; single SPACE rows in exactly three table families', recovery='For a known K-element Tcl join, K-1 separator spaces plus any embedded spaces give split length > K. Every data row has exactly K fields under split(single ASCII space), preserving empties; all names/REFs/flags and identities independently cross-checked. Reject any mismatch; raw files unchanged.', source='Archived candidate_inspector.tcl lines 356,365,379 use unquoted literal TAB, so Tcl supplies no separator argument and join defaults to single SPACE.', pure_Tcl_reproduction_passed=True), candidates=results, candidate_RAW_S_P_disjoint=True, probe=probe_result, original_alignment_failure_column='UNKNOWN; current nine-object call does not reproduce misalignment, including LOC/BEL', limits=['Candidate selection and migration benefit remain NOT_ASSESSED pending full cut and timing.', 'Source-site sharing is current primitive membership, not guaranteed released or destination-packable CLBs.', 'P policy observations exclude inherited ancestor/macro qualification; DONT_TOUCH values are retained, not cleared or silently rejected.', 'Hotspot intersections in this record are explicitly referenced engineering facts and previous separate independent target evidence, not recomputed here.', 'Native query code zero alone does not prove valid table serialization; the independent decoder checks are necessary.'], identities=list(identities.values()), audit_script=identity(Path(__file__)))
out = RUN / 'independent_membership_resources_and_probe_review.json'
with out.open('x') as stream:
    json.dump(output,stream,indent=2)
    stream.write('\n')
print(json.dumps(dict(output=identity(out), candidates={k:{s:v[s] for s in ('counts','sites','P_policy_value_counts')} for k,v in results.items()}, probe=probe_result),indent=2))
