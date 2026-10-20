"""A007 bounded offline replay; writes only to this review directory."""
from pathlib import Path
import collections, csv, datetime, hashlib, importlib.util, json, os, re, subprocess

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / '.research-agent/project.json').is_file())
RUN = ROOT / 'project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix'
NATIVE = RUN / 'evidence/native'
SOURCE = ROOT / 'project/E009_m003_failed_net_attribution/experiment_status/audit_timing_scope_v2.py'

def identity(p):
    b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def rows(p):
    with p.open(newline='') as f:
        yield from csv.DictReader(f, delimiter='\t')

def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    assert identity(SOURCE)['sha256'] == 'd15ce41875ab74bf8c2381727390ba37344852ad7873b430f65660ee0d0f2535'
    snapshot = HERE / 'timing_scope_parser_v2_snapshot.py'
    assert not snapshot.exists()
    snapshot.write_bytes(SOURCE.read_bytes())
    spec = importlib.util.spec_from_file_location('timing_parser', snapshot)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    by_tag = collections.defaultdict(set)
    for row in rows(NATIVE / 'deep_selected.tsv'):
        for tag in row['tags'].split(','):
            by_tag[tag].add(row['canonical'])
    nets = {tag: sorted(ns)[:16] for tag, ns in by_tag.items()}
    # Replay only the archived generated data declarations, without EDA.
    fixture = 'source {' + str(NATIVE / 'deep_targets.tcl') + '}\ndict for {tag ns} $timing_groups {foreach n $ns {puts [join [list $tag $n] "\t"]}}\n'
    tcl = subprocess.run(['tclsh'], input=fixture, text=True, capture_output=True, check=True)
    assert not tcl.stderr
    native_nets = collections.defaultdict(list)
    for line in tcl.stdout.splitlines():
        tag, net = line.split('\t')
        native_nets[tag].append(net)
    assert dict(native_nets) == nets
    selected_nets = set().union(*map(set, nets.values()))
    # Collect complete selected-net IN sets, then take the group union's
    # lexical first sixteen. This differs from producer's streaming top-k.
    pins_by_net = collections.defaultdict(set)
    scanned = matched = 0
    for row in rows(NATIVE / 'candidate_endpoints.tsv'):
        scanned += 1
        if row['canonical'] in selected_nets and row['kind'] == 'LEAF_PIN' and row['DIRECTION'] == 'IN':
            pins_by_net[row['canonical']].add(row['name'])
            matched += 1
    pins = {tag: sorted(set().union(*(pins_by_net[n] for n in ns)))[:16] for tag, ns in nets.items()}
    engineer = json.loads((RUN / 'timing_scope_offline_audit_v2.json').read_text())
    indexed = {(x['group'], x['delay_type']): x for x in engineer['results']}
    receipts = list(rows(NATIVE / 'timing_receipts.tsv'))
    assert len(receipts) == len(indexed) == 56
    results = []
    negative_count = total_paths = 0
    for receipt in receipts:
        tag, delay = receipt['group'], receipt['delay_type']
        claim = indexed[tag, delay]
        assert claim['reconstructed_net_IDs'] == nets[tag]
        assert claim['reconstructed_group_IN_pin_scope'] == pins[tag]
        assert int(receipt['endpoints']) == len(pins[tag]) == 16
        assert receipt['native_code'] == '0'
        report = Path(receipt['output_or_error'])
        actual_id = identity(report)
        assert actual_id == claim['report']
        text = report.read_text()
        blocks = re.split(r'(?=^Slack \()', text, flags=re.M)[1:]
        assert len(blocks) == claim['reported_path_count'] <= 2
        paths = []
        for block, expected in zip(blocks, claim['paths']):
            actual = parser.path_membership(block, set(pins[tag]))
            for key in ['explicit_scope_pins', 'scope_pins_reconstructed_from_primitive_arc', 'scope_pins_only_outside_data_path']:
                assert actual[key] == expected[key]
            assert actual['explicit_scope_pins'] or actual['scope_pins_reconstructed_from_primitive_arc']
            # Every actual launch C/CLK is a substantive negative: it occurs
            # in the report/clock-to-Q arc but must not qualify as through.
            source = actual['native_source']
            assert source.rsplit('/', 1)[-1] in ('C', 'CLK')
            negative = parser.path_membership(block, {source})
            assert not negative['explicit_scope_pins'] and not negative['scope_pins_reconstructed_from_primitive_arc']
            negative_count += 1
            slack = re.match(r'Slack \(([^)]+)\)\s*:\s*([-+0-9.]+)ns', block)
            assert slack and float(slack.group(2)) == expected['slack_ns']
            paths.append(dict(source=source, destination=actual['native_destination'], slack_ns=float(slack.group(2)), explicit=actual['explicit_scope_pins'], inferred_primitive_input=actual['scope_pins_reconstructed_from_primitive_arc']))
        total_paths += len(paths)
        if not blocks:
            assert re.search(r'No timing paths found', text, re.I)
        results.append(dict(group=tag, delay_type=delay, report=actual_id, expected_group_IN_pins=pins[tag], paths=paths, no_paths=not blocks))
    assert total_paths == negative_count == 104
    output = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), execution='one selected candidate-endpoint scan and all56 report replay complete', verdict='DATA-path membership supported for all104 reported bounded paths;4 native no-path reports retained; raw native argv not separately captured', applicability='actual AT003 outputs and d15ce418 parser, no EDA', review='independent offline scope reconstruction accepted with header limitation', candidate_endpoint_rows_scanned=scanned, selected_leaf_IN_rows=matched, candidate_endpoint_bytes=(NATIVE/'candidate_endpoints.tsv').stat().st_size, reconstructed_tags=len(nets), reports=len(results), reported_paths=total_paths, actual_launch_C_CLK_negative_cases=negative_count, results=results, sources=[identity(SOURCE), identity(Path(__file__)), identity(RUN/'timing_scope_offline_audit_v2.json')], limitations=engineer['limitations'])
    target = HERE / 'timing_scope_independent_replay.json'
    with target.open('x') as f:
        f.write(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(result=identity(target), reports=len(results), paths=total_paths, launch_clock_negatives=negative_count), ensure_ascii=False))

if __name__ == '__main__':
    main()
