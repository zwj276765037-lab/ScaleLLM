#!/usr/bin/env python3
"""Audit the ended AT004 failed graph without EDA or any process control."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
AT = ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
REPORT = ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'project/hardware/vivado/scripts'))
import m002_physical_evidence as evidence


def identity(path):
    path = Path(path).resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            digest.update(chunk)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {'path': str(path), 'bytes': after.st_size, 'sha256': digest.hexdigest()}


def save(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    target = AT/'failed_route_terminal_facts.json'
    summary = AT/'failed_route_terminal_summary.json'
    producer = AT/'capture_failed_route_terminal_producer.py'
    excerpt = AT/'route_failure_final_native_excerpt.txt'
    assert not any(p.exists() for p in [target, summary, producer, excerpt])
    status = json.loads((AT/'status.json').read_text())
    closure = json.loads((AT/'terminal_facts.json').read_text())
    observers = json.loads((AT/'observer_terminal_facts.json').read_text())
    assert status['native_exit_code'] == status['exit_code'] == 1
    assert status['native_natural_terminal_observed'] and status['stop_reason'] is None
    assert closure['closure_verified'] and all(closure['checks'].values())
    assert observers['both_observers_exit0'] and observers['observer_processes_absent']
    bindings = json.loads((AT/'input_bindings.json').read_text())
    parent_record = json.loads(Path(bindings['parent']['path']).read_text())
    assert identity(bindings['parent']['path']) == bindings['parent']
    parent = identity(parent_record['checkpoint']['path'])
    assert parent == parent_record['checkpoint']
    assert parent['bytes'] == 396068466 and parent['sha256'] == '8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f'
    sources = []
    for row in (REPORT/'archived_sources.sha256').read_text().splitlines():
        sha, filename = row.split(None, 1)
        actual = identity(filename.strip())
        assert actual['sha256'] == sha
        sources.append(actual)
    actual_archives = sorted(str(p.resolve()) for p in (REPORT/'stage_sources').iterdir() if p.is_file())
    assert len(sources) == len(actual_archives) == 39
    assert sorted(p['path'] for p in sources) == actual_archives
    source_bindings = [identity(row['path']) for row in bindings['source_bindings']]
    assert source_bindings == bindings['source_bindings']
    physical = json.loads((REPORT/'E008_physical_evidence.json').read_text())
    failed_artifacts = [identity(row['path']) for row in physical['failed_route_artifacts']]
    assert failed_artifacts == physical['failed_route_artifacts']
    checkpoint = next(p for p in failed_artifacts if p['path'].endswith('/route_failed.dcp'))
    assert checkpoint['bytes'] == 765705446 and checkpoint['sha256'] == '51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21'
    log = (REPORT/'vivado.log').read_text().splitlines()
    start = next(i for i, line in enumerate(log) if line == 'Phase 9 Verifying routed nets')
    stop = next(i for i in range(start, len(log)) if log[i].startswith('route_design: Time (s):'))
    overlap = re.search(r'There are (\d+) node overlaps', '\n'.join(log[start:stop+1]))
    congestion = re.search(r'\[Route 35-162\] (\d+) signals failed to route due to routing congestion', '\n'.join(log[start:stop+1]))
    assert overlap and congestion
    counts = {'node_overlaps': int(overlap[1]), 'congestion_failed_signals': int(congestion[1])}
    assert counts == {'node_overlaps': 702396, 'congestion_failed_signals': 547548}
    elapsed = re.search(r'elapsed = (\d+):(\d+):(\d+)', log[stop])
    native_elapsed = int(elapsed[1])*3600+int(elapsed[2])*60+int(elapsed[3])
    original = (REPORT/'route_failed_original_error.tcllist').read_text()
    epoch = int(re.search(r'epoch (\d+) disposition diagnostic_failed_route', original)[1])
    command = evidence.key_values(REPORT/'route_command_result.txt')
    receipts = list(csv.DictReader((REPORT/'route_failed_capture_receipts.tsv').open(), delimiter='\t'))
    assert [row['label'] for row in receipts] == ['checkpoint', 'route_status', 'timing', 'congestion', 'drc']
    assert all(row['code'] == '0' for row in receipts)
    assert int(receipts[0]['started_epoch']) == epoch
    assert command['native_tcl_code'] == '1' and command['ended_epoch'] == receipts[-1]['ended_epoch']
    route_text = (REPORT/'route_failed_status.rpt').read_text()
    route_counts = {}
    labels = {'logical_nets': 'logical nets', 'not_needing_routing': 'nets not needing routing',
              'internally_routed': 'internally routed nets', 'no_loads': 'nets with no loads',
              'routable_nets': 'routable nets', 'fully_routed_nets': 'fully routed nets',
              'routing_errors': 'nets with routing errors', 'resource_conflicts': 'nets with resource conflicts'}
    for key, label in labels.items():
        matches = re.findall(r'^\s*# of '+re.escape(label)+r'\.+\s*:\s*(\d+)\s*:', route_text, re.MULTILINE)
        assert len(matches) == 1, (key, matches)
        route_counts[key] = int(matches[0])
    assert route_counts['fully_routed_nets']+route_counts['routing_errors'] == route_counts['routable_nets']
    assert route_counts['resource_conflicts'] == route_counts['routing_errors'] == counts['congestion_failed_signals']
    rows = list(csv.DictReader((REPORT/'candidate_scoped_timing_route_failed.tsv').open(), delimiter='\t'))
    groups = {}
    for direction in ['INGRESS', 'EGRESS']:
        for delay in ['max', 'min']:
            part = [p for p in rows if p['direction'] == direction and p['delay_type'] == delay]
            assert len(part) == 16
            groups[direction+'_'+delay] = {'paths': 16, 'worst_slack_ns': min(float(p['SLACK']) for p in part),
                                          'queried_LOAD_pins': int(part[0]['queried_boundary_pins'])}
    cut = json.loads((REPORT/'candidate_cut_summary_route_failed.json').read_text())
    bounded = json.loads((REPORT/'candidate_timing_validation_route_failed.json').read_text())
    compliance = json.loads((REPORT/'candidate_compliance_route_failed.json').read_text())
    assert cut['directed_boundary_complete'] and cut['candidate_leaf_coverage_complete']
    assert bounded['complete_directional_query_sets'] and bounded['native_query_count'] == 4
    assert compliance['compliance_established'] and compliance['selected_SLR_counts'] == {'SLR2': 9491}
    assert not compliance['original_missing'] and not compliance['new_pblock_objects']
    assert 'E008_STAGE_COMPLETED locality_route_failed' in log
    assert (REPORT/'candidate_failed_route_capture.txt').read_text().startswith('code 0 ')
    assert not any((REPORT/p).exists() for p in ['candidate_phase_route_status.txt', 'route_result.txt', 'integrity_route.json', 'route.dcp'])
    with excerpt.open('x') as stream:
        stream.write('\n'.join(log[start:stop+1])+'\n')
    shutil.copy2(Path(__file__), producer)
    data = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'execution_state': 'failed', 'verdict': 'inconclusive',
            'native_route_original_failure_utc': datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
            'native_route_reported_elapsed_seconds': native_elapsed, 'command_receipt_includes_failure_diagnostics': command,
            'failure_capture_receipts': receipts, 'supervisor_ended_utc': status['ended_utc'],
            'native_exit_code': 1, 'supervisor_exit_code': 1, 'normal_natural_terminal': True,
            'final_native_failure_counts': counts, 'failed_route_status_counts': route_counts, 'legal_route_complete': False,
            'failure_graph_global_timing': evidence.timing_metrics(REPORT/'route_failed_timing.rpt'),
            'failure_graph_global_timing_verdict': 'FAIL_SETUP_HOLD_AND_PULSE_WIDTH',
            'failed_graph_bounded_through_LOAD_timing': groups, 'complete_route_global_POST_exists': False,
            'failed_graph_locality_complete': True, 'failed_graph_candidate_compliance': compliance,
            'failed_graph_cut': {k: cut[k] for k in ['canonical_nets', 'retained_endpoint_rows', 'candidate_boundary_driver_load_pairs', 'directed_boundary_complete', 'candidate_leaf_coverage_complete']},
            'failed_checkpoint': checkpoint, 'failed_diagnostic_artifacts_all_independently_hashed': failed_artifacts,
            'parent_checkpoint_independently_unchanged': parent, 'archived_sources_count': len(sources), 'archived_sources': sources,
            'original_source_bindings_count': len(source_bindings), 'original_source_bindings_all_unchanged': True,
            'production_144_and_full_closure': identity(AT/'terminal_facts.json'), 'observer_closure': identity(AT/'observer_terminal_facts.json'),
            'native_failure_excerpt': identity(excerpt), 'native_excerpt_first_line': start+1, 'native_excerpt_last_line': stop+1,
            'artifact_identities': [identity(REPORT/p) for p in ['vivado.log', 'route_command_result.txt', 'candidate_failed_route_capture.txt', 'candidate_cut_summary_route_failed.json', 'candidate_timing_validation_route_failed.json', 'candidate_compliance_route_failed.json', 'candidate_scoped_timing_route_failed.tsv', 'candidate_reconciliation_route_failed.json']],
            'producer': identity(producer), 'formal_reset_CDC_IO': 'OPEN',
            'limits': ['Failed-graph global timing header Routed is not complete legal-route signoff; DRC says Partially Routed/RTSTAT-13.',
                       'Candidate failed-locality compliance is separate from missing successful-route global POST/fresh80/resetCDCIO/bus-skew coverage.',
                       'Four capped through-LOAD groups are not global timing/full-cut TNS/independent complete cut crossing paths.',
                       'Original six warned bus-skew destination pins and shared source lack a successful full-route coverage report; safety remains OPEN.',
                       'Place/physopt reviews are reused, not rerun; no EDA/retry/newAT and no attribution of all global deltas to C01.',
                       'Native success-phase route_counts parser does not accept the dotted failure-report labels; this audit matches the actual native labels explicitly without changing consumed sources.']}
    save(target, data)
    brief = {k: data[k] for k in ['recorded_utc', 'execution_state', 'verdict', 'native_route_original_failure_utc', 'native_route_reported_elapsed_seconds', 'supervisor_ended_utc', 'final_native_failure_counts', 'failed_route_status_counts', 'legal_route_complete', 'failure_graph_global_timing', 'failure_graph_global_timing_verdict', 'failed_graph_bounded_through_LOAD_timing', 'failed_checkpoint', 'archived_sources_count', 'formal_reset_CDC_IO', 'limits']}
    brief['facts'] = identity(target)
    save(summary, brief)
    print(json.dumps({'facts': identity(target), 'summary': identity(summary), 'all_explicit_checks_passed': True}))


if __name__ == '__main__':
    main()
