#!/usr/bin/env python3
"""Qualify an E005 native completion after a lost supervisor without inventing wait status."""
from datetime import datetime
import json
from pathlib import Path

import m002_execution_profile as policy
from emit_current_board_evidence import file_id, input_manifest, key_values, require, sha256
import run_m002_no_wall as guard

RECEIPT = 'synthesis_supervision_recovery.json'
SCHEMA = 'm002_e005_synthesis_supervision_recovery_v1'


def _identity(record):
    require(file_id(Path(record['path'])) == record, 'recovery evidence identity changed')


def _base(project, report, attempt, handover):
    require(not (attempt/'status.json').exists(), 'recovery cannot replace an original supervisor status')
    require(handover.parent == attempt and handover.name.startswith('supervision_handover_'),
            'foreign supervision handover')
    started = json.loads((attempt/'started.json').read_text())
    command = json.loads((attempt/'command.json').read_text())
    require(all(started.get(k) == command.get(k) for k in command), 'original start/command mismatch')
    require(started.get('stage') == 'synth' and started.get('execution_profile') == policy.OPTIMIZED_PROFILE and
            started.get('project') == str(project) and started.get('report') == str(report), 'foreign original synthesis')
    workspace = Path(__file__).resolve().parents[4]
    auth = policy.authorization(workspace, 'synth', attempt, report, policy.OPTIMIZED_PROFILE)
    require(json.loads((attempt/'execution_authorization.json').read_text()) == auth and
            started.get('authorization') == policy.identity(attempt/'execution_authorization.json'),
            'original synthesis recovery authorization mismatch')
    wrapper = key_values(report/'launcher_status.txt')
    require(wrapper.get('stage') == 'synth' and wrapper.get('project') == str(project) and
            wrapper.get('reports') == str(report) and wrapper.get('exit_code') == '0' and
            wrapper.get('native_exit_code') == '0', 'native/wrapper synthesis did not both complete zero')
    snapshot = json.loads((handover/'original_evidence_snapshot.json').read_text())
    require(snapshot.get('original_terminal_status_exists') is False, 'snapshot has original terminal status')
    for name in ['started.json', 'command.json', 'resources.jsonl']:
        identity = snapshot['original_immutable_records'][name]
        require(Path(identity['path']) == attempt/name, 'foreign original evidence snapshot')
        _identity(identity)
    original_last = json.loads((attempt/'resources.jsonl').read_text().splitlines()[-1])
    require(snapshot['original_last_resource_sample'] == original_last, 'original last sample changed')
    adoption = json.loads((handover/'started.json').read_text())
    terminal = json.loads((handover/'status.json').read_text())
    require(all(terminal.get(k) == v for k, v in adoption.items()), 'handover terminal/start mismatch')
    require(adoption.get('attempt') == str(attempt) and adoption.get('report') == str(report) and
            adoption.get('original_supervisor_pid') == started['supervisor_pid'] and
            adoption.get('original_leader_pid') == started['leader_pid'] and
            adoption.get('original_leader_start_ticks') == original_last['processes'][str(started['leader_pid'])]['start_ticks'] and
            adoption.get('original_started_sha256') == sha256(attempt/'started.json'), 'handover original identity mismatch')
    require(adoption.get('resource_supervision_gap') is True and
            adoption.get('native_process_restarted') is False and adoption.get('original_records_modified') is False and
            adoption.get('original_last_resource_utc') == original_last['utc'] and
            adoption.get('gap_end_utc') == adoption.get('started_utc') and
            datetime.fromisoformat(adoption['started_utc']) > datetime.fromisoformat(original_last['utc']),
            'lost supervision gap must remain explicit')
    expected = dict(cpu_affinity=list(range(8)), nice=5, rss_limit_bytes=192*guard.GIB,
                    mem_available_floor_bytes=48*guard.GIB, mem_low_grace_seconds=30,
                    disk_free_floor_bytes=30*guard.GIB, timeout_seconds=None, no_output_timeout_seconds=None)
    require(all(adoption.get(k) == v for k, v in expected.items()), 'handover resource policy changed')
    require(terminal.get('stop_reason') is None and terminal.get('native_exit_code') is None and
            terminal.get('native_exit_not_waitable_after_orphaning') is True and
            terminal.get('final_owned_processes') == {} and
            terminal.get('controller_launcher_status') == (report/'launcher_status.txt').read_text(),
            'handover stopped, retained processes, or invented native wait')
    require(datetime.fromisoformat(terminal['ended_utc']) >= datetime.fromisoformat(adoption['started_utc']),
            'invalid handover completion time')
    guard_identity = json.loads((handover/'guard_process_identity.json').read_text())
    require(guard_identity.get('pid') == adoption['adoption_supervisor_pid'] and
            guard_identity['proc_identity']['pgrp'] == adoption['adoption_supervisor_pid'] and
            sha256(Path(guard_identity['cmdline'][1])) == adoption['guard_sha256'], 'adoption guard code/identity changed')
    adopted_last = json.loads((handover/'resources.jsonl').read_text().splitlines()[-1])
    require(adopted_last.get('live_pids') == [] and adopted_last.get('processes') == {},
            'handover final resource sample retains processes')
    tracked = {}
    for source in [attempt/'resources.jsonl', handover/'resources.jsonl']:
        with source.open() as stream:
            for line in stream:
                for pid, row in json.loads(line)['processes'].items():
                    tracked[int(pid)] = row['start_ticks']
    current = guard.process_table()
    require(not any(pid in current and current[pid]['start_ticks'] == ticks for pid, ticks in tracked.items()),
            'original owned process identity is still present')
    sources = [attempt/n for n in ['started.json', 'command.json', 'resources.jsonl', 'execution_authorization.json']]
    sources += [handover/n for n in ['started.json', 'status.json', 'resources.jsonl',
                'original_evidence_snapshot.json', 'guard_process_identity.json']]
    sources += [report/n for n in ['launcher_status.txt', 'inputs.sha256', 'build_identity.txt',
                'fresh_synth_complete.txt', 'vivado.log', 'optimized_structure_synth_result.txt',
                'optimized_boundaries_synth.tsv', 'optimized_control_sources_synth.tsv']]
    structure = (report/'optimized_structure_synth_result.txt').read_text().splitlines()
    require('phase=synth' in structure and 'issues=' in structure and
            'boundary_contract=48input_16gate_16down' in structure, 'new synthesis structure did not pass')
    log = (report/'vivado.log').read_text()
    require('COMPLETED: synth reports at '+str(report) in log and
            'E005_OPTIMIZED_STRUCTURE_COMPLETED synth 48/16/16 boundary CE graphs' in log and
            'Exiting Vivado' in log, 'missing real native completion')
    source_rows = input_manifest(report/'inputs.sha256')
    marker = (report/'fresh_synth_complete.txt').read_text()
    require(str(project) in marker and sha256(report/'inputs.sha256') in marker and
            sha256(report/'build_identity.txt') in marker, 'synthesis completion binding changed')
    return dict(schema=SCHEMA, execution_state='completed_with_supervision_gap',
        execution_profile=policy.OPTIMIZED_PROFILE, stage='synth', project=str(project), report=str(report),
        handover=str(handover), authorization=auth, original_status_missing=True,
        original_supervisor_exit_code=None, original_leader_wait_exit_code=None,
        wrapper_native_exit_code=0, wrapper_aggregate_exit_code=0,
        supervision_continuous=False, original_last_resource_utc=original_last['utc'],
        adoption_started_utc=adoption['started_utc'], adoption_ended_utc=terminal['ended_utc'],
        resource_statistics_scope='observed original/adopted intervals only; gap unobserved',
        source_rows=len(source_rows), evidence={str(p):file_id(p) for p in sources})


def _bindings(attempt, project):
    bindings = json.loads((attempt/'synth_checkpoint_bindings.json').read_text())
    paths = input_manifest(attempt/'synth_checkpoint_bindings.sha256')
    require(bindings.get('project') == str(project) and len(paths) == 45 and
            len(bindings['run_records']) == 23 and len(bindings['consumed_ip_records']) == 22 and
            set(bindings['checkpoints']) == {str(p) for p in paths}, 'incomplete recovered actual checkpoint graph')
    for path, digest in paths.items():
        require(bindings['checkpoints'][str(path)]['sha256'] == digest, 'recovered checkpoint binding changed')
    return dict(checkpoint_manifest=file_id(attempt/'synth_checkpoint_bindings.sha256'),
                checkpoint_bindings=file_id(attempt/'synth_checkpoint_bindings.json'), checkpoint_paths=45)


def record_recovery(project, report, attempt, handover):
    path = attempt/RECEIPT
    require(not path.exists(), 'recovery closure already exists')
    value = {**_base(project,report,attempt,handover), **_bindings(attempt,project),
             'recorded_utc':policy.now().isoformat()}
    with path.open('x') as stream:
        json.dump(value,stream,indent=2); stream.write('\n')
    return validate_recovery(project,report,attempt)


def validate_recovery(project, report, attempt):
    value = json.loads((attempt/RECEIPT).read_text())
    expected = {**_base(project,report,attempt,Path(value['handover'])), **_bindings(attempt,project)}
    require(set(value) == set(expected)|{'recorded_utc'} and
            all(value.get(k) == v for k,v in expected.items()), 'synthesis recovery closure changed')
    return value
