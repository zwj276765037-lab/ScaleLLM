#!/usr/bin/env python3
"""Read closed failure/connection TSVs and independently check leaf-pin totals.

No EDA calls or process control. Tcl.splitlist decodes recorded Tcl lists only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tkinter
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from capture_stage import ROOT, ATTEMPT, REPORT, identity, table, put, closed_queries

TCL = tkinter.Tcl()
SLRS = {'SLR0', 'SLR1', 'SLR2'}


def words(value):
    return list(TCL.splitlist(value))


def counts(value):
    items = words(value)
    assert len(items) % 2 == 0, value
    return {items[i]: int(items[i + 1]) for i in range(0, len(items), 2)}


def pin_class(terminal):
    if terminal in {'CE', 'GE', 'WE', 'WEA', 'WEB', 'WREN'}:
        return 'ENABLE_WRITE_CONTROL'
    if terminal in {'R', 'S', 'CLR', 'PRE', 'RST', 'RESET', 'RSTRAMARSTRAM',
                    'RSTRAMB', 'RSTREGARSTREG', 'RSTREGB'}:
        return 'RESET_SET_CONTROL'
    if terminal in {'C', 'CLK', 'CLKA', 'CLKB', 'CLKARDCLK', 'CLKBWRCLK', 'ACLK', 'BCLK'}:
        return 'CLOCK'
    if terminal in {'D', 'Q'} or re.fullmatch(r'(DI|DO|DIN|DOUT|ADDR|A|B|P)[0-9]+', terminal):
        return 'DATA_ADDRESS_PIN'
    return 'OTHER_UNCLASSIFIED_PIN'


def refined_class(ref, terminal):
    """Reviewed E007 REF rules with native IS_CLOCK explicitly unavailable."""
    if ref in {'GND', 'VCC'}:
        return 'CONSTANT'
    if ref.startswith('DSP') and re.fullmatch(r'C(?:\[[0-9]+\])?', terminal):
        return 'DATA_ARITHMETIC'
    # E006 did not query IS_CLOCK; never fabricate CLOCK_NATIVE_PIN evidence.
    if re.fullmatch(r'FD(RE|CE|PE)', ref):
        if terminal == 'C': return 'CLOCK_REF_PIN'
        if terminal in {'R', 'CLR', 'PRE'}: return 'RESET_SET'
        if terminal == 'CE': return 'ENABLE_WRITE_CONTROL'
        if terminal in {'D', 'Q'}: return 'DATA_REGISTER'
    if ref.startswith('DSP'):
        if terminal == 'CLK': return 'CLOCK_REF_PIN'
        if terminal.startswith('RST'): return 'RESET_SET'
        if terminal.startswith('CE'): return 'ENABLE_WRITE_CONTROL'
        if re.fullmatch(r'(A|B|C|D|P|ACIN|ACOUT|BCIN|BCOUT|PCIN|PCOUT)(\[[0-9]+\])?', terminal):
            return 'DATA_ARITHMETIC'
        return 'UNKNOWN_DSP_PIN'
    if re.match(r'^BU(FG|FH|FR|FIO|FMR|FCE)', ref) and terminal == 'O':
        return 'CLOCK_BUFFER_OUTPUT_REF'
    if re.fullmatch(r'LUT[1-6]', ref):
        return 'LOGIC_PIN_FUNCTION_UNCLASSIFIED'
    if ref in {'MUXF7', 'MUXF8'} and terminal == 'S':
        return 'SELECT_CONTROL'
    if ref in {'MUXF7', 'MUXF8', 'CARRY8'}:
        return 'DATA_LOGIC_PRIMITIVE'
    return 'UNKNOWN_REF_PIN'


def ranked(counter, fields, maximum=None):
    items = counter.most_common(maximum)
    return [dict(zip(fields, key), count=count) for key, count in items]


def graph(summary_path, endpoint_path, hotspot_cells, retain_all=False):
    endpoint_rows = iter(table(endpoint_path))
    seen = {}
    totals = Counter()
    resolutions = Counter()
    raw_categories = Counter()
    refined_categories = Counter()
    edges = Counter()
    detailed_edges = Counter()
    other_terms = Counter()
    top_load = []
    top_cross = []
    records = []
    all_rows = []
    for source_row in table(summary_path):
        canonical = source_row['canonical_net']
        nd = int(source_row['driver_pin_count'])
        nl = int(source_row['leaf_load_pins'])
        positions = [words(v) for v in words(source_row['driver_positions'])]
        assert len(positions) == nd and all(len(v) == 7 for v in positions), canonical
        driver_rows = []
        load_cells = set()
        load_slrs = Counter()
        categories = Counter()
        refined = Counter()
        owner_slrs = Counter()
        local_edges = Counter()
        local_details = Counter()
        local_other = Counter()
        hotspot_loads = 0
        digest = hashlib.sha256()
        pins = set()
        for row in islice(endpoint_rows, nd + nl):
            assert row['canonical_net'] == canonical, (canonical, row)
            key = (row['role'], row['pin'])
            assert key not in pins, (canonical, key)
            pins.add(key)
            digest.update((json.dumps(row, sort_keys=True) + '\n').encode())
            if row['role'] == 'DRIVER':
                driver_rows.append(row)
            else:
                assert row['role'] == 'LOAD', row
                load_cells.add(row['cell'])
                load_slrs[row['SLR']] += 1
                category = pin_class(row['REF_PIN_NAME'])
                categories[category] += 1
                refined[refined_class(row['REF_NAME'], row['REF_PIN_NAME'])] += 1
                owner_slrs[(row['owner'], row['SLR'])] += 1
                local_edges[(row['owner'], row['SLR'], category)] += 1
                local_details[(row['owner'], row['detail'], row['SLR'], category)] += 1
                if category == 'OTHER_UNCLASSIFIED_PIN':
                    local_other[(row['REF_NAME'], row['REF_PIN_NAME'])] += 1
                hotspot_loads += row['cell'] in hotspot_cells
        assert len(pins) == nd + nl, 'Endpoint file ended before declared count'
        assert len(driver_rows) == nd
        assert [[r[k] for k in ['pin', 'owner', 'detail', 'REF_NAME', 'LOC', 'BEL', 'SLR']]
                for r in driver_rows] == positions, canonical
        assert len(load_cells) == int(source_row['unique_load_cells']), canonical
        assert dict(load_slrs) == counts(source_row['load_SLR_pin_counts']), canonical
        assert dict(categories) == counts(source_row['terminal_category_counts']), canonical
        assert hotspot_loads == int(source_row['hotspot_union_leaf_load_pins']), canonical
        resolution = ('SINGLE_PRIMITIVE_DRIVER' if nd == 1 else
                      'NO_PRIMITIVE_DRIVER' if nd == 0 else 'MULTIPLE_PRIMITIVE_DRIVERS')
        assert source_row['driver_resolution'] == resolution
        owner = driver_rows[0]['owner'] if nd == 1 else 'UNKNOWN'
        slr = driver_rows[0]['SLR'] if nd == 1 else 'UNKNOWN'
        cross = (sum(n for s, n in load_slrs.items() if s != slr)
                 if nd == 1 and slr in SLRS and not (set(load_slrs) - SLRS) else 'UNAVAILABLE')
        assert str(cross) == source_row['cross_SLR_leaf_load_pins'], canonical
        signature = (json.dumps(source_row, sort_keys=True), digest.hexdigest())
        totals['raw_summary_rows'] += 1
        totals['raw_endpoint_rows'] += nd + nl
        if canonical in seen:
            assert signature == seen[canonical], 'Alias copies differ for the same canonical net'
            totals['repeated_canonical_summary_rows'] += 1
            all_rows.append(dict(canonical_net=canonical, repeated_alias=True))
            continue
        seen[canonical] = signature
        totals['unique_canonical_nets'] += 1
        totals['canonical_segments_summed_not_distinct_all_design'] += int(source_row['segment_count'])
        totals['driver_leaf_pins'] += nd
        totals['load_leaf_pins'] += nl
        totals['hotspot_union_leaf_load_pins'] += hotspot_loads
        totals['source_cells_inside_union'] += sum(r['cell'] in hotspot_cells for r in driver_rows)
        if cross == 'UNAVAILABLE':
            totals['cross_SLR_unavailable_nets'] += 1
            totals['load_leaf_pins_on_cross_unknown_nets'] += nl
        else:
            totals['known_cross_SLR_leaf_load_pins'] += cross
            totals['known_cross_SLR_nets'] += cross > 0
        resolutions[resolution] += 1
        raw_categories.update(categories)
        refined_categories.update(refined)
        other_terms.update(local_other)
        for (lo, ls, category), count in local_edges.items():
            edge = (owner, slr, lo, ls, category)
            edges[('leaf_pins',) + edge] += count
            edges[('unique_canonical_nets',) + edge] += 1
        for (lo, detail, ls, category), count in local_details.items():
            detailed_edges[(owner, slr, lo, detail, ls, category)] += count
        detail = dict(canonical_net=canonical, driver_resolution=resolution,
            drivers=[{k: r[k] for k in ['cell', 'owner', 'detail', 'REF_NAME', 'LOC', 'BEL', 'SLR', 'REF_PIN_NAME']} for r in driver_rows],
            leaf_load_pins=nl, unique_load_cells=len(load_cells),
            load_owner_SLR_pin_counts=ranked(owner_slrs, ['owner', 'SLR']),
            terminal_categories=dict(categories), refined_terminal_categories=dict(refined),
            cross_SLR_leaf_load_pins=cross, hotspot_union_leaf_load_pins=hotspot_loads)
        top_load.append(detail)
        top_load.sort(key=lambda r: (-r['leaf_load_pins'], r['canonical_net']))
        del top_load[40:]
        if cross != 'UNAVAILABLE' and cross:
            top_cross.append(detail)
            top_cross.sort(key=lambda r: (-r['cross_SLR_leaf_load_pins'], r['canonical_net']))
            del top_cross[40:]
        if retain_all:
            records.append(detail)
        all_rows.append(dict(canonical_net=canonical, repeated_alias=False)) if retain_all else None
    assert next(endpoint_rows, None) is None, 'Endpoint rows remain after declared summary scope'
    return dict(totals=dict(totals), resolutions=dict(resolutions),
        native_terminal_categories=dict(raw_categories), refined_terminal_categories=dict(refined_categories),
        top_unclassified_REF_terminals=ranked(other_terms, ['REF_NAME', 'REF_PIN_NAME'], 80),
        edges=edges, detail_edge_top200=ranked(detailed_edges,
            ['source_owner', 'source_SLR', 'load_owner', 'load_detail', 'load_SLR', 'native_terminal_category'], 200),
        top_by_leaf_loads=top_load, top_by_known_cross_SLR_loads=top_cross,
        retained_unique_nets=records, raw_summary_order=all_rows)


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['failure_samples', 'hotspot_connections'])
    stage = parser.parse_args().stage
    selected = [r for r in table(REPORT / 'stage_receipts.tsv') if r['stage'] == stage]
    assert len(selected) == 1, 'No unique naturally closed stage receipt'
    receipt = selected[0]
    output = ATTEMPT / (stage + '_closed_stage_facts.json')
    short = ATTEMPT / (stage + '_closed_stage_summary.json')
    assert not output.exists() and not short.exists(), 'Do not overwrite completed evidence'
    bindings_path = ATTEMPT / 'input_bindings.json'
    binding_id = identity(bindings_path)
    assert binding_id == json.loads((ATTEMPT / 'started.json').read_text())['inputs']
    bindings = json.loads(bindings_path.read_text())
    assert [identity(r['path']) for r in bindings['sources']] == bindings['sources']
    hotspot_cells = {r['cell'] for r in table(REPORT / 'hotspot_UNION_cells.tsv')}
    prefix = 'failure' if stage == 'failure_samples' else 'hotspot_union_canonical'
    files = [REPORT / (prefix + '_net_locations.tsv'), REPORT / (prefix + '_net_endpoints.tsv')]
    result = graph(*files, hotspot_cells, retain_all=stage == 'failure_samples')
    edge_fields = ['metric', 'source_owner', 'source_SLR', 'load_owner', 'load_SLR', 'terminal_category']
    python_edges = result.pop('edges')
    result['module_SLR_terminal_edges'] = ranked(python_edges, edge_fields)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), stage=stage,
        native_closed_stage_receipt=receipt, native_stage_zero=receipt['native_tcl_code'] == '0',
        native_closed_query_receipts=closed_queries(stage),
        input_bindings=binding_id, actual_archived_native_sources_unchanged=bindings['sources'],
        stage_marker=identity(REPORT / ('stage_' + stage + '_closed.txt')),
        parsed_graph=result, endpoint_count_and_native_summary_checks='ALL_CONSISTENT',
        refined_terminal_rules='Reviewed E007 REF_NAME/REF_PIN_NAME rules in archived producer with IS_CLOCK=NOT_QUERIED. Unknown REF/pin stays UNKNOWN_REF_PIN or UNKNOWN_DSP_PIN; native terminal-only categories remain separately preserved. Primitive semantics do not prove protocol/payload width.',
        endpoint_scope='Selected complete nets, primitive leaf DIRECTION IN/OUT only; excludes INOUT/top ports. NO_PRIMITIVE_DRIVER is not proof of no real driver.',
        graph_scope='Current E005 physopt; route-failure strings are queried exactly without suffix repair or guessed aliases.',
        units='unique canonical nets and primitive leaf pins, not SLLs/routed resources/traffic; alias canonical nets deduplicated',
        fixed_window_congestion='UNAVAILABLE; occupancy is not congestion', formal_signoff=False,
        final_native_supervisor_freeze_DCP_PID_lock='PENDING_OR_SEPARATELY_VERIFIED_AT_TRUE_TERMINAL')
    if stage == 'hotspot_connections':
        assert not result['totals'].get('repeated_canonical_summary_rows', 0)
        coverage = dict(line.split('\t', 1) for line in (REPORT / 'connection_coverage.tsv').read_text().splitlines())
        assert int(coverage['selected_hotspot_union_primitive_cells']) == len(hotspot_cells)
        assert int(coverage['unique_canonical_complete_nets']) == result['totals']['unique_canonical_nets']
        native_edges = Counter()
        path = REPORT / 'hotspot_union_module_SLR_edges.tsv'
        for row in table(path):
            key = tuple(row[k] for k in edge_fields)
            assert key not in native_edges
            native_edges[key] = int(row['count'])
        assert native_edges == python_edges, 'Independent endpoint edges differ from native edge table'
        facts.update(connection_coverage=coverage, independent_endpoint_edges_equal_native=True)
        files += [REPORT / 'connection_coverage.tsv', path]
    else:
        targets_path = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/route_failure_sample_targets.json'
        oracle_path = targets_path.parent / 'failure_nodes_cpu_tile_intersection.json'
        targets = json.loads(targets_path.read_text())
        oracle = {r['sample_id']: r for r in json.loads(oracle_path.read_text())['nodes']}
        resolutions_path = REPORT / 'failure_exact_net_resolution.tsv'
        resolution_rows = list(table(resolutions_path))
        target_nets = {r['target_id']: r for n in targets['nodes'] for r in n['listed_contender_nets']}
        assert len(resolution_rows) == len(target_nets) == 40
        aliases = defaultdict(list)
        exact = []
        for row in resolution_rows:
            assert row['exact_requested_net_name'] == target_nets[row['sample_id']]['net_name']
            match_count = int(row['exact_match_count'])
            assert len(words(row['actual_exact_matches'])) == match_count
            if match_count == 1:
                assert row['status'] == 'EXACT_ONE'
                exact.append(row)
        assert len(exact) == len(result['raw_summary_order'])
        for row, summary in zip(exact, result['raw_summary_order']):
            aliases[summary['canonical_net']].append(dict(sample_id=row['sample_id'],
                exact_requested_net_name=row['exact_requested_net_name']))
        nodes_path = REPORT / 'failure_node_device_mapping.tsv'
        nodes = list(table(nodes_path))
        assert len(nodes) == len(targets['nodes']) == 10
        for row in nodes:
            expected = oracle[row['sample_id']]
            assert row['exact_tile'] == expected['tile_name']
            assert set(words(row['actual_NW_region_memberships'])) == set(expected['actual_tile_list_memberships'])
        facts.update(failure_exact_resolution=resolution_rows,
            exact_resolution_status_counts=dict(Counter(r['status'] for r in resolution_rows)),
            exact_strings_to_canonical_alias_groups=dict(aliases),
            device_nodes=nodes, independent_tile_membership_equal_cpu_oracle=True,
            unique_failure_nodes_in_hotspot_union=sum(bool(words(r['actual_NW_region_memberships'])) for r in nodes),
            failure_source_scope=targets['source_scope'],
            failure_sample_limits='Tool top10 overlap nodes/up to5 contenders; actual source4 per node. Not complete failure distribution; sample graph may differ from current physopt graph.',
            independent_targets=identity(targets_path), independent_tile_oracle=identity(oracle_path))
        files += [resolutions_path, nodes_path]
    producer = ATTEMPT / ('capture_' + stage + '_producer.py')
    shutil.copy2(Path(__file__), producer)
    facts['producer'] = identity(producer)
    facts['producer_helper'] = identity(Path(__file__).with_name('capture_stage.py'))
    facts['artifacts'] = [identity(p) for p in files]
    put(output, facts)
    summary = {k: facts[k] for k in ['recorded_utc', 'stage', 'native_stage_zero',
        'native_closed_stage_receipt', 'endpoint_count_and_native_summary_checks',
        'endpoint_scope', 'graph_scope', 'units', 'fixed_window_congestion', 'formal_signoff']}
    summary['graph_totals'] = result['totals']
    summary['resolutions'] = result['resolutions']
    summary['native_terminal_categories'] = result['native_terminal_categories']
    summary['refined_terminal_categories'] = result['refined_terminal_categories']
    summary['top_by_leaf_loads'] = result['top_by_leaf_loads'][:5]
    summary['top_by_known_cross_SLR_loads'] = result['top_by_known_cross_SLR_loads'][:5]
    if stage == 'failure_samples':
        summary.update({k: facts[k] for k in ['exact_resolution_status_counts',
            'unique_failure_nodes_in_hotspot_union', 'independent_tile_membership_equal_cpu_oracle', 'failure_sample_limits']})
    else:
        summary['independent_endpoint_edges_equal_native'] = facts['independent_endpoint_edges_equal_native']
    summary['full_facts'] = identity(output)
    put(short, summary)
    print(json.dumps(dict(summary=identity(short), facts=identity(output),
        totals=result['totals']), ensure_ascii=False))


if __name__ == '__main__':
    main()
