#!/usr/bin/env python3
"""Bounded independent review: no EDA, signals, locks, or large-file reads."""
import ast
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AT = ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution'
OUT = ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003'
CAND = ROOT/'agent/A006/E006_lean_candidate'

def identity(path):
    path = Path(path)
    assert path.stat().st_size < 20_000_000, f'Bounded review limit: {path}'
    before = path.stat()
    value = dict(path=str(path), bytes=before.st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return value

def read(path):
    return json.loads(Path(path).read_text())

def proc(pid):
    try:
        f = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(pid=pid, start_ticks=int(f[19]), state=f[0], pgrp=int(f[2]))
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

def main():
    began = datetime.now(timezone.utc).isoformat()
    facts = read(AT/'controlled_terminal_facts_20261017.json')
    status = read(AT/'status.json')
    inputs = read(AT/'input_bindings.json')
    checked = []
    def verify(row):
        assert identity(row['path']) == row, row['path']
        checked.append(row)
    pinned = {
        'controlled_terminal_facts_20261017.json': 'c066643bfe01cc2b703b6f0357fec84a505dff9684621dcf02ec9ee88348f75f',
        'controlled_terminal_summary_20261017.json': '2b68d966101e1e6f255ae78fa30885cfcd6cedb1460ec16d4426a6a76a28c456',
        'status.json': 'ab63747e8b6f4c6070940f7ef64c1328f09aa0b7d15d087de35407cd80f2c04d',
        'input_bindings.json': '4dbaf3d6aabf1996cbabe7064dab5d955360f88fe2447a124bf967105f9c0c2f',
        'started.json': 'c834e0dc19fc3f67408e6ef195b2b5803cbe24944242db53435a9168d8edf189',
        'controlled_terminal_audit_producer_20261017.py': '87afc7353d9e112609ce9b3be3d52082054f8fcc387470e682aec5dbfc7276f1',
    }
    for name, sha in pinned.items():
        row = identity(AT/name); assert row['sha256'] == sha; checked.append(row)
    for key in ('decision', 'signal', 'reuse_manifest', 'source_log', 'query_receipts', 'stage_receipts'):
        verify(facts[key])
    signal = read(facts['signal']['path']); verify(signal['intent'])
    assert signal['signal_sent'] and signal['signal'] == 'SIGTERM'
    assert (signal['target_pid'], signal['target_start_ticks']) == (942046, 927846090)
    assert identity(AT/'input_bindings.json') == status['inputs'] == read(AT/'started.json')['inputs']
    verify(inputs['contract']); verify(inputs['frozen_inputs']['freeze'])
    assert inputs['contract']['sha256'] == 'cf53ff562b1894620ab0d6cc4398e17718cf815b32b8d2d8fd491adb17754263'
    frozen = read(inputs['frozen_inputs']['freeze']['path'])['files']; assert len(frozen) == 144
    for row in frozen: verify(row)
    assert len(inputs['external_inputs']) == 14 and len(inputs['sources']) == 4
    for row in list(inputs['external_inputs'].values()) + inputs['sources']: verify(row)
    large = []
    for row in list(facts['checkpoints'].values()) + list(facts['reused_closed_artifacts'].values()):
        if row['bytes'] >= 20_000_000:
            st = Path(row['path']).stat(); assert st.st_size == row['bytes']
            large.append(dict(bound_identity=row, observed_bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                              independent_hash=False, basis='A006 actual full hash receipt and reviewed producer, plus independent current stat'))
        else: verify(row)
    assert facts['checkpoints'] == inputs['checkpoints']
    assert facts['reused_closed_artifacts'] == read(facts['reuse_manifest']['path'])['artifacts']
    observed = []
    for row in facts['processes']:
        now = proc(row['pid'])
        assert not now or now['start_ticks'] != row['expected_start_ticks'] or now['state'] == 'Z'
        observed.append(dict(expected=row, current=now))
    pgroup = [r for p in Path('/proc').iterdir() if p.name.isdigit()
              if (r := proc(int(p.name))) and r['pgrp'] == 942061 and r['state'] != 'Z']
    assert not pgroup
    lock = ROOT/'project/hardware/vivado/.m002_eda.lock'; st = lock.stat()
    rows = []
    for line in Path('/proc/locks').read_text().splitlines():
        f = line.split()
        for part in f:
            if part.count(':') != 2: continue
            try: major, minor, inode = part.split(':'); match = (int(major,16),int(minor,16),int(inode)) == (os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
            except ValueError: continue
            if match: rows.append(line)
    assert not rows, rows
    resources = [json.loads(line) for line in (AT/'resources.jsonl').read_text().splitlines()]
    actual = dict(samples=len(resources), first_sample=resources[0]['utc'], last_sample=resources[-1]['utc'],
        maximum_sample_gap_seconds=max((datetime.fromisoformat(b['utc'])-datetime.fromisoformat(a['utc'])).total_seconds() for a,b in zip(resources,resources[1:])),
        sampled_peak_tree_rss_bytes=max(r['rss_bytes'] for r in resources),
        minimum_mem_available_bytes=min(r['mem_available_bytes'] for r in resources),
        minimum_disk_free_bytes=min(r['disk_free_bytes'] for r in resources))
    assert actual == facts['resources']; assert status['owned_survivors'] == []
    assert status['native_exit_code'] == -15 and status['exit_code'] == 125
    assert status['stop_reason'] == 'KeyboardInterrupt:signal 15' and not status['native_natural_terminal_observed']
    assert status['post_integrity_error'] == "NameError: name 'new_peak_sources' is not defined"
    assert not facts['native_diagnostic_completed'] and not facts['engineering_execution_verified']
    assert not facts['closed_stages'] and facts['result'] is None
    assert not status['physical_commands_executed'] and not status['checkpoint_write_executed']
    manifest = read(CAND/'prepared_source_manifest.json')
    assert identity(CAND/'prepared_source_manifest.json')['sha256'] == 'a60797ae6c106257904ff3029b575438e1bd0447f615f16230dd7d4e45512aa0'
    for row in manifest['files']: verify(row)
    old = (CAND/'review_before_planned_scaffold_20261017/run_attribution_lean.py').read_text()
    new = (CAND/'run_attribution_lean.py').read_text()
    assert hashlib.sha256(old.encode()).hexdigest() == 'cdf4c9d8980f08a4bbf15ac6c66f38810dd1ca7e85fea065caf55c629068f746'
    funcs = ['identity', 'freeze_check', 'require_registered_closed', 'prior_registered_identities', 'require']
    def fn(text, name): return ast.dump(next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)
    assert all(fn(old,n) == fn(new,n) for n in funcs)
    marker = '    proc=None;tracked={};stop=None;peak=0;low_since=None'
    assert old.split(marker,1)[1] == new.split(marker,1)[1]
    cpu = read(CAND/'planned_scaffold_CPU_check_CT002_20261017.json')
    assert cpu['exit_code'] == 0 and all(json.loads(cpu['stdout'])['checks'].values())
    for row in json.loads(cpu['stdout'])['actual_planned_scaffold'].values():
        if isinstance(row,dict): verify(row)
    planned = OUT/'attempts/AT001_lean_physopt_attribution'
    assert {p.name for p in planned.iterdir()} == {'run.json','report.md','evidence'}
    assert not any((planned/'evidence').iterdir())
    decision = ROOT/'.research-agent/decision_inputs/E006_R003_lean_execution_authorization_20261017.json'
    auth = read(decision)
    for key in ('decision_evidence','prior_terminal_status','controlled_closure_evidence'): verify(auth[key])
    result = dict(started_utc=began, ended_utc=datetime.now(timezone.utc).isoformat(), execution='independent_bounded_readonly_review_complete',
        verdict='controlled_original_closure_and_minimal_lean_source_admitted', review='independent_A007',
        applicability='Exact E006/R001 terminal and E006/R003 prepared source manifest; no E007 physical applicability verdict',
        checks_passed=True, independently_hashed_identities=checked, large_files_stat_and_engineering_hash_receipt_only=large,
        processes=observed, original_live_pgroup=pgroup,
        proc_locks_readonly_observation=dict(inode=st.st_ino,device_major=os.major(st.st_dev),device_minor=os.minor(st.st_dev),matching_rows=rows),
        resources=actual, transient_contract_audit=identity(AT/'controlled_terminal_audit_CT001_contract_transient.json'),
        transient_contract_caveat='Final exact equality is verified; uninterrupted immutability is not claimed.',
        lean_manifest=identity(CAND/'prepared_source_manifest.json'), lean_CPU_receipt=identity(CAND/'planned_scaffold_CPU_check_CT002_20261017.json'),
        E007_imported_helpers_AST_unchanged=funcs, supervision_and_post_tail_unchanged=True,
        authorization=identity(decision), EDA_executed=False, locks_acquired=False, process_control=False,
        limitations=['Original native attribution incomplete; status NameError retained.',
                    'Large DCP and primitive export not independently rehashed.',
                    'E007 whole runner binding requires explicit rebind before E007 execution.',
                    'Actual hotspot/failure endpoint attribution remains pending lean stage closure.'])
    target = OUT/'independent_switch_and_lean_review.json'
    with target.open('x') as stream: stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(identity(target)))

if __name__ == '__main__': main()
